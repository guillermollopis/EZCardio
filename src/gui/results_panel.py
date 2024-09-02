from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtWidgets import QPushButton, QCheckBox, QApplication, QStackedWidget, QLabel, QTableWidgetItem, QTableView, QMessageBox, QScrollArea
from functools import partial
from logic.operation_mode.operation_mode import Modes, Mode
from logic.operation_mode.partitioning import Partitions, SinglePartition
import pyqtgraph as pg
import numpy as np
from modified_dependencies.pyhrv import time_domain as td
from modified_dependencies.pyhrv import frequency_domain as fd
from modified_dependencies.pyhrv import nonlinear as nl
from modified_dependencies.pyhrv import tools as results_tools
import logging
logging.getLogger("matplotlib").setLevel(logging.WARNING)
import sympy as sp
import matplotlib.pyplot as plt
import matplotlib as mpl
mpl.use('Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import weakref
from config import settings
import json
import scipy.sparse as spd
from pathlib import Path
from utils.utils_general import resource_path
import scipy
import pandas as pd
import numpy as np

#from neurokit2.hrv import hrv_frequency, hrv_nonlinear


class ResultsFrame(QtWidgets.QFrame):

    def __init__(self, main_window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setParent(main_window)
        self.application = main_window.application
        self.setContentsMargins(0, 0, 0, 0)
        self.setFrameStyle(self.NoFrame)

        # Layout
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        #self.setLayout(self.layout)

        # Focus
        self.installEventFilter(self)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Sizing
        #self.n = 800
        #self.updateHeight()

        # Drag and Drop Related
        # TODO: only accept drag/drop of other Frames (through MIME data)
        self.setAcceptDrops(True)
        self.resultsPanel: ResultsPanel = None
        self.dragStartPos = QtCore.QPoint()
        self.drag = None

    def updateHeight(self):
        self.setFixedHeight(self.n)



class ResultsPanel(QtWidgets.QWidget):

    _instance = None

    def __init__(self, frame: ResultsFrame):
        super().__init__()
        
        self.setParent(frame)

        layout = QtWidgets.QHBoxLayout()

        self.rr_intervals = []


        # Load settings from JSON file
        with open(resource_path(Path('settings.json'))) as f:
            self.settings = json.load(f)

        # load results keys file
        with open(resource_path(Path('modified_dependencies', 'pyhrv', 'files', 'varying_keys.json'))) as f:
            self.varying_keys = json.load(f)

        self.default_bin_size = 1000/128

        

        # -------------------First column of selector and buttons------------------------
        first_column_layout = QtWidgets.QVBoxLayout()
        first_column_widget = QtWidgets.QWidget()
        first_column_widget.setLayout(first_column_layout)

        self.autoupdate_checkbox = QCheckBox("Auto update results", self)
        self.autoupdate_checkbox.setChecked(self.settings['auto_update_results'])
        self.autoupdate_checkbox.stateChanged.connect(self.update_current_result)
        self.current_active_result = 0

        # selector
        self.dropdown_name = QtWidgets.QComboBox()
        self.dropdown_name.addItems(Partitions.all_names())
        self.dropdown_name.wheelEvent = lambda event: None
        self.dropdown_name.currentIndexChanged.connect(self.update_current_result)

        self.dropdown_index = QtWidgets.QComboBox()
        self.dropdown_index.addItems(list(range(1, len(Partitions.find_partition_by_name(self.dropdown_name.currentText()))+1)))
        self.dropdown_index.wheelEvent = lambda event: None
        self.dropdown_index.currentIndexChanged.connect(self.update_current_result)

        first_column_layout.addWidget(self.dropdown_name)
        first_column_layout.addWidget(self.dropdown_index)

        self.dropdown_name.currentTextChanged.connect(self.update_own_index_combobox)

        # buttons
        self.home_domain_button = QPushButton("Home")
        first_column_layout.addWidget(self.home_domain_button)
        self.home_domain_button.setStyleSheet("background-color: blue; color: white;")

        self.time_domain_button = QPushButton("Time domain")
        first_column_layout.addWidget(self.time_domain_button)
        self.time_domain_button.setStyleSheet("background-color: blue; color: white;")

        self.frequency_domain_button = QPushButton("Frequency domain")
        first_column_layout.addWidget(self.frequency_domain_button)
        self.frequency_domain_button.setStyleSheet("background-color: blue; color: white;")

        self.non_linear_button = QPushButton("Non linear")
        first_column_layout.addWidget(self.non_linear_button)
        self.non_linear_button.setStyleSheet("background-color: blue; color: white;")

        self.time_varying_button = QPushButton("Time varying")
        first_column_layout.addWidget(self.time_varying_button)
        self.time_varying_button.setStyleSheet("background-color: blue; color: white;")

        self.sports_button = QPushButton("Sports")
        first_column_layout.addWidget(self.sports_button)
        self.sports_button.setStyleSheet("background-color: blue; color: white;")

        layout.addWidget(first_column_widget, alignment=QtCore.Qt.AlignLeft)

        self.stacked_widget = QStackedWidget()

        layout.addWidget(self.stacked_widget)

        # stacked widget has 5 options with different layouts. With each function, update the layout with the current results and set the widget


        # ----------------------HOME RESULTS-------------------------
        self.home_domain_layout = QtWidgets.QGridLayout()
        self.home_domain_widget = QtWidgets.QWidget()
        self.home_domain_widget.setLayout(self.home_domain_layout)
        self.stacked_widget.addWidget(self.home_domain_widget)
        # Set stretch factors
        # For columns: (column index, stretch factor)
        self.home_domain_layout.setColumnStretch(0, 3)  # First column (where graph is) takes 30% of width
        self.home_domain_layout.setColumnStretch(1, 7)  # Second column takes the remaining 70%

        # For rows: (row index, stretch factor)
        self.home_domain_layout.setRowStretch(0, 5)  # First row (where graph is) takes 50% of height
        self.home_domain_layout.setRowStretch(1, 5)  # Second row takes the remaining 50%
        
        # --------------------TIME DOMAIN RESULTS--------------------
        self.time_domain_layout = QtWidgets.QHBoxLayout()
        self.time_domain_widget = QtWidgets.QWidget()
        self.time_domain_widget.setLayout(self.time_domain_layout)
        # add results to stacked
        self.stacked_widget.addWidget(self.time_domain_widget)

        # --------------------FREQUENCY DOMAIN RESULTS--------------------
        self.frequency_domain_layout = QtWidgets.QHBoxLayout()
        self.frequency_domain_widget = QtWidgets.QWidget()
        self.frequency_domain_widget.setLayout(self.frequency_domain_layout)
        # frequency options is the first column and has the kind of frequency analysis and numbers
        self.frequency_options_layout = QtWidgets.QGridLayout()
        self.frequency_options_widget = QtWidgets.QWidget()
        self.frequency_options_widget.setLayout(self.frequency_options_layout)
        # add options to options layout
        self.frequency_analysis_type = QtWidgets.QComboBox()
        if (self.settings['lomb_scargle']):
            self.frequency_analysis_type.addItem("Lomb scargle")
        else:
            self.frequency_analysis_type.addItem("Welch")
        self.frequency_analysis_type.addItem("Autorregressive")
        self.frequency_analysis_type.wheelEvent = lambda event: None
        self.frequency_options_layout.addWidget(self.frequency_analysis_type, 0, 0, 1, 4)
        self.frequency_analysis_type.currentTextChanged.connect(lambda: self.set_frequency_results(self.rr_intervals))
        # vlf
        self.vlf_label = QtWidgets.QLabel("VLF: ")
        self.frequency_options_layout.addWidget(self.vlf_label, 1, 0)
        self.vlf_min = QtWidgets.QLineEdit(str(self.settings['vlf_min']))
        self.frequency_options_layout.addWidget(self.vlf_min, 1, 1)
        self.vlf_min.textChanged.connect(lambda: self.set_frequency_results(self.rr_intervals))
        self.vlf_midle = QtWidgets.QLabel(" - ")
        self.frequency_options_layout.addWidget(self.vlf_midle, 1, 2)
        self.vlf_max = QtWidgets.QLineEdit(str(self.settings['vlf_max']))
        self.frequency_options_layout.addWidget(self.vlf_max, 1, 3)
        self.vlf_max.textChanged.connect(lambda: self.set_frequency_results(self.rr_intervals))
        # lf
        self.lf_label = QtWidgets.QLabel("LF: ")
        self.frequency_options_layout.addWidget(self.lf_label, 2, 0)
        self.lf_min = QtWidgets.QLineEdit(str(self.settings['lf_min']))
        self.frequency_options_layout.addWidget(self.lf_min, 2, 1)
        self.lf_min.textChanged.connect(lambda: self.set_frequency_results(self.rr_intervals))
        self.lf_midle = QtWidgets.QLabel(" - ")
        self.frequency_options_layout.addWidget(self.lf_midle, 2, 2)
        self.lf_max = QtWidgets.QLineEdit(str(self.settings['lf_max']))
        self.frequency_options_layout.addWidget(self.lf_max, 2, 3)
        self.lf_max.textChanged.connect(lambda: self.set_frequency_results(self.rr_intervals))
        # hf
        self.hf_label = QtWidgets.QLabel("HF: ")
        self.frequency_options_layout.addWidget(self.hf_label, 3, 0)
        self.hf_min = QtWidgets.QLineEdit(str(self.settings['hf_min']))
        self.frequency_options_layout.addWidget(self.hf_min, 3, 1)
        self.hf_min.textChanged.connect(lambda: self.set_frequency_results(self.rr_intervals))
        self.hf_midle = QtWidgets.QLabel(" - ")
        self.frequency_options_layout.addWidget(self.hf_midle, 3, 2)
        self.hf_max = QtWidgets.QLineEdit(str(self.settings['hf_max']))
        self.frequency_options_layout.addWidget(self.hf_max, 3, 3)
        self.hf_max.textChanged.connect(lambda: self.set_frequency_results(self.rr_intervals))

        self.frequency_domain_layout.addWidget(self.frequency_options_widget)

        # --------------------NON LINEAR RESULTS--------------------
        self.non_linear_layout = QtWidgets.QHBoxLayout()
        self.non_linear_widget = QtWidgets.QWidget()
        self.non_linear_widget.setLayout(self.non_linear_layout)


        # --------------------TIME VARYING RESULTS-------------------
        self.varying_domain_layout = QtWidgets.QHBoxLayout()
        self.varying_domain_widget = QtWidgets.QWidget()
        self.varying_domain_widget.setLayout(self.varying_domain_layout)
        # varying options is the first column and has the kind of varying analysis and numbers
        self.varying_options_layout = QtWidgets.QGridLayout()
        self.varying_options_widget = QtWidgets.QWidget()
        self.varying_options_widget.setLayout(self.varying_options_layout)
        # add options to options layout
        # choose variable
        self.varying_analysis_type = QtWidgets.QComboBox()
        for key in self.varying_keys.keys():
            self.varying_analysis_type.addItem(key)
        self.varying_analysis_type.wheelEvent = lambda event: None
        self.varying_options_layout.addWidget(self.varying_analysis_type, 0, 0)
        self.varying_analysis_type.currentTextChanged.connect(lambda: self.set_varying_results(self.rr_intervals))
        # choose window size
        self.window_size = QtWidgets.QLabel("Window size (s): ")
        self.varying_options_layout.addWidget(self.window_size, 1, 0)
        self.window_size_value = QtWidgets.QLineEdit("300")
        self.varying_options_layout.addWidget(self.window_size_value, 1, 1)
        self.window_size_value.returnPressed.connect(lambda: self.set_varying_results(self.rr_intervals))
        self.window_size_value.editingFinished.connect(lambda: self.set_varying_results(self.rr_intervals))
        # choose sliding window size
        self.sliding_window_size = QtWidgets.QLabel("Overlap between windows (%): ")
        self.varying_options_layout.addWidget(self.sliding_window_size, 2, 0)
        self.sliding_window_size_value = QtWidgets.QLineEdit("0")
        self.varying_options_layout.addWidget(self.sliding_window_size_value, 2, 1)
        self.sliding_window_size_value.returnPressed.connect(lambda: self.set_varying_results(self.rr_intervals))
        self.sliding_window_size_value.editingFinished.connect(lambda: self.set_varying_results(self.rr_intervals))
        # choose minimum data length
        self.minimum_effective_data = QtWidgets.QLabel("Minimum data without noise (s): ")
        self.varying_options_layout.addWidget(self.minimum_effective_data, 3, 0)
        self.minimum_effective_data_value = QtWidgets.QLineEdit("30")
        self.varying_options_layout.addWidget(self.minimum_effective_data_value, 3, 1)
        self.minimum_effective_data_value.returnPressed.connect(lambda: self.set_varying_results(self.rr_intervals))
        self.minimum_effective_data_value.editingFinished.connect(lambda: self.set_varying_results(self.rr_intervals))

        self.varying_domain_layout.addWidget(self.varying_options_widget)

        # SPORTS
        self.sports_layout = QtWidgets.QGridLayout()
        self.sports_widget = QtWidgets.QWidget()
        self.sports_widget.setLayout(self.sports_layout)

        self.sports_layout.setColumnStretch(0, 1)  # First column (where graph is) takes 70% of width
        self.sports_layout.setColumnStretch(1, 6)  # Second column takes the remaining 30%
        self.sports_layout.setColumnStretch(2, 3)  # First column (where graph is) takes 70% of width

        # For rows: (row index, stretch factor)
        self.sports_layout.setRowStretch(0, 1)  # First row (where graph is) takes 50% of height
        self.sports_layout.setRowStretch(1, 1)  # Second row takes the remaining 50%
        self.sports_layout.setRowStretch(2, 1) 
        self.sports_layout.setRowStretch(3, 1) 
        self.sports_layout.setRowStretch(4, 1) 
        self.sports_layout.setRowStretch(5, 1) 

        # Checkboxes
        self.cardiorespiratory_button = QtWidgets.QCheckBox("Cardiorespiratory")
        self.sports_layout.addWidget(self.cardiorespiratory_button, 0, 0) 
        self.cardiorespiratory_button.stateChanged.connect(self.update_current_result)

        self.trimp_button = QCheckBox("Training effect")
        self.sports_layout.addWidget(self.trimp_button, 1, 0) 
        self.trimp_button.stateChanged.connect(self.update_current_result)

        self.metabolic_button = QCheckBox("Metabolic profile")
        self.sports_layout.addWidget(self.metabolic_button, 2, 0) 
        self.metabolic_button.stateChanged.connect(self.update_current_result)

        self.heart_rate_recovery_button = QCheckBox("Heart Rate Recovery")
        self.sports_layout.addWidget(self.heart_rate_recovery_button, 3, 0) 
        self.heart_rate_recovery_button.stateChanged.connect(self.update_current_result)

        # Create a button group and add checkboxes to it
        checkbox_group = QtWidgets.QButtonGroup(self)
        checkbox_group.setExclusive(True)  # Only one checkbox can be checked
        checkbox_group.addButton(self.cardiorespiratory_button)
        checkbox_group.addButton(self.trimp_button)
        checkbox_group.addButton(self.metabolic_button)
        checkbox_group.addButton(self.heart_rate_recovery_button)

        # add home to stacked
        self.stacked_widget.addWidget(self.home_domain_widget)

        # add results to stacked
        self.stacked_widget.addWidget(self.time_domain_widget)

        # add frequency to stacked
        self.stacked_widget.addWidget(self.frequency_domain_widget)

        # add non linear to stacked
        self.stacked_widget.addWidget(self.non_linear_widget)

        # add varying to stacked
        self.stacked_widget.addWidget(self.varying_domain_widget)

        # add sports to stacked
        self.stacked_widget.addWidget(self.sports_widget)

        frame.setLayout(layout)
        
        ResultsPanel._instance = weakref.ref(self)()


    @staticmethod
    def get():
        return ResultsPanel._instance if ResultsPanel._instance is not None else None
    

    def update_current_result(self):
        from gui import PALMS
        
        if Partitions.all_names() == []:
            return
        
        if (self.autoupdate_checkbox.isChecked):
            if (self.current_active_result == 1): # home
                self.set_home_results(PALMS.get().rr_intervals)
            if (self.current_active_result == 2): # time
                self.set_time_results(PALMS.get().rr_intervals)
            if (self.current_active_result == 3): # frequency
                self.set_frequency_results(PALMS.get().rr_intervals)
            if (self.current_active_result == 4): # nonlinear
                self.set_non_linear_results(PALMS.get().rr_intervals)
            if (self.current_active_result == 5): # varying
                self.set_varying_results(PALMS.get().rr_intervals)
            if (self.current_active_result == 6): # sports
                self.set_sports_results(PALMS.get().rr_intervals)


    def update_name_combobox():
        ResultsPanel.get().dropdown_name.clear()
        ResultsPanel.get().dropdown_name.addItems(Partitions.all_names())

        ResultsPanel.get().dropdown_index.clear()
        indexes = list(range(1, len(Partitions.find_partition_by_name(ResultsPanel.get().dropdown_name.currentText()))+1))
        ResultsPanel.get().dropdown_index.addItems([str(num) for num in indexes])

    def update_index_combobox():
        ResultsPanel.get().dropdown_index.clear()
        indexes = list(range(1, len(Partitions.find_partition_by_name(ResultsPanel.get().dropdown_name.currentText()))+1))
        ResultsPanel.get().dropdown_index.addItems([str(num) for num in indexes])

    def update_own_index_combobox(self):
        self.dropdown_index.clear()
        indexes = list(range(1, len(Partitions.find_partition_by_name(self.dropdown_name.currentText()))+1))
        self.dropdown_index.addItems([str(num) for num in indexes])

    def set_home_results(self, rr_intervals):

        if Partitions.all_names() == []:
            return

        self.current_active_result = 1
        for button in [self.home_domain_button, self.time_domain_button, self.frequency_domain_button, self.non_linear_button, self.time_varying_button, self.sports_button]:
            button.setStyleSheet("background-color: blue; color: white;")
        self.home_domain_button.setStyleSheet("background-color: red; color: white;")

        import copy

        self.rr_intervals = copy.deepcopy(rr_intervals)
        
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading results")
        loading_box.setText("Loading results...")
        loading_box.show()
        self.stacked_widget.setCurrentWidget(self.home_domain_widget)

        try: 
            current_partition = Partitions.find_partition_by_name(self.dropdown_name.currentText())[self.dropdown_index.currentIndex()]
            from gui.viewer import PALMS
            current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
            current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)
        except Exception as e:
            return
        
        current_rr_intervals = copy.deepcopy(rr_intervals[current_start:current_end])
        
        rr_intervals = copy.deepcopy(rr_intervals[rr_intervals != 0])
        current_rr_intervals = copy.deepcopy(current_rr_intervals[current_rr_intervals != 0])

        rr_detrended = self.get_stationary_rr(rr_intervals)
        current_rr_detrended = copy.deepcopy(rr_detrended[current_start:current_end])

        try:
            # delete previous components in the time layout
            layout = self.home_domain_widget.layout()  # Assuming 'widget' is your QWidget
            while layout.count():
                item = layout.takeAt(0)
                widget_to_remove = item.widget()
                if widget_to_remove:
                    widget_to_remove.setParent(None)
                else:
                    sublayout = item.layout()
                    while sublayout.count():
                        subitem = sublayout.takeAt(0)
                        subwidget = subitem.widget()
                        if subwidget:
                            subwidget.setParent(None)
                    sublayout.setParent(None)

            # see if male or female, age, height and weight
            # get normal and sd of mean_rr, rmssd and rmssd
            default_mean_rr = 926
            std_mean_rr = 90
            default_rmssd = 42
            std_rmssd = 15
            default_sd1 = 50
            std_sd1 = 25
            # get normal and sd of mean_hr, si and sdnn
            default_mean_hr = 65
            std_mean_hr = 7
            default_si = 8.5
            std_si = 2.5
            default_sd2 = 50
            std_sd2 = 25

            # LOCAL VALUES

            # get pns values: mean_rr, rmssd and sd1
            local_mean_rr = round(np.mean(current_rr_intervals)*1000, 3)
            local_rmssd = td.rmssd(current_rr_detrended)
            local_rmssd = round(local_rmssd['rmssd'], 3)
            first_results = nl.poincare(current_rr_intervals, show=False)
            local_sd1 = round(first_results['sd1'], 3)

            # get sns values: mean_hr, si and sd2
            local_mean_hr = 60000 / local_mean_rr
            local_stress_index = self.get_stress_index(current_rr_intervals, current_rr_detrended)
            first_results = nl.poincare(current_rr_intervals, show=False)
            local_sd2 = round(first_results['sd2'], 3)
            
            # get index of pns values
            local_mean_rr_index = round((local_mean_rr - default_mean_rr) / std_mean_rr, 3)
            local_rmssd_index = round((local_rmssd - default_rmssd) / std_rmssd, 3)
            local_sd1_index_ratio = round(local_sd1 / (local_sd1 + local_sd2), 3)
            local_sd1_index = round((local_sd1_index_ratio * 8) - 4, 3)
            local_pns_index = round((local_mean_rr_index + local_rmssd_index + local_sd1_index) / 3, 3)
            if local_mean_rr_index < -4:
                local_mean_rr_index = -4
            if local_mean_rr_index > 4:
                local_mean_rr_index = 4
            if local_rmssd_index < -4:
                local_rmssd_index = -4
            if local_rmssd_index > 4:
                local_rmssd_index = 4
            if local_sd1_index < -4:
                local_sd1_index = -4
            if local_sd1_index > 4:
                local_sd1_index = 4

            # get index of sns values
            local_mean_hr_index = round((local_mean_hr - default_mean_hr) / std_mean_hr, 3)
            local_stress_index2 = round((local_stress_index - default_si) / std_si, 3)
            local_sd2_index_ratio = round(local_sd2 / (local_sd1 + local_sd2), 3)
            local_sd2_index = round((local_sd2_index_ratio * 8) - 4, 3)
            local_sns_index = round((local_mean_hr_index + local_stress_index2 + local_sd2_index) / 3, 3)
            if local_mean_hr_index < -4:
                local_mean_hr_index = -4
            if local_mean_hr_index > 4:
                local_mean_hr_index = 4
            if local_stress_index2 < -4:
                local_stress_index2 = -4
            if local_stress_index2 > 4:
                local_stress_index2 = 4
            if local_sd2_index < -4:
                local_sd2_index = -4
            if local_sd2_index > 4:
                local_sd2_index = 4

            # GLOBAL VALUES
            global_pns_index = np.array([])
            global_sns_index = np.array([])
            t = np.cumsum(rr_intervals)
            index = 0
            result = np.array([])
            current_target = 0
            sliding_window_size = 60
            while index < len(t):
		    	# Find the leftmost value greater than or equal to the current target
                import bisect
                index = bisect.bisect_left(t, current_target, lo=index)
                if index < len(t):
                    result = np.append(result, t[index])
                    current_target += sliding_window_size
                else:
                    break
            
            for i, _t in enumerate(result):
                if _t <= sliding_window_size:
                    indices = np.where(t <= (_t + sliding_window_size))[0]
                    current_rr_intervals = rr_intervals[indices]
                    current_rr_detrended = rr_detrended[indices]
			    # Complete Window
                elif _t < t[-1] - sliding_window_size:
                    indices = np.where(((_t - sliding_window_size) <= t) & (t <= (_t + sliding_window_size)))[0]
                    current_rr_intervals = rr_intervals[indices]
                    current_rr_detrended = rr_detrended[indices]
			    # Incomplete end window
                else:
                    indices = np.where(((_t - sliding_window_size) <= t) & (t <= t[-1]))[0]
                    current_rr_intervals = rr_intervals[indices]
                    current_rr_detrended = rr_detrended[indices]

                mean_rr = round(np.mean(current_rr_intervals)*1000, 3)
                this_rmssd = td.rmssd(current_rr_detrended)
                rmssd = round(this_rmssd['rmssd'], 3)
                this_first_results = nl.poincare(current_rr_intervals, show=False)
                sd1 = round(this_first_results['sd1'], 3)

                # get sns values: mean_hr, si and sd2
                mean_hr = 60000 / local_mean_rr
                stress_index = self.get_stress_index(current_rr_intervals, current_rr_detrended)
                this_first_results = nl.poincare(current_rr_intervals, show=False)
                sd2 = round(first_results['sd2'], 3)
            
                # get index of pns values
                mean_rr_index = round((mean_rr - default_mean_rr) / std_mean_rr, 3)
                rmssd_index = round((rmssd - default_rmssd) / std_rmssd, 3)
                sd1_index_ratio = round(sd1 / (sd1 + sd2), 3)
                sd1_index = round((sd1_index_ratio * 8) - 4, 3)
                global_pns_index = np.append(global_pns_index, round((mean_rr_index + rmssd_index + sd1_index) / 3, 3))

                # get index of sns values
                mean_hr_index = round((mean_hr - default_mean_hr) / std_mean_hr, 3)
                stress_index2 = round((stress_index - default_si) / std_si, 3)
                sd2_index_ratio = round(sd2 / (sd1 + sd2), 3)
                sd2_index = round((sd2_index_ratio * 8) - 4, 3)
                global_sns_index = np.append(global_sns_index, round((mean_hr_index + stress_index2 + sd2_index) / 3, 3))

            # PLOTS
            # plot mean pns and sns in one column
            # SNS PLOT
            from scipy.stats import norm
            fig, ax = plt.subplots(figsize=(10, 2))
            fig.patch.set_facecolor('#add8e6')  # Light blue background

            # Set titles with black text
            ax.set_title(f"Parasympathetic tone (recovery)\nPNS Index = {round(local_pns_index, 3)}", fontsize=14, loc='center', color='black')

            # Define data for the bars
            indexes = [local_mean_rr_index, local_rmssd_index, local_sd1_index]
            labels = ["Mean RR", "RMSSD", "SD1"]
            colors = ['blue', 'blue', 'blue']

            # Plot settings
            xlim = (-4, 4)
            ylim = (0, 1)
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            ax.axis('off')  # No axes

            # Plot the normal curve
            x = np.linspace(xlim[0], xlim[1], 1000)
            y = norm.pdf(x, 0, 1)
            y = y / max(y) * ylim[1] * 0.3  # Normalize and scale the curve
            ax.plot(x, y, color='black')

            # Plot the vertical lines for SD
            ax.axvline(x=0, color='black', linestyle='--')
            ax.axvline(x=-1, color='black', linestyle='--', lw=0.5)
            ax.axvline(x=1, color='black', linestyle='--', lw=0.5)
            ax.text(0, ylim[1]*0.32, '', ha='center', va='top', color='black')
            ax.text(-1, ylim[1]*0.32, '', ha='center', va='top', color='black')
            ax.text(1, ylim[1]*0.32, '', ha='center', va='top', color='black')

            # Bottom labels with black text
            ax.text(xlim[0], ylim[0]-0.1, 'LOW', ha='left', color='black')
            ax.text(0, ylim[0]-0.1, 'NORMAL', ha='center', color='black')
            ax.text(xlim[1], ylim[0]-0.1, 'HIGH', ha='right', color='black')

            # Define the spacing and height of the bars
            spacing = 0.025  # 2.5% of the height of the graph
            bar_height = 0.25  # 30% of the height of the graph

            # Draw the horizontal bars with adjusted height and width
            for i, (index, label) in enumerate(zip(indexes, labels)):
                # Calculate bar width based on the index
                bar_width = (index + 4) / 8 * (xlim[1] - xlim[0])
                # Calculate the position of each bar
                y_pos = 1 - (spacing + bar_height) * (i + 1)
                # Draw the horizontal bar
                ax.barh(y=y_pos, width=bar_width, left=xlim[0], height=bar_height, color=colors[i], edgecolor='white')
                # Adjust text position to be in the middle of the bar
                text_y_pos = y_pos - 0.2 + bar_height / 2
                # Add text inside the bar
                if i== 0:
                    current_index = round(local_mean_rr, 3)
                if i== 1:
                    current_index = round(local_rmssd, 3)
                if i== 2:
                    current_index = f"{round(local_sd1_index_ratio*100, 3)} %"
                ax.text(xlim[0] + bar_width / 2, text_y_pos, f'{label} {current_index}', va='center', ha='center', color='white')

            fig.tight_layout()
            canvas = FigureCanvas(fig)
            self.home_domain_layout.addWidget(canvas, 0, 0)

            # PNS PLOT
            from scipy.stats import norm
            fig, ax = plt.subplots(figsize=(10, 2))
            fig.patch.set_facecolor('#FFCC99')  # Light orange background

            # Set titles with black text
            ax.set_title(f"Sympathetic tone (stress)\nSNS Index = {round(local_sns_index, 3)}", fontsize=14, loc='center', color='black')

            # Define data for the bars
            indexes = [local_mean_hr_index, local_stress_index2, local_sd2_index]
            labels = ["Mean HR", "Stress index", "SD2"]
            colors = ['#FFA500', '#FFA500', '#FFA500']

            # Plot settings
            xlim = (-4, 4)
            ylim = (0, 1)
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            ax.axis('off')  # No axes

            # Plot the normal curve
            x = np.linspace(xlim[0], xlim[1], 1000)
            y = norm.pdf(x, 0, 1)
            y = y / max(y) * ylim[1] * 0.3  # Normalize and scale the curve
            ax.plot(x, y, color='black')

            # Plot the vertical lines for SD
            ax.axvline(x=0, color='black', linestyle='--')
            ax.axvline(x=-1, color='black', linestyle='--', lw=0.5)
            ax.axvline(x=1, color='black', linestyle='--', lw=0.5)
            ax.text(0, ylim[1]*0.32, '', ha='center', va='top', color='black')
            ax.text(-1, ylim[1]*0.32, '', ha='center', va='top', color='black')
            ax.text(1, ylim[1]*0.32, '', ha='center', va='top', color='black')

            # Bottom labels with black text
            ax.text(xlim[0], ylim[0]-0.1, 'LOW', ha='left', color='black')
            ax.text(0, ylim[0]-0.1, 'NORMAL', ha='center', color='black')
            ax.text(xlim[1], ylim[0]-0.1, 'HIGH', ha='right', color='black')

            # Define the spacing and height of the bars
            spacing = 0.025  # 2.5% of the height of the graph
            bar_height = 0.25  # 30% of the height of the graph

            # Draw the horizontal bars with adjusted height and width
            for i, (index, label) in enumerate(zip(indexes, labels)):
                # Calculate bar width based on the index
                bar_width = (index + 4) / 8 * (xlim[1] - xlim[0])
                # Calculate the position of each bar
                y_pos = 1 - (spacing + bar_height) * (i + 1)
                # Draw the horizontal bar
                ax.barh(y=y_pos, width=bar_width, left=xlim[1] - bar_width, height=bar_height, color=colors[i], edgecolor='white')
                # Adjust text position to be in the middle of the bar
                text_y_pos = y_pos - 0.1 + bar_height / 2
                # Add text inside the bar
                if i== 0:
                    current_index = round(local_mean_hr, 3)
                if i== 1:
                    current_index = round(local_stress_index, 3)
                if i== 2:
                    current_index = f"{round(local_sd2_index_ratio*100, 3)} %"
                ax.text(xlim[1] - bar_width / 2, text_y_pos, f'{label} {current_index}', va='center', ha='center', color='white')

            fig.tight_layout()
            canvas = FigureCanvas(fig)
            self.home_domain_layout.addWidget(canvas, 1, 0)


            # PLOT FULL TREND
            array_for_plot = rr_intervals  # Replace with your data
            total_seconds = np.cumsum(rr_intervals)

            # Transform the array for plot
            hr_intervals = 60 / array_for_plot
            extended_arr = np.pad(hr_intervals, (10, 10), mode='edge')
            transformed_values = np.array([np.median(extended_arr[max(i - 10, 0):i + 10 + 1]) for i in range(len(hr_intervals))])

            # Create the second plot
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            ORIGINAL_DATETIME = PALMS.get().ORIGINAL_DATETIME  # Replace with your datetime variable

            # Calculate time for each sample
            import datetime as dt
            if ORIGINAL_DATETIME:
                from dateutil import parser
                from dateutil.relativedelta import relativedelta
                current_result = np.insert(time_values, 0, 0)
                dt = parser.parse(PALMS.get().ORIGINAL_DATETIME)
                time_values = [dt + relativedelta(seconds=seconds) for seconds in current_result[:-1]]
                ax2.set_xlabel('Time [d  HH:MM:SS]')
            else:
                time_values = total_seconds
                if time_values[-1] <= 60:
                    ax2.set_xlabel('Time [s]')
		        # Set x-axis format to MM:SS if the duration of the signal > 60s and <= 1h
                elif 60 < time_values[-1] <= 3600:
                    ax2.set_xlabel('Time [MM:SS]')
                    formatter = mpl.ticker.FuncFormatter(lambda ms, x: str(dt.timedelta(seconds=ms))[2:])
                    ax2.xaxis.set_major_formatter(formatter)	
                else:
                    ax2.set_xlabel('Time [HH:MM:SS]')
                    formatter = mpl.ticker.FuncFormatter(lambda ms, x: str(dt.timedelta(seconds=ms)))
                    ax2.xaxis.set_major_formatter(formatter)
            
            ax2.plot(time_values, transformed_values, color='blue')

            # Add horizontal lines and configure axes
            for line in [50, 60, 70, 80, 90]:
                ax2.axhline(y=line, color='gray', linestyle='-', linewidth=0.5)

            ax2.set_xlim(time_values.min(), time_values.max())
            ax2.set_ylim(-4, transformed_values.max())

            # Show left and bottom axes only
            ax2.spines['top'].set_visible(False)
            ax2.spines['right'].set_visible(False)

            # legend
            # Calculate values for the legend
            avg_value = np.mean(transformed_values)
            min_value = np.min(transformed_values)
            max_value = np.max(transformed_values)

            # Create custom legend
            legend_text = f"HR\nAVG: {avg_value:.2f}\nMIN: {min_value:.2f}\nMAX: {max_value:.2f}"
            ax2.text(0.02, 0.98, legend_text, transform=ax2.transAxes, fontsize=10, verticalalignment='top', 
                     bbox=dict(boxstyle="round,pad=0.3", facecolor='blue', edgecolor='blue', alpha=0.7), color='white')
            

            # Plot additional arrays and fill AUC
            from scipy.interpolate import interp1d
            scaling_factor = 10
            original_indices = np.linspace(0, len(time_values) - 1, num=len(global_pns_index), dtype=int)
            interp_func = interp1d(original_indices, global_pns_index, kind='linear', fill_value="extrapolate")
            interpolated_pns_index = interp_func(np.arange(len(time_values)))
            ax2.plot(time_values, interpolated_pns_index * scaling_factor, color='skyblue', label='PNS')
            ax2.fill_between(time_values, 0, interpolated_pns_index * scaling_factor, color='skyblue', alpha=0.3)

            original_indices = np.linspace(0, len(time_values) - 1, num=len(global_sns_index), dtype=int)
            interp_func = interp1d(original_indices, global_sns_index, kind='linear', fill_value="extrapolate")
            interpolated_sns_index = interp_func(np.arange(len(time_values)))
            ax2.plot(time_values, interpolated_sns_index * scaling_factor, color='peachpuff', label='SNS')
            ax2.fill_between(time_values, 0, interpolated_sns_index * scaling_factor, color='peachpuff', alpha=0.3)

            # Calculate values for the PNS legend
            avg_pns = np.mean(interpolated_pns_index)
            min_pns = np.min(interpolated_pns_index)
            max_pns = np.max(interpolated_pns_index)

            # Calculate values for the second array legend
            avg_sns = np.mean(interpolated_sns_index)
            min_sns = np.min(interpolated_sns_index)
            max_sns = np.max(interpolated_sns_index)

            # Create custom legend for PNS
            legend_text_pns = f"PNS\nAVG: {avg_pns:.2f}\nMIN: {min_pns:.2f}\nMAX: {max_pns:.2f}"
            ax2.text(0.78, 0.98, legend_text_pns, transform=ax2.transAxes, fontsize=10, 
                     verticalalignment='top', horizontalalignment='right',
                     bbox=dict(boxstyle="round,pad=0.3", facecolor='blue', edgecolor='blue', alpha=0.7), 
                     color='white')

            # Create custom legend for the second array (orange legend) at the top right
            legend_text_second_array = f"SNS\nAVG: {avg_sns:.2f}\nMIN: {min_sns:.2f}\nMAX: {max_sns:.2f}"
            ax2.text(0.98, 0.98, legend_text_second_array, transform=ax2.transAxes, fontsize=10, 
                     verticalalignment='top', horizontalalignment='right',
                     bbox=dict(boxstyle="round,pad=0.3", facecolor='orange', edgecolor='orange', alpha=0.7), 
                     color='white')

            # Create and set up the secondary y-axis
            sec_ax = ax2.twinx()
            sec_ax.set_ylim(ax2.get_ylim()[0] / scaling_factor, ax2.get_ylim()[1] / scaling_factor)

            # Add the second plot to the layout
            fig2.subplots_adjust(bottom=0.2)
            canvas2 = FigureCanvas(fig2)
            self.home_domain_layout.addWidget(canvas2, 0, 1, 2, 1)

        except Exception as e:
            error_message = "An error has occurred!"
            QMessageBox.critical(None, "Error", str(e), QMessageBox.Ok)
            import traceback
            error_traceback = traceback.format_exc()
            print(error_traceback)

        loading_box.close()


    def set_time_results(self, rr_intervals):

        if Partitions.all_names() == []:
            return
        
        self.current_active_result = 2
        for button in [self.home_domain_button, self.time_domain_button, self.frequency_domain_button, self.non_linear_button, self.time_varying_button, self.sports_button]:
            button.setStyleSheet("background-color: blue; color: white;")
        self.time_domain_button.setStyleSheet("background-color: red; color: white;")

        try: 
            current_partition = Partitions.find_partition_by_name(self.dropdown_name.currentText())[self.dropdown_index.currentIndex()]
            from gui.viewer import PALMS
            current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
            current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)
        except Exception as e:
            return

        import copy

        self.rr_intervals = copy.deepcopy(rr_intervals)

        rr_intervals = copy.deepcopy(rr_intervals[current_start:current_end])
        
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading results")
        loading_box.setText("Loading results...")
        loading_box.show()
        self.stacked_widget.setCurrentWidget(self.time_domain_widget)
        rr_intervals = copy.deepcopy(rr_intervals[rr_intervals != 0])

        rr_detrended = self.get_stationary_rr(rr_intervals)

        try:
            # delete previous components in the time layout
            layout = self.time_domain_widget.layout()  # Assuming 'widget' is your QWidget
            while layout.count():
                item = layout.takeAt(0)
                widget_to_remove = item.widget()
                if widget_to_remove:
                    widget_to_remove.setParent(None)
                else:
                    sublayout = item.layout()
                    while sublayout.count():
                        subitem = sublayout.takeAt(0)
                        subwidget = subitem.widget()
                        if subwidget:
                            subwidget.setParent(None)
                    sublayout.setParent(None)

            if (self.time_domain_layout.isEmpty):
                self.initialize_time_table()

            
            # get results
            mean_rr = round(np.mean(rr_intervals)*1000, 3)
            mean_rr_5 = np.nanmean(np.pad(rr_intervals.astype(float), (0, self.settings["average_hr"] - rr_intervals.size%self.settings["average_hr"]), mode='constant', constant_values=np.NaN).reshape(-1, self.settings["average_hr"]), axis=1)
            mean_rr_5 = mean_rr_5[~np.isnan(mean_rr_5)]
            mean_rr_detrended = np.nanmean(np.pad(rr_detrended.astype(float), (0, self.settings["average_hr"] - rr_detrended.size%self.settings["average_hr"]), mode='constant', constant_values=np.NaN).reshape(-1, self.settings["average_hr"]), axis=1)
            mean_rr_detrended = mean_rr_detrended[~np.isnan(mean_rr_detrended)]
            sdnn = td.sdnn(mean_rr_detrended)
            #sdnn = np.std(rr_intervals)
            sdnn = round(sdnn['sdnn'], 3)
            
            hr_results = td.hr_parameters(mean_rr_5)
            mean_hr = round(hr_results['hr_mean'], 3)
            max_hr = round(hr_results['hr_max'], 3)
            min_hr = round(hr_results['hr_min'], 3)
            std_hr = round(hr_results['hr_std'], 3)
            rmssd = td.rmssd(rr_detrended)
            rmssd = round(rmssd['rmssd'], 3)
            total_nnxx = td.nnXX(rr_detrended, threshold=(self.settings["nnxx_threshold"]))
            nnxx = round(total_nnxx['nn'+str(self.settings["nnxx_threshold"])], 3)
            pnnxx = round(total_nnxx['pnn'+str(self.settings["nnxx_threshold"])], 3)
            histogram_plot, no_triangular_index = td.triangular_index(rr_intervals, binsize=self.default_bin_size, plot=True, show=False, figsize=None, legend=True)
            triangular_index = td.triangular_index(rr_detrended, binsize=self.default_bin_size, plot=False, show=False, figsize=None, legend=False)
            triangular_index = round(triangular_index['tri_index'], 3)
            tinn = self.hrv_TINN(rr_detrended)

            # Calculate Baevsky Stress Index
            stress_index = self.get_stress_index(rr_intervals, rr_detrended)

            # update table with results
            self.update_time_table([mean_rr, sdnn, mean_hr, std_hr, min_hr, max_hr, rmssd, nnxx, pnnxx, triangular_index, tinn, stress_index])
 
            # update histogram with intervals
            histogram_plot.subplots_adjust(bottom=0.2)
            canvas = FigureCanvas(histogram_plot)
            self.time_domain_layout.addWidget(canvas, 1)

        except Exception as e:
            error_message = "An error has occurred!"
            QMessageBox.critical(None, "Error", str(e), QMessageBox.Ok)
            import traceback
            error_traceback = traceback.format_exc()
            print(error_traceback)

        loading_box.close()

    def hrv_TINN(self, rri):
        # Convert IBI values from seconds to milliseconds
        binsize = 1000/128
        rri = rri * 1000
        bins = np.arange(np.min(rri), np.max(rri) + binsize, binsize)
        bar_y, bar_x = np.histogram(rri, bins=bins)

        min_error = 2 ** 14
        X = bar_x[np.argmax(bar_y)]  # bin where Y is max
        Y = np.max(bar_y)  # max value of Y
        #n = bar_x[np.where(bar_x - np.min(rri) > 0)[0][0]]  # starting search of N
        n = bar_x[0]
        m = X + binsize  # starting search value of M
        N = 0
        M = 0
        # start to find best values of M and N where least square is minimized
        while n < X:
            while m < np.max(rri):
                n_start = np.where(bar_x == n)[0][0]
                n_end = np.where(bar_x == X)[0][0]
                qn = np.polyval(np.polyfit([n, X], [0, Y], deg=1), bar_x[n_start:n_end + 1])
                m_start = np.where(bar_x == X)[0][0]
                m_end = np.where(bar_x == m)[0][0]
                qm = np.polyval(np.polyfit([X, m], [Y, 0], deg=1), bar_x[m_start:m_end + 1])
                q = np.zeros(len(bar_x))
                q[n_start:n_end + 1] = qn
                q[m_start:m_end + 1] = qm
                # least squares error
                error = np.sum((bar_y[n_start:m_end + 1] - q[n_start:m_end + 1]) ** 2)
                if error < min_error:
                    N = n
                    M = m
                    min_error = error
                m += binsize
            n += binsize
        return round(M - N, 3)


    def initialize_time_table(self):
        # First column: Table with 12 rows and 3 columns
        self.time_table_view = QTableView()
        # Create the item model
        self.time_model = QtGui.QStandardItemModel(self)
        self.time_table_view.setModel(self.time_model)
        # Set the table headers
        headers = ['Variable', 'Value', 'Unit']
        self.time_model.setHorizontalHeaderLabels(headers)
        self.time_domain_layout.addWidget(self.time_table_view, 0)
        first_column_time = ['Mean RR', 'SDNN', 'Mean HR', 'Std HR', 'Min HR', 'Max HR',
                'RMS SD', 'NN30', 'PNN30', 'HRV triangular index (bin=7.8125ms)', 'TINN(bin=7.8125ms)', 'Stress index(bin=50ms)']
        first_column_items = [QtGui.QStandardItem(value) for value in first_column_time]
        for row, item in enumerate(first_column_items):
            self.time_model.setItem(row, 0, item)
        third_column_time = ['ms', 'ms', 'beats/min', 'beats/min', 'beats/min', 'beats/min',
                'ms', ' ', '%', '', 'ms', ' ']
        third_column_items = [QtGui.QStandardItem(value) for value in third_column_time]
        for row, item in enumerate(third_column_items):
            self.time_model.setItem(row, 2, item)
        self.time_table_view.setFixedWidth(400)
        self.time_table_view.resizeColumnsToContents()


    def update_time_table(self, values): 
        
        # Clear the table
        index = 0
        for row in range(12):
            for col in range(1,2):
                item = QtGui.QStandardItem(str(round(values[index], 4)))

                # Set the item in the model at the corresponding row and column
                self.time_model.setItem(row, col, item)
            
                index += 1

        self.time_table_view.resizeColumnsToContents()

    
    def export_time_results(self, rr_intervals):

        # get detrended
        detrended_rr = self.get_stationary_rr(rr_intervals)

        mean_rr = round(np.mean(rr_intervals), 3)
        sdnn = td.sdnn(detrended_rr)
        sdnn = round(sdnn['sdnn'], 3)
        hr_results = td.hr_parameters(rr_intervals)
        mean_hr = round(hr_results['hr_mean'], 3)
        max_hr = round(hr_results['hr_max'], 3)
        min_hr = round(hr_results['hr_min'], 3)
        std_hr = round(hr_results['hr_std'], 3)
        sdnn_index = sdnn/mean_rr
        rmssd = td.rmssd(detrended_rr)
        rmssd = round(rmssd['rmssd'], 3)
        total_nnxx = td.nnXX(detrended_rr, threshold=(self.settings["nnxx_threshold"]))
        nnxx = round(total_nnxx['nn'+str(self.settings["nnxx_threshold"])], 3)
        pnnxx = round(total_nnxx['pnn'+str(self.settings["nnxx_threshold"])], 3)
        triangular_index = td.triangular_index(detrended_rr, binsize=self.default_bin_size, plot=False, show=False, figsize=None, legend=False)
        triangular_index = round(triangular_index['tri_index'], 3)
        try:
            tinn = self.hrv_TINN(detrended_rr)
        except:
            tinn = None

        # Calculate Baevsky Stress Index
        stress_index = self.get_stress_index(rr_intervals, detrended_rr)
        

        return mean_rr, sdnn, mean_hr, std_hr, min_hr, max_hr, rmssd, nnxx, pnnxx, triangular_index, tinn, stress_index, sdnn_index

    
    def get_stress_index(self, rr_intervals, rr_values_ms):

        rr_values = rr_intervals

        # amo
        bin_width = 0.050 # kubios documentation says 50
        bins = np.arange(np.min(rr_values_ms), np.max(rr_values_ms) + bin_width, bin_width)
        hist, edges = np.histogram(rr_values_ms, bins)
        most_common_bin_index = np.argmax(hist)
        amo = hist[most_common_bin_index]/len(rr_values_ms)

        # mo
        mo = np.abs(np.median(rr_values)) # original ones, detrended values makes no sense

        # mxdmn
        mxdmn = rr_values_ms.max() - rr_values_ms.min()

        si_index = (amo*100)/(2*mo*mxdmn)

        return round(np.sqrt(si_index), 3)


    def set_frequency_results(self, rr_intervals):

        if Partitions.all_names() == []:
            return

        # get detrended
        #detrended_rr = self.get_stationary_rr(rr_intervals)

        self.current_active_result = 3
        for button in [self.home_domain_button, self.time_domain_button, self.frequency_domain_button, self.non_linear_button, self.time_varying_button, self.sports_button]:
            button.setStyleSheet("background-color: blue; color: white;")
        self.frequency_domain_button.setStyleSheet("background-color: red; color: white;")

        try:
            current_partition = Partitions.find_partition_by_name(self.dropdown_name.currentText())[self.dropdown_index.currentIndex()]
            from gui.viewer import PALMS
            current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
            current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)
        except Exception as e:
            return

        
        self.rr_intervals = rr_intervals

        rr_intervals = rr_intervals[current_start:current_end]
        
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading results")
        loading_box.setText("Loading results...")
        loading_box.show()
        self.stacked_widget.setCurrentWidget(self.frequency_domain_widget)
        rr_intervals = rr_intervals[rr_intervals != 0]


        try:
            fbands = {'ulf': (0, 0), 'vlf': (float(self.vlf_min.text()), float(self.vlf_max.text())), 'lf': (float(self.lf_min.text()), float(self.lf_max.text())), 'hf': (float(self.hf_min.text()), float(self.hf_max.text()))}
            # get results

            if (self.frequency_analysis_type.currentIndex() == 0):
                if (self.settings["lomb_scargle"]):
                    first_result = fd.lomb_psd(nni=rr_intervals, show=False, fbands=fbands, ma_size=self.settings["ma_order"], nfft=self.settings['spectrum_points'])
                    first_figure = first_result['lomb_plot']
                else:
                    first_result = fd.welch_psd(nni=rr_intervals, show=False, fbands=fbands, nfft=self.settings['spectrum_points'])
                    first_figure = first_result['fft_plot']

                # add first graph
                first_canvas = FigureCanvas(first_figure)

                first_figure.subplots_adjust(bottom=0.2)
            
            else:
                second_result = fd.ar_psd(nni=rr_intervals,show=False, fbands=fbands, order=self.settings["ar_order"])
                # add second graph
                second_figure = second_result['ar_plot']
                second_figure.subplots_adjust(bottom=0.2)
                second_canvas = FigureCanvas(second_figure)

            # delete just the last component in the frequency layout, which is the graph
            if (self.frequency_domain_widget.layout().count() == 2):
                # Remove the last widget from the layout
                last_widget_index = self.frequency_domain_layout.count() - 1
            
                last_widget_item = self.frequency_domain_layout.itemAt(last_widget_index)
                last_widget = last_widget_item.widget()
                self.frequency_domain_layout.removeWidget(last_widget)
            
                last_widget.deleteLater()
        
        
            if (self.frequency_analysis_type.currentIndex() == 0):
                scroll_area = QScrollArea()
                scroll_area.setWidget(first_canvas)
                self.frequency_domain_layout.addWidget(scroll_area, 1)
            
            else:
                scroll_area = QScrollArea()
                scroll_area.setWidget(second_canvas)
                self.frequency_domain_layout.addWidget(scroll_area, 1)

            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(error_traceback)

        loading_box.close()


    def export_frequency_results(self, rr_intervals):

        fbands = {'ulf': (0, 0), 'vlf': (float(self.vlf_min.text()), float(self.vlf_max.text())), 'lf': (float(self.lf_min.text()), float(self.lf_max.text())), 'hf': (float(self.hf_min.text()), float(self.hf_max.text()))}
        
        # get results
        if (self.settings["lomb_scargle"] == True):
            first_result = fd.lomb_psd(nni=rr_intervals,show=False, fbands=fbands, ma_size=self.settings["ma_order"], nfft=self.settings['spectrum_points'])
            vlf_peak_welch = round(first_result['lomb_peak'][1], 3)
            lf_peak_welch = round(first_result['lomb_peak'][2], 3)
            hf_peak_welch = round(first_result['lomb_peak'][3], 3)

            vlf_absolute_power_ms2_welch = round(first_result['lomb_abs'][1], 3)
            lf_absolute_power_ms2_welch = round(first_result['lomb_abs'][2], 3)
            hf_absolute_power_ms2_welch = round(first_result['lomb_abs'][3], 3)

            vlf_absolute_power_log_welch = round(first_result['lomb_log'][1], 3)
            lf_absolute_power_log_welch = round(first_result['lomb_log'][2], 3)
            hf_absolute_power_log_welch = round(first_result['lomb_log'][3], 3)

            vlf_relative_power_welch = round(first_result['lomb_rel'][1], 3)
            lf_relative_power_welch = round(first_result['lomb_rel'][2], 3)
            hf_relative_power_welch = round(first_result['lomb_rel'][3], 3)
        
            lf_normalized_power_welch = round(first_result['lomb_norms'][0], 3)
            hf_normalized_power_welch = round(first_result['lomb_norms'][1], 3)

            total_power_welch = round(first_result['lomb_total'], 3)

            lf_hf_ratio_welch = round(first_result['lomb_ratio'], 3)
        else:
            first_result = fd.welch_psd(nni=rr_intervals,show=False, fbands=fbands, nfft=self.settings['spectrum_points'])
            # add first graph
            vlf_peak_welch = round(first_result['fft_peak'][1], 3)
            lf_peak_welch = round(first_result['fft_peak'][2], 3)
            hf_peak_welch = round(first_result['fft_peak'][3], 3)

            vlf_absolute_power_ms2_welch = round(first_result['fft_abs'][1], 3)
            lf_absolute_power_ms2_welch = round(first_result['fft_abs'][2], 3)
            hf_absolute_power_ms2_welch = round(first_result['fft_abs'][3], 3)

            vlf_absolute_power_log_welch = round(first_result['fft_log'][1], 3)
            lf_absolute_power_log_welch = round(first_result['fft_log'][2], 3)
            hf_absolute_power_log_welch = round(first_result['fft_log'][3], 3)

            vlf_relative_power_welch = round(first_result['fft_rel'][1], 3)
            lf_relative_power_welch = round(first_result['fft_rel'][2], 3)
            hf_relative_power_welch = round(first_result['fft_rel'][3], 3)
        
            lf_normalized_power_welch = round(first_result['fft_norm'][0], 3)
            hf_normalized_power_welch = round(first_result['fft_norm'][1], 3)

            total_power_welch = round(first_result['fft_total'], 3)

            lf_hf_ratio_welch = round(first_result['fft_ratio'], 3)


        second_result = fd.ar_psd(nni=rr_intervals,show=False, fbands=fbands, order=self.settings["ar_order"])
        # add second graph
        vlf_peak_ar = round(second_result['ar_peak'][1], 3)
        lf_peak_ar = round(second_result['ar_peak'][2], 3)
        hf_peak_ar = round(second_result['ar_peak'][3], 3)

        vlf_absolute_power_ms2_ar = round(second_result['ar_abs'][1], 3)
        lf_absolute_power_ms2_ar = round(second_result['ar_abs'][2], 3)
        hf_absolute_power_ms2_ar = round(second_result['ar_abs'][3], 3)

        vlf_absolute_power_log_ar = round(second_result['ar_log'][1], 3)
        lf_absolute_power_log_ar = round(second_result['ar_log'][2], 3)
        hf_absolute_power_log_ar = round(second_result['ar_log'][3], 3)

        vlf_relative_power_ar = round(second_result['ar_rel'][1], 3)
        lf_relative_power_ar = round(second_result['ar_rel'][2], 3)
        hf_relative_power_ar = round(second_result['ar_rel'][3], 3)

        lf_normalized_power_ar = round(second_result['ar_norm'][0], 3)
        hf_normalized_power_ar = round(second_result['ar_norm'][1], 3)

        total_power_ar = round(second_result['ar_total'], 3)

        lf_hf_ratio_ar = round(second_result['ar_ratio'], 3)

        return vlf_peak_welch, lf_peak_welch, hf_peak_welch, vlf_absolute_power_ms2_welch, lf_absolute_power_ms2_welch, hf_absolute_power_ms2_welch, vlf_absolute_power_log_welch, lf_absolute_power_log_welch, hf_absolute_power_log_welch, vlf_relative_power_welch, lf_relative_power_welch, hf_relative_power_welch, lf_normalized_power_welch, hf_normalized_power_welch, total_power_welch, lf_hf_ratio_welch, vlf_peak_ar, lf_peak_ar, hf_peak_ar, vlf_absolute_power_ms2_ar, lf_absolute_power_ms2_ar, hf_absolute_power_ms2_ar, vlf_absolute_power_log_ar, lf_absolute_power_log_ar, hf_absolute_power_log_ar, vlf_relative_power_ar, lf_relative_power_ar, hf_relative_power_ar, lf_normalized_power_ar, hf_normalized_power_ar, total_power_ar, lf_hf_ratio_ar



    def set_non_linear_results(self, rr_intervals):

        if Partitions.all_names() == []:
            return

        self.current_active_result = 4
        for button in [self.home_domain_button, self.time_domain_button, self.frequency_domain_button, self.non_linear_button, self.time_varying_button, self.sports_button]:
            button.setStyleSheet("background-color: blue; color: white;")
        self.non_linear_button.setStyleSheet("background-color: red; color: white;")

        self.rr_intervals = rr_intervals

        try:
            current_partition = Partitions.find_partition_by_name(self.dropdown_name.currentText())[self.dropdown_index.currentIndex()]
            from gui.viewer import PALMS
            current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
            current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)
        except Exception as e:
            return


        rr_intervals = rr_intervals[current_start:current_end]
        
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading results")
        loading_box.setText("Loading results...")
        loading_box.show()
        self.stacked_widget.setCurrentWidget(self.non_linear_widget)
        rr_intervals = rr_intervals[rr_intervals != 0]

        detrend = self.settings["nonlinear_detrending"]
        if detrend:
            rr_intervals = self.get_stationary_rr(rr_intervals)

        try:

            

            # delete previous components in the time layout
            layout = self.non_linear_widget.layout()  # Assuming 'widget' is your QWidget
            while layout.count():
                item = layout.takeAt(0)
                widget_to_remove = item.widget()
                if widget_to_remove:
                    widget_to_remove.setParent(None)
                else:
                    sublayout = item.layout()
                    while sublayout.count():
                        subitem = sublayout.takeAt(0)
                        subwidget = subitem.widget()
                        if subwidget:
                            subwidget.setParent(None)
                    sublayout.setParent(None)

            # delete previous graphs

            first_results = nl.poincare(rr_intervals, show=False)
            second_results = nl.dfa(rr_intervals, show=False, short=[self.settings["n1_min"], self.settings["n1_max"]], long=[self.settings["n2_min"], self.settings["n2_max"]])
                
            first_figure = first_results['poincare_plot']
            second_figure = second_results['dfa_plot']

            first_canvas = FigureCanvas(first_figure)
            first_figure.subplots_adjust(bottom=0.2)
            self.non_linear_layout.addWidget(first_canvas, 0)

            second_canvas = FigureCanvas(second_figure)
            second_figure.subplots_adjust(bottom=0.2)
            self.non_linear_layout.addWidget(second_canvas, 1)
            

        except Exception as e:
            error_message = "An error has occurred!"
            QMessageBox.critical(None, "Error", str(e), QMessageBox.Ok)
            import traceback
            error_traceback = traceback.format_exc()
            print(error_traceback)

        loading_box.close()


    def export_nonlinear_results(self, rr_intervals):
        detrend = self.settings["nonlinear_detrending"]
        if detrend:
            rr_intervals = self.get_stationary_rr(rr_intervals)
        first_results = nl.poincare(rr_intervals, show=False)
        second_results = nl.dfa(rr_intervals, show=False, short=[self.settings["n1_min"], self.settings["n1_max"]], long=[self.settings["n2_min"], self.settings["n2_max"]])
        samp_en = nl.sample_entropy(rr_intervals, dim=self.settings["embedding_dimension"], tolerance=self.settings["tolerance"])
        ap_en = nl.approximate_entropy(rr_intervals, dim=self.settings["embedding_dimension"], tolerance=self.settings["tolerance"])

        sd1 = round(first_results['sd1'], 3)
        sd2 = round(first_results['sd2'], 3)
        sd_ratio = round(first_results['sd_ratio'], 3)

        apen = round(ap_en['apen'], 3)
        sampen = round(samp_en['sampen'], 3)

        dfa1 = round(second_results['dfa_alpha1'], 3)
        dfa2 = round(second_results['dfa_alpha2'], 3)

        return sd1, sd2, sd_ratio, apen, sampen, dfa1, dfa2
    

    def set_varying_results(self, rr_intervals):

        if Partitions.all_names() == []:
            return

        # activate button
        self.current_active_result = 5
        for button in [self.home_domain_button, self.time_domain_button, self.frequency_domain_button, self.non_linear_button, self.time_varying_button, self.sports_button]:
            button.setStyleSheet("background-color: blue; color: white;")
        self.time_varying_button.setStyleSheet("background-color: red; color: white;")
        
        self.rr_intervals = rr_intervals
        try: 
            window_size = int(self.window_size_value.text())
            overlap_percentage = int(self.sliding_window_size_value.text())
            sliding_window_size = window_size - (window_size*overlap_percentage/100)
            minimum_effective_data = int(self.minimum_effective_data_value.text())
        except:
            from utils.utils_gui import Dialog
            Dialog().warningMessage('Choose the data in numbers')
            return

        if window_size < 120:
            from utils.utils_gui import Dialog
            Dialog().warningMessage('The window size must be of at least 120 seconds')
            return
        
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading results")
        loading_box.setText("Loading results...")
        loading_box.show()
        self.stacked_widget.setCurrentWidget(self.varying_domain_widget)
        rr_intervals = rr_intervals[rr_intervals != 0]

        # Get the current key
        current_key = self.varying_analysis_type.currentText()

        # Get the value corresponding to the key from JSON data
        value = self.varying_keys.get(current_key, None)

        # Call the varying function with the value
        window = f't{window_size}'
        first_result = results_tools.time_varying(rr_intervals, parameter=value, window=window, sliding_window=sliding_window_size, minimum_effective_data=minimum_effective_data, show=False)
        # add first graph
        first_figure = first_result["time_varying_%s" % value]
        first_figure.subplots_adjust(bottom=0.2)
        first_canvas = FigureCanvas(first_figure)

        # delete just the last component in the varying layout, which is the graph
        if (self.varying_domain_widget.layout().count() == 2):
            # Remove the last widget from the layout
            last_widget_index = self.varying_domain_layout.count() - 1
           
            last_widget_item = self.varying_domain_layout.itemAt(last_widget_index)
            last_widget = last_widget_item.widget()
            self.varying_domain_layout.removeWidget(last_widget)
            
            last_widget.deleteLater()
        
        # add widget
        scroll_area = QScrollArea()
        scroll_area.setWidget(first_canvas)
        self.varying_domain_layout.addWidget(scroll_area, 1)

        loading_box.close()


    def set_sports_results(self, rr_intervals):

        if Partitions.all_names() == []:
            return

        self.current_active_result = 6
        for button in [self.home_domain_button, self.time_domain_button, self.frequency_domain_button, self.non_linear_button, self.time_varying_button, self.sports_button]:
            button.setStyleSheet("background-color: blue; color: white;")
        self.sports_button.setStyleSheet("background-color: red; color: white;")

        for i in reversed(range(self.sports_layout.count())):
            item = self.sports_layout.itemAt(i)

            if isinstance(item.widget(), QCheckBox) and item.widget() in [self.cardiorespiratory_button, self.trimp_button, self.metabolic_button, self.heart_rate_recovery_button]:
                continue  # Skip option buttons
            else:
                self.sports_layout.removeItem(item)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()

        try: 
            current_partition = Partitions.find_partition_by_name(self.dropdown_name.currentText())[self.dropdown_index.currentIndex()]
            from gui.viewer import PALMS
            current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
            current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)
        except Exception as e:
            return

        import copy

        self.rr_intervals = copy.deepcopy(rr_intervals)

        current_rr_intervals = copy.deepcopy(rr_intervals[current_start:current_end])
        
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading results")
        loading_box.setText("Loading results...")
        loading_box.show()
        self.stacked_widget.setCurrentWidget(self.sports_widget)
        rr_intervals = copy.deepcopy(rr_intervals[rr_intervals != 0])
        current_rr_intervals = copy.deepcopy(current_rr_intervals[current_rr_intervals != 0])

        rr_detrended = self.get_stationary_rr(rr_intervals)
        current_rr_detrended = self.get_stationary_rr(current_rr_intervals)



        if self.cardiorespiratory_button.isChecked():
            hr_intervals = 60 / rr_intervals
            extended_arr = np.pad(hr_intervals, (10, 10), mode='edge')
            transformed_values = np.array([np.median(extended_arr[max(i - 10, 0):i + 10 + 1]) for i in range(len(hr_intervals))])

            respiratory_rate = self.estimate_respiratory_rate(transformed_values, PALMS.get().FREQUENCY)

            max_hr = round(max(transformed_values))
            hr_50 = round(max_hr*0.5)
            hr_60 = round(max_hr*0.6)
            hr_70 = round(max_hr*0.7)
            hr_80 = round(max_hr*0.8)
            hr_90 = round(max_hr*0.9)

            # Calculate time for each sample
            from gui import PALMS
            fig2, ax2 = plt.subplots(figsize=(2, 3))
            ORIGINAL_DATETIME = PALMS.get().ORIGINAL_DATETIME
            import datetime as dt
            if ORIGINAL_DATETIME:
                from dateutil import parser
                from dateutil.relativedelta import relativedelta
                current_result = np.insert(time_values, 0, 0)
                dt = parser.parse(PALMS.get().ORIGINAL_DATETIME)
                time_values = [dt + relativedelta(seconds=seconds) for seconds in current_result[:-1]]
                ax2.set_xlabel('Time [d  HH:MM:SS]')
            else:
                time_values = np.cumsum(rr_intervals)
                if time_values[-1] <= 60:
                    ax2.set_xlabel('Time [s]')
		        # Set x-axis format to MM:SS if the duration of the signal > 60s and <= 1h
                elif 60 < time_values[-1] <= 3600:
                    ax2.set_xlabel('Time [MM:SS]')
                    formatter = mpl.ticker.FuncFormatter(lambda ms, x: str(dt.timedelta(seconds=ms))[2:])
                    ax2.xaxis.set_major_formatter(formatter)	
                else:
                    ax2.set_xlabel('Time [HH:MM:SS]')
                    formatter = mpl.ticker.FuncFormatter(lambda ms, x: str(dt.timedelta(seconds=ms)))
                    ax2.xaxis.set_major_formatter(formatter)

            # Plot the last segment with the remaining color
            ax2.plot(time_values, transformed_values, color="black")

            # Define intervals and colors
            intervals = [0, hr_50, hr_60, hr_70, hr_80, hr_90, max_hr]
            colors = ["darkblue", "darkblue", "lightblue", "yellow", "orange", "red"]

            import matplotlib.patches as patches
            # Add colored rectangles for each interval
            for i in range(len(intervals) - 1):
                rect = patches.Rectangle((min(time_values), intervals[i]), max(time_values) - min(time_values), intervals[i+1] - intervals[i], color=colors[i], alpha=0.3)
                ax2.add_patch(rect)

            # Set limits for y-axis
            ax2.set_ylim([0, max(intervals)])
            # Adjust x-axis limits to remove white space
            ax2.set_xlim([min(time_values), max(time_values)])

            # Create a secondary y-axis for new_array
            # Convert rr_intervals to cumulative time (in seconds)
            cumulative_time = np.cumsum(rr_intervals)

            ax1 = ax2.twinx()
            from scipy.interpolate import interp1d
            original_indices = np.linspace(0, len(time_values) - 1, num=len(respiratory_rate), dtype=int)
            interp_func = interp1d(original_indices, respiratory_rate, kind='linear', fill_value="extrapolate")
            respiratory_rate_interpolated = interp_func(np.arange(len(time_values)))
            ax1.plot(time_values, respiratory_rate_interpolated, color="green")  # Choose a different color

            # Adjust the subplot's layout
            fig2.subplots_adjust(top=0.85)

            # Add title for the first data set outside the graph
            avg_value = np.mean(transformed_values)
            min_value = np.min(transformed_values)
            max_value = np.max(transformed_values)
            black_circle = plt.Circle((0.03, 1.08), 0.01, transform=ax1.transAxes, color="black", clip_on=False)
            fig2.add_artist(black_circle)
            title_text = "Heart Rate (beats/min)\nAvg {:.2f} | Min {:.2f} | Max {:.2f}".format(avg_value, min_value, max_value)
            ax2.text(0.05, 1.05, title_text, transform=ax2.transAxes, fontsize=8, verticalalignment='bottom', horizontalalignment='left')

            # Add circle and title for the second data set outside the graph
            avg_value = np.mean(respiratory_rate)
            min_value = np.min(respiratory_rate)
            max_value = np.max(respiratory_rate)
            black_circle = plt.Circle((0.73, 1.08), 0.01, transform=ax1.transAxes, color="black", clip_on=False)
            fig2.add_artist(black_circle)
            title_text = "Respiratory Rate (breaths/min)\nAvg {:.2f} | Min {:.2f} | Max {:.2f}".format(avg_value, min_value, max_value)
            ax1.text(0.75, 1.05, 'Respiratory Rate (breatsh/min)', transform=ax1.transAxes, fontsize=12, verticalalignment='bottom', horizontalalignment='left')

            # Add the second plot to the layout
            fig2.subplots_adjust(bottom=0.2)
            canvas2 = FigureCanvas(fig2)
            self.sports_layout.addWidget(canvas2, 0, 1, 6, 1)

            # Reduce figure size
            fig3, ax3 = plt.subplots(figsize=(2, 3))  # Adjusted to a smaller size
            values = [0, hr_50, hr_60, hr_70, hr_80, hr_90, max_hr]
            colors = ["darkblue", "darkblue", "lightblue", "yellow", "orange", "red"]
            intensity_labels = ["INACTIVE", "VERY LIGHT", "LIGHT", "MODERATE", "HARD", "MAXIMUM"] 

            # Maximum bar width
            max_bar_width = 4.5
            label_width = 1
            graph_center = max_bar_width / 2  # Middle of the graph

            # Draw bars
            import datetime as dtime
            measurement_date_start = PALMS.get().FIRST_DATETIME
            measurement_date_start = measurement_date_start.replace('--', ' ').strip()
            measurement_date_end = PALMS.get().LAST_DATETIME
            measurement_date_end = measurement_date_end.replace('--', ' ').strip()
            time_duration = dtime.datetime.strptime(measurement_date_end, "%d %H:%M:%S") - dtime.datetime.strptime(measurement_date_start, "%d %H:%M:%S")
            for i, value in enumerate(values[:-1]):
                upper_bound = values[i + 1]
                percentage = self.calculate_percentage_in_interval(transformed_values, value, upper_bound)
                current_time_duration = time_duration * (percentage / 100)
                time_formatted = self.format_time(current_time_duration)

                # Draw the full length of the bar in reduced intensity
                ax3.barh(i, max_bar_width, left=label_width, color="gray", edgecolor='none', alpha=0.3)

                # Overlay with full color up to the percentage length
                percentage_length = (max_bar_width - label_width) * (percentage / 100)
                ax3.barh(i, percentage_length, left=label_width, color=colors[i], edgecolor='none', alpha=0.5)

                # Draw the left segment of the bar with full color
                ax3.barh(i, label_width, color=colors[i], edgecolor='none')

                # Add labels and text
                ax3.text(label_width / 2, i, intensity_labels[i], va='center', ha='center', color='black', fontsize=8)
                ax3.text(graph_center, i, f'{percentage:.1f}%', va='center', ha='center', color='black')
                ax3.text(max_bar_width - 0.1, i, time_formatted, va='center', ha='right', color='black')

            # Draw a vertical line at the 0% mark
            ax3.axvline(x=label_width, color='black', linestyle='--')

            # Adjust y-ticks to appear between bars
            tick_positions = [i - 0.5 for i in range(len(values))]
            ax3.set_yticks(tick_positions)

            # Add 0% and 100% labels for the percentage part
            ax3.set_xticks([])
            ax3.text(label_width, -1, '0%', va='center', ha='center')
            ax3.text(max_bar_width, -1, '100%', va='center', ha='center')

            # Set y-tick labels to represent values between bars
            ax3.set_yticklabels(values[:])

            ax3.set_title('Heart Rate (HR)', pad=10, fontsize=10)
            ax3.set_xlim(0, 4.5)

            fig3.subplots_adjust(top=0.85, left=0.15, right=0.95, bottom=0.15)
            fig3.tight_layout()

            canvas3 = FigureCanvas(fig3)
            self.sports_layout.addWidget(canvas3, 0, 2, 5, 1)

            # Reduce figure size
            fig4, ax4 = plt.subplots(figsize=(1, 8))  # Adjusted to a smaller size
            values = [0, 21, 32]
            colors = ["darkblue", "yellow", "orange"]
            intensity_labels = ["LIGHT", "MODERATE", "HARD"] 

            # Maximum bar width
            max_bar_width = 4.5
            label_width = 1
            graph_center = max_bar_width / 2  # Middle of the graph

            # Draw bars
            import datetime as dtime
            measurement_date_start = PALMS.get().FIRST_DATETIME
            measurement_date_start = measurement_date_start.replace('--', ' ').strip()
            measurement_date_end = PALMS.get().LAST_DATETIME
            measurement_date_end = measurement_date_end.replace('--', ' ').strip()
            time_duration = dtime.datetime.strptime(measurement_date_end, "%d %H:%M:%S") - dtime.datetime.strptime(measurement_date_start, "%d %H:%M:%S")
            for i, value in enumerate(values[:-1]):
                upper_bound = values[i + 1]
                percentage = self.calculate_percentage_in_interval(transformed_values, value, upper_bound)
                current_time_duration = time_duration * (percentage / 100)
                time_formatted = self.format_time(current_time_duration)

                # Draw the full length of the bar in reduced intensity
                ax4.barh(i, max_bar_width, left=label_width, color="gray", edgecolor='none', alpha=0.3)

                # Overlay with full color up to the percentage length
                percentage_length = (max_bar_width - label_width) * (percentage / 100)
                ax4.barh(i, percentage_length, left=label_width, color=colors[i], edgecolor='none', alpha=0.5)

                # Draw the left segment of the bar with full color
                ax4.barh(i, label_width, color=colors[i], edgecolor='none')

                # Add labels and text
                ax4.text(label_width / 2, i, intensity_labels[i], va='center', ha='center', color='black', fontsize=8)
                ax4.text(graph_center, i, f'{percentage:.1f}%', va='center', ha='center', color='black')
                ax4.text(max_bar_width - 0.1, i, time_formatted, va='center', ha='right', color='black')

            # Draw a vertical line at the 0% mark
            ax4.axvline(x=label_width, color='black', linestyle='--')

            # Adjust y-ticks to appear between bars
            tick_positions = [i - 0.5 for i in range(len(values))]
            ax4.set_yticks(tick_positions)

            # Add 0% and 100% labels for the percentage part
            ax4.set_xticks([])
            ax4.text(label_width, -1, '0%', va='center', ha='center')
            ax4.text(max_bar_width, -1, '100%', va='center', ha='center')

            # Set y-tick labels to represent values between bars
            ax4.set_yticklabels(values[:])

            ax4.set_title('Respiratory Rate (RESP)', pad=10, fontsize=10)
            ax4.set_xlim(0, 4.5)

            fig4.subplots_adjust(top=0.85, left=0.15, right=0.95, bottom=0.15)
            fig4.tight_layout()

            canvas4 = FigureCanvas(fig4)
            self.sports_layout.addWidget(canvas4, 5, 2, 2, 1)

        elif self.trimp_button.isChecked():
            hr_intervals = 60 / rr_intervals
            extended_arr = np.pad(hr_intervals, (10, 10), mode='edge')
            transformed_values = np.array([np.median(extended_arr[max(i - 10, 0):i + 10 + 1]) for i in range(len(hr_intervals))])

            T = np.cumsum(rr_intervals)[-1]/60       # Duration of exercise in minutes
            HR_rest = self.settings['hr_rest'] # Resting heart rate
            HR_max = self.settings['hr_max'] # Max heart rate
            # Generating an array of HR_ex values (10 random values for this example)
            HR_ex_array = transformed_values
            # Calculate ΔHR and TRIMP for each HR_ex value
            Delta_HR_array = (HR_ex_array - HR_rest) / (HR_max - HR_rest)
            if self.settings['sex'] == 1:
                TRIMP_array = Delta_HR_array * 0.64 * np.exp(1.92 * Delta_HR_array)
            else:
                TRIMP_array = Delta_HR_array * 0.86 * np.exp(1.67 * Delta_HR_array)

            # show trimp graph
            transformed_values = np.cumsum(TRIMP_array)
            # Calculate time for each sample
            from gui import PALMS
            fig2, ax2 = plt.subplots(figsize=(10, 6))
            ORIGINAL_DATETIME = PALMS.get().ORIGINAL_DATETIME
            import datetime as dt
            if ORIGINAL_DATETIME:
                from dateutil import parser
                from dateutil.relativedelta import relativedelta
                current_result = np.insert(time_values, 0, 0)
                dt = parser.parse(PALMS.get().ORIGINAL_DATETIME)
                time_values = [dt + relativedelta(seconds=seconds) for seconds in current_result[:-1]]
                ax2.set_xlabel('Time [d  HH:MM:SS]')
            else:
                time_values = np.cumsum(rr_intervals)
                if time_values[-1] <= 60:
                    ax2.set_xlabel('Time [s]')
		        # Set x-axis format to MM:SS if the duration of the signal > 60s and <= 1h
                elif 60 < time_values[-1] <= 3600:
                    ax2.set_xlabel('Time [MM:SS]')
                    formatter = mpl.ticker.FuncFormatter(lambda ms, x: str(dt.timedelta(seconds=ms))[2:])
                    ax2.xaxis.set_major_formatter(formatter)	
                else:
                    ax2.set_xlabel('Time [HH:MM:SS]')
                    formatter = mpl.ticker.FuncFormatter(lambda ms, x: str(dt.timedelta(seconds=ms)))
                    ax2.xaxis.set_major_formatter(formatter)

            # Plot the last segment with the remaining color
            ax2.plot(time_values, TRIMP_array, color="black")

            # Define intervals and colors
            intervals = [0, 0.2, 0.6, 1.3, 2.5, 4.5]
            colors = ["darkblue", "lightblue", "yellow", "orange", "red"]

            import matplotlib.patches as patches
            # Add colored rectangles for each interval
            for i in range(len(intervals) - 1):
                rect = patches.Rectangle((min(time_values), intervals[i]), max(time_values) - min(time_values), intervals[i+1] - intervals[i], color=colors[i], alpha=0.3)
                ax2.add_patch(rect)

            # Set limits for y-axis
            ax2.set_ylim([0, max(intervals)])
            # Adjust x-axis limits to remove white space
            ax2.set_xlim([min(time_values), max(time_values)])

            # Create a secondary y-axis for new_array
            # Convert rr_intervals to cumulative time (in seconds)
            cumulative_time = np.cumsum(rr_intervals)

            # Initialize variables
            minute_means = []
            start_index = 0
            current_minute = 1

            # Iterate over cumulative_time and calculate mean TRIMP values per minute
            for i, time in enumerate(cumulative_time):
                if time >= current_minute * 60:
                    # Calculate mean for the current minute segment
                    mean_TRIMP = np.mean(TRIMP_array[start_index:i])
                    minute_means.append(mean_TRIMP)

                    # Update for the next minute
                    start_index = i
                    current_minute += 1

            # Don't forget to include the last segment if needed
            if start_index < len(TRIMP_array):
                mean_TRIMP = np.mean(TRIMP_array[start_index:])
                minute_means.append(mean_TRIMP)

            # Resulting array of mean TRIMP values per minute
            minute_means = np.cumsum(minute_means)

            ax1 = ax2.twinx()
            from scipy.interpolate import interp1d
            original_indices = np.linspace(0, len(time_values) - 1, num=len(minute_means), dtype=int)
            interp_func = interp1d(original_indices, minute_means, kind='linear', fill_value="extrapolate")
            minute_means_interpolated = interp_func(np.arange(len(time_values)))
            ax1.plot(time_values, minute_means_interpolated, color="green")  # Choose a different color

            # Adjust the subplot's layout
            fig2.subplots_adjust(top=0.85)

            # Add title for the first data set outside the graph
            avg_value = np.mean(TRIMP_array)
            min_value = np.min(TRIMP_array)
            max_value = np.max(TRIMP_array)
            black_circle = plt.Circle((0.03, 1.08), 0.01, transform=ax1.transAxes, color="black", clip_on=False)
            fig2.add_artist(black_circle)
            title_text = "Training Intensity (TRIMP/min)\nAvg {:.2f} | Min {:.2f} | Max {:.2f}".format(avg_value, min_value, max_value)
            ax2.text(0.05, 1.05, title_text, transform=ax2.transAxes, fontsize=8, verticalalignment='bottom', horizontalalignment='left')

            # Add circle and title for the second data set outside the graph
            green_circle = plt.Circle((0.73, 1.08), 0.01, transform=ax1.transAxes, color="green", clip_on=False)
            fig2.add_artist(green_circle)
            ax1.text(0.75, 1.05, 'Training Load (TRIMP)', transform=ax1.transAxes, fontsize=12, verticalalignment='bottom', horizontalalignment='left')

            # Add the second plot to the layout
            fig2.subplots_adjust(bottom=0.2)
            canvas2 = FigureCanvas(fig2)
            self.sports_layout.addWidget(canvas2, 0, 1, 6, 1)

            # Reduce figure size
            fig3, ax3 = plt.subplots(figsize=(2, 3))  # Adjusted to a smaller size
            values = [0, 0.2, 0.6, 1.3, 2.5, 4.5]
            colors = ['darkblue', 'lightblue', 'yellow', 'orange', 'red']
            intensity_labels = ["VERY LIGHT", "LIGHT", "MODERATE", "HARD", "MAXIMUM"] 

            # Maximum bar width
            max_bar_width = 4.5
            label_width = 1
            graph_center = max_bar_width / 2  # Middle of the graph

            # Draw bars
            import datetime as dtime
            measurement_date_start = PALMS.get().FIRST_DATETIME
            measurement_date_start = measurement_date_start.replace('--', ' ').strip()
            measurement_date_end = PALMS.get().LAST_DATETIME
            measurement_date_end = measurement_date_end.replace('--', ' ').strip()
            time_duration = dtime.datetime.strptime(measurement_date_end, "%d %H:%M:%S") - dtime.datetime.strptime(measurement_date_start, "%d %H:%M:%S")
            for i, value in enumerate(values[:-1]):
                upper_bound = values[i + 1]
                percentage = self.calculate_percentage_in_interval(TRIMP_array, value, upper_bound)
                current_time_duration = time_duration * (percentage / 100)
                time_formatted = self.format_time(current_time_duration)

                # Draw the full length of the bar in reduced intensity
                ax3.barh(i, max_bar_width, left=label_width, color="gray", edgecolor='none', alpha=0.3)

                # Overlay with full color up to the percentage length
                percentage_length = (max_bar_width - label_width) * (percentage / 100)
                ax3.barh(i, percentage_length, left=label_width, color=colors[i], edgecolor='none', alpha=0.5)

                # Draw the left segment of the bar with full color
                ax3.barh(i, label_width, color=colors[i], edgecolor='none')

                # Add labels and text
                ax3.text(label_width / 2, i, intensity_labels[i], va='center', ha='center', color='black', fontsize=8)
                ax3.text(graph_center, i, f'{percentage:.1f}%', va='center', ha='center', color='black')
                ax3.text(max_bar_width - 0.1, i, time_formatted, va='center', ha='right', color='black')

            # Draw a vertical line at the 0% mark
            ax3.axvline(x=label_width, color='black', linestyle='--')

            # Adjust y-ticks to appear between bars
            tick_positions = [i - 0.5 for i in range(len(values))]
            ax3.set_yticks(tick_positions)

            # Add 0% and 100% labels for the percentage part
            ax3.set_xticks([])
            ax3.text(label_width, -1, '0%', va='center', ha='center')
            ax3.text(max_bar_width, -1, '100%', va='center', ha='center')

            # Set y-tick labels to represent values between bars
            ax3.set_yticklabels(values[:])

            ax3.set_title('Training intensity (TRIMP/min)', pad=10, fontsize=10)
            ax3.set_xlim(0, 4.5)

            fig3.subplots_adjust(top=0.85, left=0.15, right=0.95, bottom=0.15)
            fig3.tight_layout()

            canvas3 = FigureCanvas(fig3)
            self.sports_layout.addWidget(canvas3, 0, 2, 5, 1)

            fig4, (ax4, ax5) = plt.subplots(2, 1, figsize=(1, 3))  # Two horizontal bars

            # Data for the bars
            values_bar1 = [0, 15, 40, 80, 150, 270]
            values_bar2 = [0, 0.2, 0.6, 1.3, 2.5, 4.5]
            segment_length = 1  # Length of each segment
            number_in_bar1 = round(minute_means[-1], 3)
            number_in_bar2 = round(mean_TRIMP, 3)

            # Calculate positions for vertical lines
            position_in_bar1 = self.calculate_position(values_bar1, number_in_bar1)
            position_in_bar2 = self.calculate_position(values_bar2, number_in_bar2)

            # Function to draw segments and labels for a bar
            def draw_bar(ax, values, line_position):
                colors = ['darkblue', 'lightblue', 'yellow', 'orange', 'red']
                for i in range(len(values)):
                    segment_start = i * segment_length
                    segment_end = segment_start + segment_length
                    color_segment_end = min(segment_end, line_position)

                    # Draw colored part of the segment
                    if segment_start < line_position:
                        ax.barh(0, color_segment_end - segment_start, left=segment_start, color=colors[i], edgecolor='none')

                    # Draw gray part of the segment
                    if color_segment_end < segment_end:
                        ax.barh(0, segment_end - color_segment_end, left=color_segment_end, color='gray', edgecolor='none')

                    label_pos = segment_start + segment_length / 2
                    ax.text(label_pos-0.5, 0.4, f'{values[i]}', ha='center', va='bottom', fontsize=8)

            # Draw bars
            draw_bar(ax4, values_bar1, position_in_bar1)
            draw_bar(ax5, values_bar2, position_in_bar2)

            # Set x-ticks to show numbers outside the bars
            ax4.set_xticks(range(len(values_bar1)))
            ax5.set_xticks(range(len(values_bar2)))

            # Set titles and layout adjustments
            fig4.suptitle('Training load vs intensity', fontsize=10)
            ax4.set_yticks([])
            ax4.set_xticks([])
            ax5.set_yticks([])
            ax5.set_xticks([])
            ax4.set_xlim(0, len(values_bar1) - 1)
            ax5.set_xlim(0, len(values_bar2) - 1)
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])

            # Calculate positions for vertical lines and add text
            position_in_bar1 = self.calculate_position(values_bar1, number_in_bar1)
            ax4.axvline(x=position_in_bar1, color='r', linewidth=1)
            ax4.text(position_in_bar1, 0.05, f'{number_in_bar1}', ha='center', va='center', color='white', fontsize=8)

            position_in_bar2 = self.calculate_position(values_bar2, number_in_bar2)
            ax5.axvline(x=position_in_bar2, color='r', linewidth=1)
            ax5.text(position_in_bar2, 0.05, f'{number_in_bar2}', ha='center', va='center', color='white', fontsize=8)

            canvas4 = FigureCanvas(fig4)
            self.sports_layout.addWidget(canvas4, 5, 2, 1, 1)

        elif self.metabolic_button.isChecked():
            label = QLabel("Coming soon...")
            label.setAlignment(QtCore.Qt.AlignCenter)
            font = label.font()
            font.setPointSize(16)  # Set the desired font size
            label.setFont(font)
            self.sports_layout.addWidget(label, 3, 1, 2, 1)

        elif self.heart_rate_recovery_button.isChecked():
            label = QLabel("Coming soon...")
            label.setAlignment(QtCore.Qt.AlignCenter)
            font = label.font()
            font.setPointSize(16)  # Set the desired font size
            label.setFont(font)
            self.sports_layout.addWidget(label, 3, 1, 2, 1)

        loading_box.close()

    # Function to calculate the exact position of the vertical line
    def calculate_position(self, values, number):
        segment_length = 1
        for i in range(len(values) - 1):
            if values[i] <= number <= values[i + 1]:
                # Interpolate within the segment
                segment_start = i * segment_length
                segment_end = (i + 1) * segment_length
                relative_position = (number - values[i]) / (values[i + 1] - values[i])
                return segment_start + (relative_position * segment_length)
        return 0  # Default case if number not in range

    def calculate_percentage_in_interval(self, array, lower_bound, upper_bound):
        count = sum(lower_bound <= x < upper_bound for x in array)
        return (count / len(array)) * 100

    def format_time(self, td):
        total_seconds = int(td.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f'{hours:02d}:{minutes:02d}:{seconds:02d}'

    def get_stationary_rr(self, previous_rr):

        detrended_rr = previous_rr

        if (self.settings['detrending_method'] == 1): # smoothn priors
            regularization = self.settings['smoothing_parameter']
            N = len(previous_rr)
            identity = np.eye(N)
            B = np.dot(np.ones((N, 1)), np.array([[1, -2, 1]]))
            D_2 = spd.dia_matrix((B.T, [0, 1, 2]), shape=(N - 2, N)) 
            inv = np.linalg.inv(identity + regularization**2 * D_2.T @ D_2)
            z_stat = ((identity - inv)) @ previous_rr
            trend = np.squeeze(np.asarray(previous_rr - z_stat))
            detrended_rr = previous_rr - trend

        elif (self.settings['detrending_method'] == 2):
            x = np.arange(len(previous_rr))
            coefficients = np.polyfit(x, previous_rr, 1)
            trend = np.polyval(coefficients, x)
            detrended_rr = previous_rr - trend

        elif (self.settings['detrending_method'] == 3):
            x = np.arange(len(previous_rr))
            coefficients = np.polyfit(x, previous_rr, 2)
            trend = np.polyval(coefficients, x)
            detrended_rr = previous_rr - trend

        elif (self.settings['detrending_method'] == 4):
            x = np.arange(len(previous_rr))
            coefficients = np.polyfit(x, previous_rr, 3)
            trend = np.polyval(coefficients, x)
            detrended_rr = previous_rr - trend

        return detrended_rr
    

    def bandpass_filter(self, data, lowcut, highcut, fs, order=5):
        from scipy.signal import butter, filtfilt

        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(order, [low, high], btype='band')
        y = filtfilt(b, a, data)
        return y

    def estimate_respiratory_rate(self, hr, fs):

        # Calculate period in sec, based on peak to peak difference and make sure
        # that rate has the same number of elements as peaks (important for
        # interpolation later) by prepending the mean of all periods.
        from gui import PALMS
        from logic.databases.DatabaseHandler import Database
        db = Database.get()
        ecg = db.tracks["ecg_filt"].get_value()
        # Desired length
        array_length = len(PALMS.get().ECG_DATA)

        # Original indices
        x_original = np.linspace(0, len(hr) - 1, len(hr))

        # New indices for the interpolated array
        x_new = np.linspace(0, len(hr) - 1, array_length)

        # Create the interpolating function
        interpolator = scipy.interpolate.PchipInterpolator(x_original, hr)

        # Interpolate to the new length
        hr_interpolated = interpolator(x_new)

        import neurokit2 as nk
        # resp signal
        order = 6
        lowcut = 0.1
        highcut = 0.35
        freqs, filter_type = _signal_filter_sanitize(lowcut=lowcut, highcut=highcut, sampling_rate=fs)
        sos = scipy.signal.butter(order, freqs, btype=filter_type, output="sos", fs=fs)
        rsp_cleaned = scipy.signal.sosfiltfilt(sos, hr_interpolated)

        nk.signal_plot(rsp_cleaned, sampling_rate=fs) # Visualize

        # resp frequency
        df, peaks_dict = nk.rsp_peaks(rsp_cleaned) 
        rsp_rate = nk.rsp_rate(rsp_cleaned, peaks_dict, sampling_rate=fs)

        return rsp_rate
  
def _signal_filter_sanitize(lowcut=None, highcut=None, sampling_rate=1000, normalize=False):

    # Sanity checks
    if lowcut is not None or highcut is not None:
        if sampling_rate <= 2 * np.nanmax(np.array([lowcut, highcut], dtype=np.float64)):
            pass

    # Replace 0 by none
    if lowcut is not None and lowcut == 0:
        lowcut = None
    if highcut is not None and highcut == 0:
        highcut = None

    # Format
    if lowcut is not None and highcut is not None:
        if lowcut > highcut:
            filter_type = "bandstop"
        else:
            filter_type = "bandpass"
        # pass frequencies in order of lowest to highest to the scipy filter
        freqs = list(np.sort([lowcut, highcut]))
    elif lowcut is not None:
        freqs = [lowcut]
        filter_type = "highpass"
    elif highcut is not None:
        freqs = [highcut]
        filter_type = "lowpass"

    # Normalize frequency to Nyquist Frequency (Fs/2).
    # However, no need to normalize if `fs` argument is provided to the scipy filter
    if normalize is True:
        freqs = np.array(freqs) / (sampling_rate / 2)

    return freqs, filter_type