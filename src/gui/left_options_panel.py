from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtWidgets import QPushButton, QCheckBox, QApplication, QStackedWidget, QMessageBox, QFileDialog
from functools import partial
import bisect
from PyQt5.QtCore import qWarning
import numpy as np
from gui.sample_options import SampleOptionsFrame, SampleOptionsPanel
from gui.results_panel import ResultsPanel
import datetime as dtime
from pathlib import Path
from utils.utils_general import resource_path

from config import tooltips
from logic.operation_mode.partitioning import SinglePartition, Partitions
from logic.operation_mode.noise_partitioning import NoisePartition, NoisePartitions
from logic.operation_mode.rr_noise_partitioning import RRNoisePartition, RRNoisePartitions
from qtpy.QtCore import Slot, Signal
import os
from config import settings
import json
#from numba import jit


class LeftOptionsFrame(QtWidgets.QFrame):

    def __init__(self, main_window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setParent(main_window)
        self.application = main_window.application
        self.setContentsMargins(0, 0, 0, 0)
        #self.setFrameStyle(self.NoFrame)
        
        

        screen_rect = QApplication.instance().desktop().screenGeometry()
        width = screen_rect.width()
        self.original_width = width * 0.2

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
        self.leftOptionsPanel: LeftOptionsPanel = None
        self.dragStartPos = QtCore.QPoint()
        self.drag = None

        

    #def updateHeight(self):
    #    self.setFixedHeight(self.n)



class LeftOptionsPanel(QtWidgets.QWidget):

    def __init__(self, frame: LeftOptionsFrame):
        super().__init__()
        
        self.setParent(frame)

        main_layout = QtWidgets.QVBoxLayout()

        self.sample_names = []

        # Create the scroll area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # Create the widget to hold the frames
        scroll_contents = QtWidgets.QWidget()
        #scroll_contents.setParent(scroll_area)
        scroll_layout = QtWidgets.QVBoxLayout(scroll_contents)
        scroll_contents.setLayout(scroll_layout)

        

        # Set the scroll area contents
        scroll_area.setWidget(scroll_contents)


        # Load settings from JSON file
        with open(resource_path(Path('settings.json'))) as f:
            self.settings = json.load(f)
        

        # ----------------------FIRST BUTTONS---------------------------
        buttons_layout = QtWidgets.QHBoxLayout()

        buttons_widget = QtWidgets.QWidget()
        buttons_widget.setLayout(buttons_layout)

        # Button 1
        open_file_button = QPushButton()
        open_file_button.setFixedSize(50, 50)  # Set a fixed size for the icon buttons
        open_file_icon = QtGui.QIcon("config/icons/open_file.jpg")
        open_file_button.setIcon(open_file_icon)
        open_file_button.clicked.connect(self.open_new_file)
        buttons_layout.addWidget(open_file_button)

        # Button 2
        save_file_button = QPushButton()
        save_file_button.setFixedSize(50, 50)  # Set a fixed size for the icon buttons
        save_file_icon = QtGui.QIcon("config/icons/save_file.jpg")
        save_file_button.setIcon(save_file_icon)
        save_file_button.clicked.connect(self.save_file)
        buttons_layout.addWidget(save_file_button)

        # Button 3
        print_button = QPushButton()
        print_button.setFixedSize(50, 50)  # Set a fixed size for the icon buttons
        print_icon = QtGui.QIcon("config/icons/print.jpg")
        print_button.setIcon(print_icon)
        buttons_layout.addWidget(print_button)
        print_button.clicked.connect(self.append_results)

        # Button 4
        settings_button = QPushButton()
        settings_button.setFixedSize(50, 50)  # Set a fixed size for the icon buttons
        settings_icon = QtGui.QIcon("config/icons/settings.jpg")
        settings_button.setIcon(settings_icon)
        buttons_layout.addWidget(settings_button)
        settings_button.clicked.connect(self.open_settings)

        # Button 5
        information_button = QPushButton()
        information_button.setFixedSize(50, 50)  # Set a fixed size for the icon buttons
        information_icon = QtGui.QIcon("config/icons/information.jpg")
        information_button.setIcon(information_icon)
        information_button.clicked.connect(self.open_doc)
        buttons_layout.addWidget(information_button)

        # Add the first row layout to the main layout
        #main_layout.addWidget(buttons_widget)


        # ----------------FILE INFORMATION----------------------
        file_information_layout = QtWidgets.QVBoxLayout()

        file_information_widget = QtWidgets.QWidget()
        file_information_widget.setLayout(file_information_layout)

        # First row - Centered label
        file_information_label1 = QtWidgets.QLabel("File information")
        file_information_label1.setAlignment(QtCore.Qt.AlignCenter)
        file_information_layout.addWidget(file_information_label1)
        from gui import PALMS

        # Second row - File name
        filename = os.path.basename(PALMS.get().CURRENT_FILE)
        file_name = QtWidgets.QLabel(f"File name: {filename}")
        file_information_layout.addWidget(file_name)

        # Third row - File frequency
        file_frequency = QtWidgets.QLabel(f"Frequency (Hz): {PALMS.get().FREQUENCY}")
        file_information_layout.addWidget(file_frequency)

        # Fourth row - File length
        seconds_length = len(PALMS.get().ECG_DATA) / PALMS.get().FREQUENCY
        m, s = divmod(seconds_length, 60)
        h, m = divmod(m, 60)
        self.time_str = f"{int(h)}:{int(m)}:{int(s)}"
        file_length = QtWidgets.QLabel("File length (h:min:s): "+self.time_str)
        file_information_layout.addWidget(file_length)

        # frame
        file_information_frame = QtWidgets.QFrame()
        file_information_frame.setLayout(file_information_layout)
        file_information_frame.setFrameShape(QtWidgets.QFrame.Box)
        file_information_frame.setLineWidth(2)
        file_information_frame.setStyleSheet("QFrame { border-color: black; }")

        scroll_layout.layout().addWidget(file_information_frame)
        

        # ----------------NOISE DETECTION----------------------
        noise_detection_layout = QtWidgets.QVBoxLayout()

        noise_detection_widget = QtWidgets.QWidget()
        noise_detection_widget.setLayout(noise_detection_layout)
        #noise_detection_widget.setStyleSheet("background-color: white;")

        # First row - Centered label
        noise_title_layout = QtWidgets.QHBoxLayout()
        noise_title_widget = QtWidgets.QWidget()
        noise_title_widget.setLayout(noise_title_layout)
        noise_label1 = QtWidgets.QLabel("Noise detection")
        noise_label1.setAlignment(QtCore.Qt.AlignCenter)
        noise_title_layout.addWidget(noise_label1)
        self.noise_icon_label = QtWidgets.QLabel()
        noise_icon_path = "config/icons/information.jpg"
        noise_icon_pixmap = QtGui.QPixmap(noise_icon_path)
        noise_icon_pixmap = noise_icon_pixmap.scaled(*(20,20))
        self.noise_icon_label.setPixmap(noise_icon_pixmap)
        self.noise_icon_label.setToolTip(tooltips.noise_explanation)
        self.noise_icon_label.setAlignment(QtCore.Qt.AlignRight)
        noise_title_layout.addWidget(self.noise_icon_label)
        noise_detection_layout.addWidget(noise_title_widget)

        # Second row - Slider
        noise_slider_layout = QtWidgets.QHBoxLayout()
        noise_slider_widget = QtWidgets.QWidget()
        noise_slider_widget.setLayout(noise_slider_layout)

        #noise_label2_left = QtWidgets.QLabel("Detection level: ")
        #noise_label2_left.setAlignment(QtCore.Qt.AlignLeft)
        self.noise_level = QtWidgets.QComboBox()
        self.noise_level.addItem("Basic")
        self.noise_level.addItem("Very low")
        self.noise_level.addItem("Low")
        self.noise_level.addItem("Medium")
        self.noise_level.addItem("High")
        self.noise_level.addItem("Custom (set in preferences)")
        self.noise_level.wheelEvent = lambda event: None
        self.noise_level.setCurrentIndex(self.settings['noise_detection_level'])
        #noise_settings_button = QPushButton()
        #noise_settings_button.setFixedSize(20, 20)  # Set a fixed size for the icon buttons
        #noise_settings_icon = QtGui.QIcon("config/icons/settings.jpg")
        #noise_settings_button.setIcon(noise_settings_icon)
        #noise_settings_button.clicked.connect(self.open_settings)
        #noise_slider_layout.addWidget(noise_label2_left)
        noise_slider_layout.addWidget(self.noise_level)
        #noise_slider_layout.addWidget(noise_settings_button)
        noise_detection_layout.addWidget(noise_slider_widget)

        # Third row - Buttons
        #noise_buttons_layout = QtWidgets.QHBoxLayout()
        #noise_buttons_widget = QtWidgets.QWidget()
        #noise_buttons_widget.setLayout(noise_buttons_layout)

        #self.noise_button_mark = QPushButton("Mark noise")
        #self.noise_button_mark.setStyleSheet("background-color: blue; color: white;")
        #noise_buttons_layout.addWidget(self.noise_button_mark)
        #noise_detection_layout.addWidget(noise_buttons_widget)

        self.noise_level.currentIndexChanged.connect(self.detectNoise)

        # Fourth row - Smaller label
        self.noise_text_label = QtWidgets.QLabel("0 intervals detected (0 % of signal)")
        noise_font = self.noise_text_label.font()
        noise_font.setPointSize(8)
        self.noise_text_label.setFont(noise_font)
        self.noise_text_label.setAlignment(QtCore.Qt.AlignCenter)
        noise_detection_layout.addWidget(self.noise_text_label)

        # frame
        noise_detection_frame = QtWidgets.QFrame()
        noise_detection_frame.setLayout(noise_detection_layout)
        noise_detection_frame.setFrameShape(QtWidgets.QFrame.Box)
        noise_detection_frame.setLineWidth(2)
        noise_detection_frame.setStyleSheet("QFrame { border-color: black; }")

        scroll_layout.layout().addWidget(noise_detection_frame)

        # --------------OUTLIERS BOX----------------------------------
        #outliers_box_layout = QtWidgets.QVBoxLayout()
        #outliers_box__widget = QtWidgets.QWidget()
        #beat_algorithm_frame = QtWidgets.QFrame()
        #beat_algorithm_frame.setLayout(beat_algorithm_layout)
        #beat_algorithm_frame.setFrameShape(QtWidgets.QFrame.Box)
        #beat_algorithm_frame.setLineWidth(2)
        #beat_algorithm_frame.setStyleSheet("QFrame { border-color: black; }")

        #scroll_layout.layout().addWidget(beat_algorithm_frame)

        # --------------BEAT CORRECTION ALGORITHM--------------------
        beat_algorithm_layout = QtWidgets.QVBoxLayout()

        beat_algorithm_widget = QtWidgets.QWidget()
        beat_algorithm_widget.setLayout(beat_algorithm_layout)

        # First row - Centered label
        beat_algorithm_title_layout = QtWidgets.QHBoxLayout()
        beat_algorithm_title_widget = QtWidgets.QWidget()
        beat_algorithm_title_widget.setLayout(beat_algorithm_title_layout)
        beat_algorithm_label1 = QtWidgets.QLabel("Outlier correction with algorithm")
        beat_algorithm_label1.setAlignment(QtCore.Qt.AlignCenter)
        beat_algorithm_title_layout.addWidget(beat_algorithm_label1)
        self.algorithm_icon_label = QtWidgets.QLabel()
        algorithm_icon_path = "config/icons/information.jpg"
        algorithm_icon_pixmap = QtGui.QPixmap(algorithm_icon_path)
        algorithm_icon_pixmap = algorithm_icon_pixmap.scaled(*(20,20))
        self.algorithm_icon_label.setPixmap(algorithm_icon_pixmap)
        self.algorithm_icon_label.setToolTip(tooltips.outliers_algorithm_explanation)
        self.algorithm_icon_label.setAlignment(QtCore.Qt.AlignRight)
        beat_algorithm_title_layout.addWidget(self.algorithm_icon_label)
        beat_algorithm_layout.addWidget(beat_algorithm_title_widget)

        # Second row - Slider
        beat_algorithm_slider_layout = QtWidgets.QHBoxLayout()
        beat_algorithm_slider_widget = QtWidgets.QWidget()
        beat_algorithm_slider_widget.setLayout(beat_algorithm_slider_layout)
        if self.settings['algorithm_option']:
            self.beat_algorithm_button = QPushButton("Do not apply")
            self.beat_algorithm_button.setStyleSheet("background-color: red; color: white;")
            self.algorithm_active = True
        else:
            self.beat_algorithm_button = QPushButton("Apply")
            self.beat_algorithm_button.setStyleSheet("background-color: blue; color: white;")
            self.algorithm_active = False
        beat_algorithm_slider_layout.addWidget(self.beat_algorithm_button)
        beat_algorithm_layout.addWidget(beat_algorithm_slider_widget)

        self.beat_algorithm_button.clicked.connect(lambda: self.outlier_decision_central(False, True))

        # Fourth row - Smaller label
        self.beat_algorithm_text_label = QtWidgets.QLabel("0 outliers corrected (0 % of beats)")
        beat_algorithm_font = self.beat_algorithm_text_label.font()
        beat_algorithm_font.setPointSize(8)
        self.beat_algorithm_text_label.setFont(beat_algorithm_font)
        self.beat_algorithm_text_label.setAlignment(QtCore.Qt.AlignCenter)
        beat_algorithm_layout.addWidget(self.beat_algorithm_text_label)

        # frame
        beat_algorithm_frame = QtWidgets.QFrame()
        beat_algorithm_frame.setLayout(beat_algorithm_layout)
        beat_algorithm_frame.setFrameShape(QtWidgets.QFrame.Box)
        beat_algorithm_frame.setLineWidth(2)
        beat_algorithm_frame.setStyleSheet("QFrame { border-color: black; }")

        scroll_layout.layout().addWidget(beat_algorithm_frame)

        # --------------BEAT CORRECTION THRESHOLD--------------------
        beat_threshold_layout = QtWidgets.QVBoxLayout()

        beat_threshold_widget = QtWidgets.QWidget()
        beat_threshold_widget.setLayout(beat_threshold_layout)

        # First row - Centered label
        beat_threshold_title_layout = QtWidgets.QHBoxLayout()
        beat_threshold_title_widget = QtWidgets.QWidget()
        beat_threshold_title_widget.setLayout(beat_threshold_title_layout)
        beat_threshold_label1 = QtWidgets.QLabel("Outlier correction with threshold")
        beat_threshold_label1.setAlignment(QtCore.Qt.AlignCenter)
        beat_threshold_title_layout.addWidget(beat_threshold_label1)
        self.threshold_icon_label = QtWidgets.QLabel()
        threshold_icon_path = "config/icons/information.jpg"
        threshold_icon_pixmap = QtGui.QPixmap(threshold_icon_path)
        threshold_icon_pixmap = threshold_icon_pixmap.scaled(*(20,20))
        self.threshold_icon_label.setPixmap(threshold_icon_pixmap)
        self.threshold_icon_label.setToolTip(tooltips.outliers_threshold_explanation)
        self.threshold_icon_label.setAlignment(QtCore.Qt.AlignRight)
        beat_threshold_title_layout.addWidget(self.threshold_icon_label)
        beat_threshold_layout.addWidget(beat_threshold_title_widget)

        # Second row - Slider
        beat_threshold_slider_layout = QtWidgets.QHBoxLayout()
        beat_threshold_slider_widget = QtWidgets.QWidget()
        beat_threshold_slider_widget.setLayout(beat_threshold_slider_layout)
        self.beat_threshold_level = QtWidgets.QComboBox()
        self.beat_threshold_level.addItem("None")
        self.beat_threshold_level.addItem("Very low correction (threshold = 0.45 s)")
        self.beat_threshold_level.addItem("Low correction (threshold = 0.35 s)")
        self.beat_threshold_level.addItem("Medium correction (threshold = 0.25 s)")
        self.beat_threshold_level.addItem("High correction (threshold = 0.15 s)")
        self.beat_threshold_level.addItem("Very high correction (threshold = 0.05 s)")
        self.beat_threshold_level.wheelEvent = lambda event: None
        self.beat_threshold_level.setCurrentIndex(self.settings['beat_correction_level'])
        #threshold_settings_button = QPushButton()
        #threshold_settings_button.setFixedSize(20, 20)  # Set a fixed size for the icon buttons
        #threshold_settings_icon = QtGui.QIcon("config/icons/settings.jpg")
        #threshold_settings_button.setIcon(threshold_settings_icon)
        #threshold_settings_button.clicked.connect(self.open_settings)
        beat_threshold_slider_layout.addWidget(self.beat_threshold_level)
        #beat_threshold_slider_layout.addWidget(threshold_settings_button)
        beat_threshold_layout.addWidget(beat_threshold_slider_widget)

        # Third row - Buttons
        #beat_threshold_buttons_layout = QtWidgets.QHBoxLayout()
        #beat_threshold_buttons_widget = QtWidgets.QWidget()
        #beat_threshold_buttons_widget.setLayout(beat_threshold_buttons_layout)

        #self.beat_threshold_button_mark = QPushButton("Mark")
        #self.beat_threshold_button_mark.setStyleSheet("background-color: blue; color: white;")
        #self.beat_threshold_button_correct = QPushButton("Automatic correction")
        #self.beat_threshold_button_correct.setStyleSheet("background-color: blue; color: white;")
        #beat_threshold_buttons_layout.addWidget(self.beat_threshold_button_mark)
        #beat_threshold_buttons_layout.addWidget(self.beat_threshold_button_correct)
        #beat_threshold_layout.addWidget(beat_threshold_buttons_widget)

        self.beat_threshold_level.currentIndexChanged.connect(lambda: self.outlier_decision_central(True))
        #self.beat_threshold_button_mark.clicked.connect(lambda: self.outlier_decision_central(False))
        #self.beat_threshold_button_correct.clicked.connect(lambda: self.outlier_decision_central(True))

        # Fourth row - Smaller label
        self.beat_threshold_text_label = QtWidgets.QLabel("0 outliers corrected (0 % of beats)")
        beat_threshold_font = self.beat_threshold_text_label.font()
        beat_threshold_font.setPointSize(8)
        self.beat_threshold_text_label.setFont(beat_threshold_font)
        self.beat_threshold_text_label.setAlignment(QtCore.Qt.AlignCenter)
        beat_threshold_layout.addWidget(self.beat_threshold_text_label)

        # frame
        beat_threshold_frame = QtWidgets.QFrame()
        beat_threshold_frame.setLayout(beat_threshold_layout)
        beat_threshold_frame.setFrameShape(QtWidgets.QFrame.Box)
        beat_threshold_frame.setLineWidth(2)
        beat_threshold_frame.setStyleSheet("QFrame { border-color: black; }")

        scroll_layout.layout().addWidget(beat_threshold_frame)

        # -----------------------SAMPLE SELECTION------------------------
        sample_selection_layout = QtWidgets.QVBoxLayout()
        sample_selection_widget = QtWidgets.QWidget()
        sample_selection_widget.setLayout(sample_selection_layout)

        # First row - Centered label
        sample_selection_label1 = QtWidgets.QLabel("Sample selection")
        sample_selection_label1.setAlignment(QtCore.Qt.AlignCenter)
        sample_selection_layout.addWidget(sample_selection_label1)

        # Second row - Selector and buttons
        sample_selection_selector_layout = QtWidgets.QHBoxLayout()
        sample_selection_selector_widget = QtWidgets.QWidget()
        sample_selection_selector_widget.setLayout(sample_selection_selector_layout)

        self.sample_selection_remove = QPushButton("Remove")
        self.sample_selection_remove.setStyleSheet("background-color: blue; color: white;")
        self.sample_selection_left = QPushButton("<")
        self.currentSelector = 1
        #self.sample_names.append("Sample 1")
        self.selector_label = QtWidgets.QLineEdit("Name")
        
        self.selector_label.textChanged.connect(lambda: self.updateSampleName(self.selector_label.text(), self.currentSelector, len(self.sample_names)))
        self.sample_selection_right = QPushButton(">")
        self.sample_selection_add = QPushButton("Add")
        self.sample_selection_add.setStyleSheet("background-color: blue; color: white;")
        sample_selection_selector_layout.addWidget(self.sample_selection_remove)
        sample_selection_selector_layout.addWidget(self.sample_selection_left)
        sample_selection_selector_layout.addWidget(self.selector_label)
        sample_selection_selector_layout.addWidget(self.sample_selection_right)
        sample_selection_selector_layout.addWidget(self.sample_selection_add)
        sample_selection_layout.addWidget(sample_selection_selector_widget)

        self.stacked_widget = QStackedWidget()
        self.sample_options_frame_list = []
        self.w_list = []
        self.createSampleOptions()
        self.showSampleOptions(self.currentSelector)

        sample_selection_layout.addWidget(self.stacked_widget)

        sample_selection_frame = QtWidgets.QFrame()
        sample_selection_frame.setLayout(sample_selection_layout)
        sample_selection_frame.setFrameShape(QtWidgets.QFrame.Box)
        sample_selection_frame.setLineWidth(2)
        sample_selection_frame.setStyleSheet("QFrame { border-color: black; }")

        scroll_layout.layout().addWidget(sample_selection_frame)
        
        main_layout.addWidget(scroll_area)

        # Connect the button signals to the slot functions
        self.sample_selection_left.setEnabled(False)
        self.sample_selection_right.setEnabled(False)
        self.sample_selection_remove.setStyleSheet("background-color: lightgray; color: gray;")
        self.sample_selection_left.clicked.connect(lambda: self.update_label(self.currentSelector, -1))
        self.sample_selection_right.clicked.connect(lambda: self.update_label(self.currentSelector, 1))

        self.sample_selection_add.clicked.connect(lambda: self.add_sample())
        self.sample_selection_remove.clicked.connect(lambda: self.delete_sample())

        frame.setLayout(main_layout)


    def open_settings(self):
        settings_window = settings.SettingsWindow()
        
        settings_window.show()

    #@jit
    def outlier_decision_central(self, threshold_correction, activate_algorithm = False):

        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading")
        loading_box.setText("Detecting outliers...")
        loading_box.show()

        from gui import PALMS

        use_threshold = False
        use_algorithm = False

        if activate_algorithm:
            if self.algorithm_active:
                self.algorithm_active = False
            else:
                self.algorithm_active = True

        # depending on current selector of algorithm and threshold, decide what previous outliers to delete
        if threshold_correction: # last update is threshold, so no need to modify algorithm
            # reset text and selector 
            self.beat_threshold_text_label.setText("0 outliers corrected (0 % of beats)")

            if (self.beat_threshold_level.currentIndex() != 0): # update threshold outliers
                for previous_threshold_outlier in PALMS.get().threshold_outliers:
                    PALMS.get().singleUpdateRR(PALMS.get().from_time_to_closest_sample(previous_threshold_outlier), 3, False)
                PALMS.get().threshold_outliers = np.array([], dtype="int32")
                PALMS.get().viewer.getOutliersDisplayPanel().threshold_outliers = np.array([])
                use_threshold = True
            else: # just delete
                for previous_threshold_outlier in PALMS.get().threshold_outliers:
                    PALMS.get().singleUpdateRR(PALMS.get().from_time_to_closest_sample(previous_threshold_outlier), 3, False)
                PALMS.get().threshold_outliers = np.array([], dtype="int32")
                PALMS.get().viewer.getOutliersDisplayPanel().threshold_outliers = np.array([])
                PALMS.get().threshold_outliers = np.array([], dtype="int32")
            PALMS.get().viewer.getOutliersDisplayPanel().initializeNoise()
                
        else: # algorithm is last change, so always reset everything
            
            from logic.operation_mode import annotation
            from logic.databases.DatabaseHandler import Database
            

            for previous_add_outlier in PALMS.get().algorithm_outliers.get("add", np.array([],dtype="int32")): # previous added now is deleted
                PALMS.get().singleUpdateRR(PALMS.get().from_time_to_closest_sample(previous_add_outlier), 1, False)
            for previous_delete_outlier in PALMS.get().algorithm_outliers.get("delete", np.array([],dtype="int32")): # previous deleted now is added
                PALMS.get().singleUpdateRR(PALMS.get().from_time_to_closest_sample(previous_delete_outlier), 0, False)
            for previous_add_interpolation_outlier in PALMS.get().algorithm_outliers.get("interpolate", np.array([],dtype="int32")): # previous added interpolation now is deleted
                PALMS.get().singleUpdateRR(PALMS.get().from_time_to_closest_sample(previous_add_interpolation_outlier), 3, False)
            PALMS.get().algorithm_outliers = {}
            PALMS.get().algorithm_outliers["interpolate"] = np.array([],dtype="int32")
            PALMS.get().algorithm_outliers["add"] = np.array([],dtype="int32")
            PALMS.get().algorithm_outliers["delete"] = np.array([],dtype="int32")
            PALMS.get().viewer.getOutliersDisplayPanel().algorithm_outliers = np.array([],dtype="int32")

            for previous_threshold_outlier in PALMS.get().threshold_outliers:
                PALMS.get().singleUpdateRR(PALMS.get().from_time_to_closest_sample(previous_threshold_outlier), 3, False)
            PALMS.get().threshold_outliers = np.array([],dtype="int32")
            PALMS.get().viewer.getOutliersDisplayPanel().threshold_outliers = np.array([],dtype="int32")

            # also reset outliers texts
            self.beat_threshold_text_label.setText("0 outliers corrected (0 % of beats)")
            self.beat_algorithm_text_label.setText("0 outliers corrected (0 % of beats)")

            # reset annotations and rr values to original
            Database.get()._set_annotation_from_idx('rpeak', PALMS.get().original_annotations)
            PALMS.get().rr_intervals = PALMS.get().original_fiducials
            PALMS.get().fiducials = PALMS.get().original_rr

            # decide if activate algorithm or cancel it depending on last state
            if self.algorithm_active: # activate
                self.beat_algorithm_button.setStyleSheet("background-color: red; color: white;")
                self.algorithm_active = True
                self.beat_algorithm_button.setText("Cancel")
                use_algorithm = True

            else: # cancel
                self.beat_algorithm_button.setStyleSheet("background-color: blue; color: white;")
                self.algorithm_active = False
                self.beat_algorithm_button.setText("Apply")

            # also check if need to use threshold
            if (self.beat_threshold_level.currentIndex() != 0): # update threshold outliers
                use_threshold = True


        if use_algorithm: # automatic algorithm
            new_outliers = self.outlier_decision_algorithm(False, True)
            

        if use_threshold:
            threshold = 0
            window_size = 0
            if (self.beat_threshold_level.currentIndex() == 1):
                threshold = 0.45
                window_size = 10
            if (self.beat_threshold_level.currentIndex() == 2):
                threshold = 0.35
                window_size = 10
            if (self.beat_threshold_level.currentIndex() == 3):
                threshold = 0.25
                window_size = 10
            if (self.beat_threshold_level.currentIndex() == 4):
                threshold = 0.15
                window_size = 10
            if (self.beat_threshold_level.currentIndex() == 5):
                threshold = 0.05
                window_size = 10

            new_outliers = self.outlier_threshold(threshold, window_size, False, True)
            PALMS.get().viewer.getOutliersDisplayPanel().threshold_outliers = new_outliers

            if threshold_correction or (use_threshold is True and use_algorithm is False):
                # update selector
                PALMS.get().viewer.getOutliersDisplayPanel().selector_option.setCurrentIndex(2)
                PALMS.get().viewer.getOutliersDisplayPanel().switchSelectorOption()

        #PALMS.get().updateRR(True)
        PALMS.get().createNewRRGraph()

        loading_box.close()
            

    def add_sample(self):
        if (Partitions.find_partition_by_name(self.selector_label.text()) == []):
            if " " not in self.selector_label.text():
                self.w_list[self.currentSelector-1].add_sample(self.selector_label.text())
                self.sample_names.append(self.selector_label.text())
            
                from gui.results_panel import ResultsPanel
                ResultsPanel.update_name_combobox()
            else:
                QMessageBox.critical(None, "Error", "There cannot be spaces in the sample name", QMessageBox.Ok)
        else:
            QMessageBox.critical(None, "Error", "There is a sample with that name", QMessageBox.Ok)

    def load_sample(self, name):
        self.createSampleOptions()
        self.showSampleOptions(self.currentSelector)
        self.sample_names.append(name)
        self.w_list[self.currentSelector-1].disableOptions()
            
        from gui.results_panel import ResultsPanel
        ResultsPanel.update_name_combobox()


    def createSampleOptions(self):
        
        options_frame = SampleOptionsFrame(main_window=self)
        w = SampleOptionsPanel(frame=options_frame)
        options_frame.layout.addWidget(w)
        options_frame.sampleOptionsPanel = w
        
        self.sample_options_frame_list.append(options_frame)
        self.w_list.append(w)
        self.stacked_widget.addWidget(options_frame)


    def showSampleOptions(self, current_selector):
        self.stacked_widget.setCurrentWidget(self.sample_options_frame_list[current_selector-1])


    def update_label(self, current_value, value):
        new_value = current_value + value
        
        if (new_value >= 1):

            if (value == -1 or len(self.sample_names) >= self.currentSelector):
                
                self.currentSelector = new_value

                previous_name = self.selector_label.text()

                if (value == -1 or len(self.sample_names) >= (new_value)): # go to existing sample
                    
                    # delete always enabled
                    self.sample_selection_remove.setStyleSheet("background-color: blue; color: white;")
                    
                    self.selector_label.setText(self.sample_names[self.currentSelector-1])
                    self.showSampleOptions(self.currentSelector)
                    
                    new_name = self.sample_names[self.currentSelector-1]
                    
                    Partitions.hide_all_partitions_by_name(previous_name)
                    Partitions.unhide_all_partitions_by_name(new_name)

                    # right selector always disabled
                    self.sample_selection_add.setStyleSheet("background-color: lightgray; color: gray;")
                    self.sample_selection_right.setEnabled(True)

                else: # new sample
                    Partitions.hide_all_partitions_by_name(previous_name)
                    self.selector_label.setText("Name")
                    self.createSampleOptions()
                    self.showSampleOptions(self.currentSelector)

                    # delete always disabled
                    self.sample_selection_remove.setStyleSheet("background-color: lightgray; color: gray;")

                    # right selector always enabled
                    self.sample_selection_add.setStyleSheet("background-color: blue; color: white;")
                    self.sample_selection_right.setEnabled(False)

            # if other sample before, enable left
            if (new_value != 1): # going to sample which is not last
                self.sample_selection_left.setEnabled(True)
            else:
                self.sample_selection_left.setEnabled(False)



    def updateSampleName(self, new_name, current_selector, samples_length):
        if (samples_length > current_selector):
            previous_name = self.sample_names[current_selector-1]

            Partitions.change_partition_name(previous_name, new_name)
            
            from gui.results_panel import ResultsPanel
            ResultsPanel.update_name_combobox()

            self.sample_names[current_selector-1] = new_name


    def delete_sample(self):
        if (Partitions.find_partition_by_name(self.selector_label.text()) != []):
            self.sample_options_frame_list.pop(self.currentSelector-1)
            self.w_list.pop(self.currentSelector-1)

            Partitions.delete_by_name(self.sample_names[self.currentSelector-1])

            self.sample_names.pop(self.currentSelector-1)
            
            if (self.sample_names == []):
                self.createSampleOptions()
                self.currentSelector = 1
                #self.sample_names.append("Sample 1")
                self.showSampleOptions(self.currentSelector)
                self.selector_label.setText("Name")

                self.sample_selection_remove.setStyleSheet("background-color: lightgray; color: gray;")
                self.sample_selection_add.setStyleSheet("background-color: blue; color: white;")
                self.sample_selection_right.setEnabled(False)
                self.sample_selection_left.setEnabled(False)

            else:
                self.currentSelector = self.currentSelector-1
                if (self.currentSelector == 0):
                    self.currentSelector = 1
                self.showSampleOptions(self.currentSelector)
                self.selector_label.setText(self.sample_names[self.currentSelector-1])
                Partitions.unhide_all_partitions_by_name(self.sample_names[self.currentSelector-1])

                self.sample_selection_remove.setStyleSheet("background-color: blue; color: white;")
                self.sample_selection_add.setStyleSheet("background-color: lightgray; color: gray;")

        else:
            QMessageBox.critical(None, "Error", "The sample has not been created yet", QMessageBox.Ok)


    def createNoiseInterval(self, start, end):
        from gui.viewer import PALMS

        if (RRNoisePartitions.find_partition_by_point(start) is not None):
            qWarning('Choose different place or delete existing region')
        else:
            if PALMS.get().RR_ONLY is False:
                p = NoisePartition("", start=start, end=end)
                PALMS.get().viewer.selectedDisplayPanel.plot_area.main_vb.addItem(p)
                PALMS.get().viewer.selectedDisplayPanel.plot_area.main_vb.addItem(p.label)

            p_rr = RRNoisePartition("", start=start, end=end)
            PALMS.get().viewer.RRDisplayPanel.plot_area.main_vb.addItem(p_rr)
            PALMS.get().viewer.RRDisplayPanel.plot_area.main_vb.addItem(p_rr.label)

            new_end_index = PALMS.get().from_time_to_closest_sample(p_rr.end)
            new_start_index = PALMS.get().from_time_to_closest_sample(p_rr.start)
            
            end_index_to_insert = np.searchsorted(PALMS.get().START_INDEXES, new_end_index)
            PALMS.get().START_INDEXES = np.insert(PALMS.get().START_INDEXES, end_index_to_insert, new_end_index)
            start_index_to_insert = np.searchsorted(PALMS.get().END_INDEXES, new_start_index)
            PALMS.get().END_INDEXES = np.insert(PALMS.get().END_INDEXES, start_index_to_insert, new_start_index)

    def markNoise(self):
        from gui.viewer import PALMS
        PALMS.get().viewer.getOutliersDisplayPanel().selector_option.setCurrentIndex(0)
        PALMS.get().viewer.getOutliersDisplayPanel().switchSelectorOption()

    #@jit
    def detectNoise(self):
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading")
        loading_box.setText("Detecting noise...")
        loading_box.show()
        from gui import PALMS
        # delete all previous noises that are not missing regions
        if PALMS.get().RR_ONLY is False:
            noise_intervals = NoisePartitions.find_partitions_by_name("")
            for noise_interval in noise_intervals:
                noise_interval.region_deleted()
        else:
            noise_rr_intervals = RRNoisePartitions.find_partitions_by_name("")
            for noise_rr_interval in noise_rr_intervals:
                noise_rr_interval.region_deleted()

        
        PALMS.get().START_INDEXES = np.array([], dtype="int32")
        PALMS.get().END_INDEXES = np.array([], dtype="int32")
        
        if (self.noise_level.currentIndex() == 0):
            loading_box.close()
            # add missing and ecg noises
            PALMS.get().START_INDEXES = np.concatenate((PALMS.get().START_INDEXES, PALMS.get().START_ECG_INDEXES, PALMS.get().START_MISSING_INDEXES))
            PALMS.get().START_INDEXES = np.sort(PALMS.get().START_INDEXES)
            PALMS.get().END_INDEXES = np.concatenate((PALMS.get().END_INDEXES, PALMS.get().END_ECG_INDEXES, PALMS.get().END_MISSING_INDEXES))
            PALMS.get().END_INDEXES = np.sort(PALMS.get().END_INDEXES)
            
            return
        # Create and show the "Loading data" message box
        
        from gui.viewer import PALMS
        
        # for low noise:
        if (self.noise_level.currentIndex() == 1):
            noise_size_limit = 0.4
            noise_length_limit = 15
        elif (self.noise_level.currentIndex() == 2):
            noise_size_limit = 0.35
            noise_length_limit = 25
        elif (self.noise_level.currentIndex() == 3):
            noise_size_limit = 0.3
            noise_length_limit = 35
        elif (self.noise_level.currentIndex() == 4):
            noise_size_limit = 0.25
            noise_length_limit = 45
        elif (self.noise_level.currentIndex() == 5):
            noise_size_limit = self.settings["between_beats"]
            noise_length_limit = self.settings["minimum_noise"]
        else:
            loading_box.close()
            # add missing and ecg noises
            PALMS.get().START_INDEXES = np.concatenate((PALMS.get().START_INDEXES, PALMS.get().START_ECG_INDEXES, PALMS.get().START_MISSING_INDEXES))
            PALMS.get().START_INDEXES = np.sort(PALMS.get().START_INDEXES)
            PALMS.get().END_INDEXES = np.concatenate((PALMS.get().END_INDEXES, PALMS.get().END_ECG_INDEXES, PALMS.get().END_MISSING_INDEXES))
            PALMS.get().END_INDEXES = np.sort(PALMS.get().END_INDEXES)
            
            return
        
        minimum_noise_beats = 3

        rr_intervals = PALMS.get().original_fiducials

        # just missing partitions, not all noise
        noise_start_points = RRNoisePartitions.all_startpoints()
        noise_end_points = RRNoisePartitions.all_endpoints()

        # if there are noise segments, iterate through them. Otherwise start in 0 and end in last sample
        if (noise_start_points.size == 0):
            noise_end_samples = np.append(noise_end_points, 0)
            noise_start_samples = np.append(noise_start_points, len(PALMS.get().ECG_DATA)-1)

        else:
            # check if first part of the signal is good (add initial point) or noise (delete initial point)
            if (noise_start_points[0] != 0):
                noise_end_points = np.insert(noise_end_points, 0, 0)
            else:
                noise_start_points = np.delete(noise_start_points, 0)
        
            try:
                noise_start_samples = np.vectorize(PALMS.get().from_time_to_closest_sample)(np.array(noise_start_points))
            except:
                noise_start_samples = np.array([], dtype="int32")
            try:
                noise_end_samples = np.vectorize(PALMS.get().from_time_to_closest_sample)(np.array(noise_end_points))
            except:
                noise_end_samples = np.array([], dtype="int32")

            # same test for last part of the signal
            if (noise_end_samples[-1] != len(PALMS.get().ECG_DATA)):
                noise_start_samples = np.append(noise_start_samples, len(PALMS.get().ECG_DATA))
            else:
                noise_end_samples = np.delete(noise_end_samples, -1)

        if (self.noise_level.currentIndex() == 1):
            all_outliers = self.outlier_threshold(0.45, 10, True, False)
        elif (self.noise_level.currentIndex() == 2):
            all_outliers = self.outlier_threshold(0.35, 10, True, False)
        elif (self.noise_level.currentIndex() == 3):
            all_outliers = self.outlier_threshold(0.25, 10, True, False)
        elif (self.noise_level.currentIndex() == 4):
            all_outliers = self.outlier_threshold(0.15, 10, True, False)
        elif (self.noise_level.currentIndex() == 5):
            noise_outlier_level = self.settings["noise_outlier_level"]
            if (noise_outlier_level == 1):
                all_outliers = self.outlier_threshold(0.45, 10, True, False)
            elif (noise_outlier_level == 2):
                all_outliers = self.outlier_threshold(0.35, 10, True, False)
            elif (noise_outlier_level == 3):
                all_outliers = self.outlier_threshold(0.25, 10, True, False)
            elif (noise_outlier_level == 4):
                all_outliers = self.outlier_threshold(0.15, 10, True, False)
            elif (noise_outlier_level == 5):
                all_outliers = self.outlier_decision_algorithm(True, False)
            else:
                self.noise_text_label.setText("0 intervals detected (0 % of signal)")
                PALMS.get().viewer.getOutliersDisplayPanel().selector_option.setCurrentIndex(0)
                PALMS.get().viewer.getOutliersDisplayPanel().switchSelectorOption()
                loading_box.close()
                # add missing and ecg noises
                PALMS.get().START_INDEXES = np.concatenate((PALMS.get().START_INDEXES, PALMS.get().START_ECG_INDEXES, PALMS.get().START_MISSING_INDEXES))
                PALMS.get().START_INDEXES = np.sort(PALMS.get().START_INDEXES)
                PALMS.get().END_INDEXES = np.concatenate((PALMS.get().END_INDEXES, PALMS.get().END_ECG_INDEXES, PALMS.get().END_MISSING_INDEXES))
                PALMS.get().END_INDEXES = np.sort(PALMS.get().END_INDEXES)
                
                return
        else:
            self.noise_text_label.setText("0 intervals detected (0 % of signal)")
            PALMS.get().viewer.getOutliersDisplayPanel().selector_option.setCurrentIndex(0)
            PALMS.get().viewer.getOutliersDisplayPanel().switchSelectorOption()
            loading_box.close()
            # add missing and ecg noises
            PALMS.get().START_INDEXES = np.concatenate((PALMS.get().START_INDEXES, PALMS.get().START_ECG_INDEXES, PALMS.get().START_MISSING_INDEXES))
            PALMS.get().START_INDEXES = np.sort(PALMS.get().START_INDEXES)
            PALMS.get().END_INDEXES = np.concatenate((PALMS.get().END_INDEXES, PALMS.get().END_ECG_INDEXES, PALMS.get().END_MISSING_INDEXES))
            PALMS.get().END_INDEXES = np.sort(PALMS.get().END_INDEXES)
            
            return

        if (len(all_outliers) == 0): # if no outliers, do not continue
            self.noise_text_label.setText("0 intervals detected (0 % of signal)")
            PALMS.get().viewer.getOutliersDisplayPanel().selector_option.setCurrentIndex(0)
            PALMS.get().viewer.getOutliersDisplayPanel().switchSelectorOption()
            loading_box.close()
            # add missing and ecg noises
            PALMS.get().START_INDEXES = np.concatenate((PALMS.get().START_INDEXES, PALMS.get().START_ECG_INDEXES, PALMS.get().START_MISSING_INDEXES))
            PALMS.get().START_INDEXES = np.sort(PALMS.get().START_INDEXES)
            PALMS.get().END_INDEXES = np.concatenate((PALMS.get().END_INDEXES, PALMS.get().END_ECG_INDEXES, PALMS.get().END_MISSING_INDEXES))
            PALMS.get().END_INDEXES = np.sort(PALMS.get().END_INDEXES)
            
            return
        
        all_outliers = np.array(all_outliers)
        all_outliers = np.unique(all_outliers)
        all_outliers = np.sort(all_outliers)

        all_samples = np.vectorize(PALMS.get().from_time_to_closest_sample)(np.array(all_outliers))
        all_samples = np.sort(all_samples)

        from logic.operation_mode import annotation
        annotations = PALMS.get().original_annotations
        annotations = np.array(annotations) # points in which there is peak
        annotations = np.sort(annotations)
        last_peak_sample = round(annotations[-1])

        noise_length = 0 # in time
        noise_count = 0

        # loop from end to start
        for new_end_sample, new_start_sample in zip(noise_end_samples, noise_start_samples): 

            # i need to get the times of the outliers and get the ones in this interval
            current_outliers = all_outliers[(all_outliers < new_start_sample) & (all_outliers > new_end_sample)]

            # same for outlier samples (i can use same indexes as before)
            current_samples = all_samples[(all_outliers < new_start_sample) & (all_outliers > new_end_sample)]


            current_outliers = np.array(current_outliers)
            current_outliers = np.append(current_outliers, PALMS.get().from_sample_to_time(last_peak_sample))
            #current_outliers = current_outliers.astype(int)
            current_samples = np.array(current_samples)
            current_samples = np.append(current_samples, last_peak_sample)
            current_samples = current_samples.astype(int)
            
            new_start_noise, new_end_noise = LeftOptionsPanel.get_noise_loop(current_outliers, current_samples, annotations, noise_length_limit, last_peak_sample, minimum_noise_beats, rr_intervals, noise_size_limit, new_start_sample)

            
            # after algorithm, whe start noise and end filled
            for new_start, new_end in zip(new_start_noise, new_end_noise): 
                
                from logic.operation_mode.operation_mode import Modes, Mode

                mode = Modes.noise_partition.value
                Mode.switch_mode(Modes[mode]) # Modes has no influence on gui

                if PALMS.get().RR_ONLY is False:
                    p = NoisePartition("", start=new_start, end=new_end, click=False) # The partition goes from end to start, as it is the missing part
                    PALMS.get().viewer.selectedDisplayPanel.plot_area.main_vb.addItem(p)
                    PALMS.get().viewer.selectedDisplayPanel.plot_area.main_vb.addItem(p.label)
 
                p_rr = RRNoisePartition("", start=new_start, end=new_end, click=False) # The partition goes from end to start, as it is the missing part
                PALMS.get().viewer.RRDisplayPanel.plot_area.main_vb.addItem(p_rr)
                PALMS.get().viewer.RRDisplayPanel.plot_area.main_vb.addItem(p_rr.label)

                new_end_index = PALMS.get().from_time_to_closest_sample(p_rr.end)
                new_start_index = PALMS.get().from_time_to_closest_sample(p_rr.start)
            
                end_index_to_insert = np.searchsorted(PALMS.get().START_INDEXES, new_end_index)
                PALMS.get().START_INDEXES = np.insert(PALMS.get().START_INDEXES, end_index_to_insert, new_end_index)
                start_index_to_insert = np.searchsorted(PALMS.get().END_INDEXES, new_start_index)
                PALMS.get().END_INDEXES = np.insert(PALMS.get().END_INDEXES, start_index_to_insert, new_start_index)
            
                #mode = Modes.browse.value
                #Mode.switch_mode(Modes[mode]) # Modes has no influence on gui

                annotation.Annotation.get().updateFiducialsNoise()

        

        noise_start_points = RRNoisePartitions.all_startpoints_by_two_names("", "ecg")
        noise_end_points = RRNoisePartitions.all_endpoints_by_two_names("", "ecg")

        signal_length = PALMS.get().from_sample_to_time(len(PALMS.get().ECG_DATA)-1)
        for noise_start, noise_end in zip(noise_start_points, noise_end_points):
            noise_length += (noise_end - noise_start)
            noise_count += 1

        ratio_noise = round(100*noise_length/signal_length, 2)
        self.noise_text_label.setText(f"{noise_count} intervals detected ({ratio_noise} % of signal)")
        

        PALMS.get().viewer.getOutliersDisplayPanel().selector_option.setCurrentIndex(0)
        PALMS.get().viewer.getOutliersDisplayPanel().switchSelectorOption()


        loading_box.close()

    #@jit(nopython=True, cache=True)
    def get_noise_loop(current_outliers, current_samples, annotations, noise_length_limit, last_peak_sample, minimum_noise_beats, rr_intervals, noise_size_limit, new_start_sample):
        
        new_start_noise = np.empty(0, dtype=np.float64)
        new_end_noise = np.empty(0, dtype=np.float64)

        current_cluster = np.empty(0, dtype=np.float64)
        current_cluster_sample = np.empty(0, dtype=np.int32) 
        previous_sample = 0

        for i in range(len(current_outliers)):
            current_outlier = current_outliers[i]
            current_sample = current_samples[i]

            midle_annotations = annotations[(annotations > previous_sample) & (annotations <= current_sample)]

            if len(midle_annotations) < noise_length_limit:
                current_cluster = np.append(current_cluster, current_outlier)
                current_cluster_sample = np.append(current_cluster_sample, current_sample)

                if current_sample >= last_peak_sample:
                    if len(current_cluster) > minimum_noise_beats:
                        outliers_times = rr_intervals[current_cluster_sample]
                        outliers_length = np.sum(outliers_times)
                        total_times = rr_intervals[current_cluster_sample[0]:current_cluster_sample[-1]]
                        total_length = np.sum(total_times)
                        outliers_proportion = outliers_length / total_length

                        if outliers_proportion > noise_size_limit:
                            new_start_noise = np.append(new_start_noise, current_cluster[0])
                            new_end_noise = np.append(new_end_noise, new_start_sample)

                    current_cluster = np.empty(0, dtype=np.float64)
                    current_cluster_sample = np.empty(0, dtype=np.int32) 
                    current_cluster = np.append(current_cluster, current_outlier)
                    current_cluster_sample = np.append(current_cluster_sample, current_sample)

            else:
                if len(current_cluster) > minimum_noise_beats:
                    outliers_times = rr_intervals[current_cluster_sample]
                    outliers_length = np.sum(outliers_times)
                    total_times = rr_intervals[current_cluster_sample[0]:current_cluster_sample[-1]]
                    total_length = np.sum(total_times)
                    outliers_proportion = outliers_length / total_length

                    if outliers_proportion > noise_size_limit:
                        new_start_noise = np.append(new_start_noise, current_cluster[0])
                        new_end_noise = np.append(new_end_noise, current_cluster[-1])

                current_cluster = np.empty(0, dtype=np.float64)
                current_cluster_sample = np.empty(0, dtype=np.int32) 

            previous_sample = current_sample

        return new_start_noise, new_end_noise



    #@jit
    def outlier_decision_algorithm(self, useOriginal, updatePalms):
        # Create and show the "Loading data" message box
        from gui.viewer import PALMS

        if useOriginal:
            rr_intervals = PALMS.get().original_fiducials
        else:
            rr_intervals = PALMS.get().rr_intervals

        # algorithm acts on each non-noisy interval. From noise indexes, get them (seconds -> samples)
        noise_start_points = RRNoisePartitions.all_startpoints()
        noise_end_points = RRNoisePartitions.all_endpoints()

        # if there are noise segments, iterate through them. Otherwise start in 0 and end in last sample
        if (noise_start_points.size == 0):
            noise_end_samples = np.append(noise_end_points, 0)
            noise_start_samples = np.append(noise_start_points, len(PALMS.get().ECG_DATA)-1)

        else:
            # check if first part of the signal is good (add initial point) or noise (delete initial point)
            if (noise_start_points[0] != 0):
                noise_end_points = np.insert(noise_end_points, 0, 0)
            else:
                noise_start_points = np.delete(noise_start_points, 0)
        
            try:
                noise_start_samples = np.vectorize(PALMS.get().from_time_to_closest_sample)(np.array(noise_start_points))
            except:
                noise_start_samples = np.array([], dtype="int32")
            try:
                noise_end_samples = np.vectorize(PALMS.get().from_time_to_closest_sample)(np.array(noise_end_points))
            except:
                noise_end_samples = np.array([], dtype="int32")

            # same test for last part of the signal
            if (noise_end_samples[-1] != len(PALMS.get().ECG_DATA)):
                noise_start_samples = np.append(noise_start_samples, len(PALMS.get().ECG_DATA))
            else:
                noise_end_samples = np.delete(noise_end_samples, -1)


        # get previous annotations
        from logic.operation_mode import annotation
        from logic.operation_mode import annotation
        if useOriginal:
            annotations = PALMS.get().original_annotations
        else:
            annotations = [fiducial.annotation.idx for fiducial in annotation.AnnotationConfig.get().fiducials]
            annotations = np.array(annotations[0]) # points in which there is peak

        start_beat = 0

        long_short_beats = np.empty(0, dtype=np.int64)
        miss_beats = np.empty(0, dtype=np.int64)
        extra_beats = np.empty(0, dtype=np.int64)
        ectopic_beats = np.empty(0, dtype=np.int64)

        # loop from end to start
        previous_start = 0
        for new_end, new_start in zip(noise_end_samples, noise_start_samples): 
            
            if (new_end != 0):
                start_beat = len(annotations[annotations < new_end])-1

            rr_intervals_local = rr_intervals[int(new_end):int(new_start)]

            rr_intervals_values = rr_intervals_local[rr_intervals_local != 0]

            if rr_intervals_values.size == 0:
                continue
            
            current_extra_beats, current_miss_beats, current_ectopic_beats, current_long_short_beats = LeftOptionsPanel.algorithm_loop(rr_intervals_values, start_beat)
            extra_beats = np.concatenate((extra_beats, current_extra_beats))
            miss_beats = np.concatenate((miss_beats, current_miss_beats))
            ectopic_beats = np.concatenate((ectopic_beats, current_ectopic_beats))
            long_short_beats = np.concatenate((long_short_beats, current_long_short_beats))

            previous_start = new_start


        PALMS.get().algorithm_outliers = {}

        # dRR is the difference of r-intervals, so the difference of difference of beats
        # dRR is supposed to be of size (len(peaks)-1), so len(rr_intervals)
        # an outliers in dRR[i] means an outlier in peak[i+1]
        extra_beats = np.array(extra_beats)
        extra_beats = np.unique(extra_beats)
        miss_beats = np.array(miss_beats)
        miss_beats = np.unique(miss_beats)
        ectopic_beats = np.array(ectopic_beats)
        ectopic_beats = np.unique(ectopic_beats)
        long_short_beats = np.array(long_short_beats)
        long_short_beats = np.unique(long_short_beats)

        if updatePalms:

            for extra_beat in extra_beats: # in peak index
                if extra_beat in PALMS.get().algorithm_outliers.get("delete", np.array([],dtype="int32")):
                    continue
                # delete peak in (extra_beat+1)
                previous_beat = annotations[extra_beat+1]
                annotations = np.delete(annotations, (extra_beat+1))
                previous_values = PALMS.get().algorithm_outliers.get("delete", np.array([],dtype="int32"))
                beat_time = PALMS.get().from_sample_to_time(previous_beat)
                previous_values = np.append(previous_values, beat_time)
                PALMS.get().algorithm_outliers["delete"] = previous_values
                # delete value to miss and interpolated, as one less value on the rr_intervals (only values after outlier)
                extra_beats[extra_beats > extra_beat+1] -= 1
                miss_beats[miss_beats > extra_beat+1] -= 1
                ectopic_beats[ectopic_beats > extra_beat+1] -= 1
                long_short_beats[long_short_beats > extra_beat+1] -= 1
                PALMS.get().singleUpdateRR(previous_beat, 1, False)
                from logic.databases.DatabaseHandler import Database
                Database.get()._set_annotation_from_idx('rpeak', annotations)

            for miss_beat in miss_beats: # in peak index
                if miss_beat in PALMS.get().algorithm_outliers.get("delete", np.array([],dtype="int32")) or miss_beat in PALMS.get().algorithm_outliers.get("add", np.array([],dtype="int32")):
                    continue
                # add peak between (extra_beat), which is previous, and (extra_beat+1), which is current
                previous_annotation = annotations[miss_beat]
                current_annotation = annotations[miss_beat+1]
                new_annotation = int((previous_annotation+current_annotation)/2)
                annotations = np.insert(annotations, (miss_beat+1), new_annotation)
                previous_values = PALMS.get().algorithm_outliers.get("add", np.array([],dtype="int32"))
                beat_time = PALMS.get().from_sample_to_time(new_annotation)
                previous_values = np.append(previous_values, beat_time)
                PALMS.get().algorithm_outliers["add"] = previous_values
                # add value to miss interpolated, as one more value on the rr_intervals (only values after outlier)
                # no need to change miss, as outliers are stored as sample number
                miss_beats[miss_beats > miss_beat] += 1
                ectopic_beats[ectopic_beats > miss_beat] += 1
                long_short_beats[long_short_beats > miss_beat] += 1
                PALMS.get().singleUpdateRR(new_annotation, 0, False)
                from logic.databases.DatabaseHandler import Database
                Database.get()._set_annotation_from_idx('rpeak', annotations)

            for interpolated_beat in ectopic_beats:
                if interpolated_beat in PALMS.get().algorithm_outliers.get("delete", np.array([],dtype="int32")) or interpolated_beat in PALMS.get().algorithm_outliers.get("add", np.array([],dtype="int32")) or interpolated_beat in PALMS.get().algorithm_outliers.get("interpolate", np.array([],dtype="int32")):
                    continue
                beat_sample = annotations[interpolated_beat+1]
                beat_time = PALMS.get().from_sample_to_time(beat_sample)
                previous_values = PALMS.get().algorithm_outliers.get("interpolate", np.array([],dtype="int32"))
                previous_values = np.append(previous_values, beat_time)
                PALMS.get().algorithm_outliers["interpolate"] = previous_values
                PALMS.get().singleUpdateRR(beat_sample, 2, False)
                from logic.databases.DatabaseHandler import Database
                Database.get()._set_annotation_from_idx('rpeak', annotations)

        
            for long_short_beat in long_short_beats:
                if long_short_beat in PALMS.get().algorithm_outliers.get("delete", []) or long_short_beat in PALMS.get().algorithm_outliers.get("add", []) or long_short_beat in PALMS.get().algorithm_outliers.get("interpolate", []):
                    continue
                beat_sample = annotations[long_short_beat+1]
                beat_time = PALMS.get().from_sample_to_time(beat_sample)
                previous_values = PALMS.get().algorithm_outliers.get("interpolate", [])
                previous_values = np.append(previous_values, beat_time)
                PALMS.get().algorithm_outliers["interpolate"] = previous_values
                PALMS.get().singleUpdateRR(beat_sample, 2, False)
                from logic.databases.DatabaseHandler import Database
                Database.get()._set_annotation_from_idx('rpeak', annotations)
            
            outliers_number = len(miss_beats)+len(extra_beats)+len(ectopic_beats)+len(long_short_beats)
            total_beats = len(annotations)
            outliers_ratio = round(100*outliers_number/total_beats, 2)
            
            self.beat_algorithm_text_label.setText(f"{outliers_number} outliers corrected ({outliers_ratio} % of beats)")

            #PALMS.get().updateRR(True)

        all_outliers = np.concatenate((PALMS.get().algorithm_outliers.get("delete", []), PALMS.get().algorithm_outliers.get("add", []), PALMS.get().algorithm_outliers.get("interpolate", [])))
        all_outliers.sort()

        new_outliers = all_outliers

        PALMS.get().viewer.getOutliersDisplayPanel().algorithm_outliers = new_outliers
        PALMS.get().viewer.getOutliersDisplayPanel().selector_option.setCurrentIndex(1)
        PALMS.get().viewer.getOutliersDisplayPanel().switchSelectorOption()


        return new_outliers
    
    
    #@jit(nopython=True, cache=True)
    def algorithm_loop(rr_intervals_values, start_beat):

        long_short_beats = np.empty(0, dtype=np.int64)
        miss_beats = np.empty(0, dtype=np.int64)
        extra_beats = np.empty(0, dtype=np.int64)
        ectopic_beats = np.empty(0, dtype=np.int64)

        dRRs = np.diff(rr_intervals_values)
        dRRs = np.concatenate((dRRs[:0], np.array([0]), dRRs[0:]))
            

        # Window size
        window_size = 45
        threshold1 = np.empty(0, dtype=np.float64)
        alpha = 5.2
        dRR = np.empty(0, dtype=np.float64)

        # Iterate over each element in the array
        for i in range(len(dRRs)):
            # Calculate the indices for the window
            start_index = max(i - window_size, 0)
            end_index = min(i + window_size, len(dRRs)-1)
    
            # Extract the window of values
            window = dRRs[start_index:end_index]

            # Calculate the absolute values
            abs_window = np.abs(window)

            if len(abs_window)==0:
                continue
    
            # Calculate the quartile deviation
            qdeviation = np.percentile(abs_window, 75) - np.percentile(abs_window, 25)

            threshold1 = np.append(threshold1, alpha*qdeviation)

            dRR = np.append(dRR, dRRs[i]/(alpha*qdeviation))

        m_window_size = 5
        mRRs = np.empty(0, dtype=np.float64)
        medRR = np.empty(0, dtype=np.float64)

        for i in range(len(rr_intervals_values)):
            # mrr
            start_index = max(i - m_window_size, 0)
            end_index = min(i + m_window_size, len(rr_intervals_values)-1)

            window = rr_intervals_values[start_index:end_index]

            medRR = np.append(medRR, np.median(window))

            if ((rr_intervals_values[i] - np.median(window)) < 0):
                mRRs = np.append(mRRs, 2 * (rr_intervals_values[i] - np.median(window)))
            else:
                mRRs = np.append(mRRs, rr_intervals_values[i] - np.median(window))

        # Window size
        window_size = 45
        threshold2 = np.empty(0, dtype=np.float64)
        alpha = 5.2
        mRR = np.empty(0, dtype=np.float64)

        # Iterate over each element in the array
        for i in range(len(mRRs)):
            # Calculate the indices for the window
            start_index = max(i - window_size, 0)
            end_index = min(i + window_size, len(mRRs)-1)
    
            # Extract the window of values
            window = mRRs[start_index:end_index]

            # Calculate the absolute values
            abs_window = np.abs(window)

            if len(abs_window)==0:
                continue
    
            # Calculate the quartile deviation
            qdeviation = np.percentile(abs_window, 75) - np.percentile(abs_window, 25)

            threshold2 = np.append(threshold2, alpha*qdeviation)

            mRR = np.append(mRR, mRRs[i]/(alpha*qdeviation))


        s11 = dRR
        window_size = 1
        s12 = np.empty(0, dtype=np.float64)
        # Iterate over each element in the array
        for i in range(len(dRR)):
            # Calculate the indices for the window
            start_index = max(i - window_size, 0)
            end_index = min(i + window_size + 1, len(dRR)-1)

            if (dRR[i] > 0):
                s12 = np.append(s12, max(dRR[start_index], dRR[end_index]))
            else:
                s12 = np.append(s12, min(dRR[start_index], dRR[end_index]))


        # decision algorithm. 
        c1 = 0.13
        c2 = 0.17

        for i in range(len(dRR)):
            if (np.abs(dRR[i]) > 1):
                eq1 = ((s11[i] > 1) and (s12[i] < (-c1*s11[i] + c2)))
                eq2 = ((s11[i] < -1) and (s12[i] > (-c1*s11[i] - c2)))

                if (eq1 or eq2):
                    ectopic_beats = np.append(ectopic_beats, start_beat+i)
                    continue
            if (i < (len(dRR)-1)):
                if ((np.abs(dRR[i]) > 1) or (np.abs(mRR[i]) > 3)):
                    eq3 = ((np.sign(dRR[i])*dRR[i+1]) < -1)
                    eq4 = (np.abs(mRR[i]) > 3)
                    eq5 = False
                    if (i < (len(dRR)-2)):
                        eq5 = ((np.sign(dRR[i])*dRR[i+2]) < -1)
                    if (eq3 or eq4 or eq5):
                        eq6 = ((np.abs(rr_intervals_values[i]/2 - medRR[i])) < threshold2[i])
                        eq7 = ((np.abs(rr_intervals_values[i] + rr_intervals_values[i+1] - medRR[i]) < threshold2[i]))
                        if (eq6):
                            miss_beats = np.append(miss_beats, start_beat+i)
                        elif (eq7):
                            extra_beats = np.append(extra_beats, start_beat+i) # this and next
                        elif (eq5):
                            long_short_beats = np.append(long_short_beats, start_beat+i) # this and next
                        elif (eq3 or eq4):
                            long_short_beats = np.append(long_short_beats, start_beat+i)



        return extra_beats, miss_beats, ectopic_beats, long_short_beats


    #@jit
    def outlier_threshold(self, threshold, window_size, useOriginal, updatePalms):
        # Create and show the "Loading data" message box
        from gui import PALMS

        if useOriginal:
            rr_intervals = PALMS.get().original_fiducials
        else:
            rr_intervals = PALMS.get().rr_intervals

        # algorithm acts on each non-noisy interval. From noise indexes, get them (seconds -> samples)
        noise_start_points = RRNoisePartitions.all_startpoints()
        noise_end_points = RRNoisePartitions.all_endpoints()

        # if there are noise segments, iterate through them. Otherwise start in 0 and end in last sample
        if (noise_start_points.size == 0):
            noise_end_samples = np.append(noise_end_points, 0)
            noise_start_samples = np.append(noise_start_points, len(PALMS.get().ECG_DATA)-1)

        else:
            # check if first part of the signal is good (add initial point) or noise (delete initial point)
            if (noise_start_points[0] != 0):
                noise_end_points = np.insert(noise_end_points, 0, 0)
            else:
                noise_start_points = np.delete(noise_start_points, 0)
        
            try:
                noise_start_samples = np.vectorize(PALMS.get().from_time_to_closest_sample)(np.array(noise_start_points))
            except:
                noise_start_samples = np.array([], dtype="int32")
            try:
                noise_end_samples = np.vectorize(PALMS.get().from_time_to_closest_sample)(np.array(noise_end_points))
            except:
                noise_end_samples = np.array([], dtype="int32")

            # same test for last part of the signal
            if (noise_end_samples[-1] != len(PALMS.get().ECG_DATA)):
                noise_start_samples = np.append(noise_start_samples, len(PALMS.get().ECG_DATA))
            else:
                noise_end_samples = np.delete(noise_end_samples, -1)


        # get previous annotations
        from logic.operation_mode import annotation
        if useOriginal:
            annotations = PALMS.get().original_annotations
        else:
            annotations = [fiducial.annotation.idx for fiducial in annotation.AnnotationConfig.get().fiducials]
            annotations = np.array(annotations[0]) # points in which there is peak
        frequency = PALMS.get().FREQUENCY

        new_outliers = LeftOptionsPanel.threshold_loop(noise_end_samples, noise_start_samples, rr_intervals, window_size, threshold, annotations, frequency)
        

        for outlier in new_outliers:
            if updatePalms:
                PALMS.get().threshold_outliers = np.append(PALMS.get().threshold_outliers, outlier)
                PALMS.get().singleUpdateRR(PALMS.get().from_time_to_closest_sample(outlier), 2, False)

        if updatePalms:

            # update text
            outliers_number = len(new_outliers)
            total_beats = len(PALMS.get().original_annotations)
            outliers_ratio = round(100*outliers_number/total_beats, 2)

            self.beat_threshold_text_label.setText(f"{outliers_number} outliers corrected ({outliers_ratio} % of beats)")


        return new_outliers
    
    #@jit(nopython=True, cache=True)
    def threshold_loop(noise_end_samples, noise_start_samples, rr_intervals, window_size, threshold, annotations, frequency):
        threshold_outliers = np.empty(0, dtype=np.int64)
        # loop from end to start
        for new_end, new_start in zip(noise_end_samples, noise_start_samples): 

            start_beat = 0
            if (new_end != 0):
                start_beat = len(annotations[annotations < new_end])


            rr_intervals_local = rr_intervals[int(new_end):int(new_start)]

            rr_intervals_values = rr_intervals_local[rr_intervals_local != 0]
            

            # Iterate over each element in the array
            for i in range(len(rr_intervals_values)):
                # Calculate the indices for the window
                start_index = max(i - window_size, 0)
                end_index = min(i + window_size, len(rr_intervals_values)-1)
    
                # Extract the window of values
                window = rr_intervals_values[start_index:end_index]

                mean_rr = np.mean(window)

                if ((mean_rr < (rr_intervals_values[i] - threshold)) or (mean_rr > (rr_intervals_values[i] + threshold))):
                    threshold_outliers = np.append(threshold_outliers, i+start_beat)


        new_outliers = np.empty(0, dtype=np.float64)
        for outlier in threshold_outliers:
            outlier = min(outlier+1, len(annotations)-2)
            sample_index = int(annotations[outlier+1])
            new_outliers = np.append(new_outliers, sample_index/frequency)

        return new_outliers

    def mainExportResults(self):
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Exporting results")
        loading_box.setText("Exporting results...")
        loading_box.show()
        # Load settings from JSON file
        with open(resource_path(Path('settings.json'))) as f:
            self.settings = json.load(f)
        try:
            self.exportResults()
            loading_box.close()

        except Exception as e:
            loading_box.close()
            import traceback
            # Display an error message box
            error_message = "An error has occurred!"
            QMessageBox.critical(None, "Error", str(e), QMessageBox.Ok)
            error_traceback = traceback.format_exc()
            print(error_traceback)

    #@jit
    def exportResults(self):
        import csv
        from gui.viewer import PALMS

        if len(Partitions.all_startpoints()) == 0:
            error_message = "You need to select samples before exporting the results"
            QMessageBox.critical(None, "No samples", error_message, QMessageBox.Ok)
            return

        # Open the file dialog to choose the output file path
        output_file, _ = QtWidgets.QFileDialog.getSaveFileName(None, 'Save CSV', '', 'CSV Files (*.csv)')

        # ---------------------------SOFTWARE INFORMATION----------------------
        # define data
        current_time = dtime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            [f"HRV analysis results of {current_time}"],
            ["Program name"],
            ["Released on December 2023"],
            [""]
        ]
        # writing in csv
        if output_file:
           # Write the data to the CSV file
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)

        # ---------------------------FILE INFORMATION----------------------
        # define data
        file_name = PALMS.get().CURRENT_FILE
        measurement_date_start = PALMS.get().FIRST_DATETIME
        measurement_date_start = measurement_date_start.replace('--', ' ').strip()
        measurement_date_end = PALMS.get().LAST_DATETIME
        measurement_date_end = measurement_date_end.replace('--', ' ').strip()
        time_duration = dtime.datetime.strptime(measurement_date_end, "%d %H:%M:%S") - dtime.datetime.strptime(measurement_date_start, "%d %H:%M:%S")
        measurement_rate = PALMS.get().FREQUENCY
        rows = [
            [f"File name: {file_name}"],
            [f"Measurement date (start): {measurement_date_start}"],
            [f"Measurement date (end): {measurement_date_end}"],
            [f"Time duration (d h:min:s): {time_duration}"],
            [f"Measurement rate (hz): {measurement_rate}"],
            [""]
        ]
        # writing in csv
        if output_file:
           # Write the data to the CSV file
            with open(output_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)

        # ---------------------------PARAMETERS----------------------
        # define data
        samples_number = len(Partitions.all_startpoints())
        detrending_method_index = self.settings['detrending_method']
        if (detrending_method_index == 0):
            detrending_method = "None"
        if (detrending_method_index == 1):
            detrending_method = "Smoothn priors (lambda="+str(self.settings["smoothing_parameter"])+")"
        if (detrending_method_index == 2):
            detrending_method = "1st order Polynomial"
        if (detrending_method_index == 3):
            detrending_method = "2nd order Polynomial"
        if (detrending_method_index == 4):
            detrending_method = "3rd order Polynomial"

        hr_as_average_of = str(self.settings["average_hr"])+" beats"
        nnxx_threshold = str(self.settings["nnxx_threshold"])+" ms"
        vlf_min = PALMS.get().viewer.results_w.vlf_min.text()
        vlf_max = PALMS.get().viewer.results_w.vlf_max.text()
        lf_min = PALMS.get().viewer.results_w.lf_min.text()
        lf_max = PALMS.get().viewer.results_w.lf_max.text()
        hf_min = PALMS.get().viewer.results_w.hf_min.text()
        hf_max = PALMS.get().viewer.results_w.hf_max.text()
        interpolation_rate = "4 hz"
        spectrum_points = str(self.settings["spectrum_points"])+" points/Hz"
        if (self.settings["lomb_scargle"] == False):
            ma_order = self.settings["ma_order"]
        else:
            ma_order = "-"
        ar_model_order = self.settings["ar_order"]
        apply_detrending = self.settings["nonlinear_detrending"]
        entropy_dimension = self.settings["embedding_dimension"]
        entropy_tolerance = str(self.settings["tolerance"])+" x SD"
        dfa_short_term = str(self.settings["n1_min"])+"-"+str(self.settings["n1_max"])+" beats"
        dfa_long_term = str(self.settings["n2_min"])+"-"+str(self.settings["n2_max"])+" beats"
        rows = [
            ["Parameters"],
            [f"Number of samples: {samples_number}"],
            [f"Detrending method: {detrending_method}"],
            [f"Min/Max HR as average of: {hr_as_average_of}"],
            [f"Threshold for NNxx/pNNxx: {nnxx_threshold}"],
            ["Frequency bands"],
            [f"VLF: {vlf_min} - {vlf_max} Hz"],
            [f"LF: {lf_min} - {lf_max} Hz"],
            [f"HF: {hf_min} - {hf_max} Hz"],
            [f"Interpolation rate: {interpolation_rate}"],
            [f"Spectrum points: {spectrum_points}"],
            ["FFT spectrum options"],
            ["AR spectrum options"],
            [f"AR model order: {ar_model_order}"],
            [f"FFT moving average order: {ma_order}"],
            [f"Apply detrending for nonlinear analysis: {apply_detrending}"],
            [f"Entropy, embedding dimension: {entropy_dimension}"],
            [f"Entropy, tolerance: {entropy_tolerance}"],
            [f"DFA, short-term fluctuations: {dfa_short_term}"],
            [f"DFA, long-term fluctuations: {dfa_long_term}"],
            [""]
        ]
        # writing in csv
        if output_file:
           # Write the data to the CSV file
            with open(output_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)

        # ---------------------------RESULTS----------------------
        # 1) RR INTERVAL SAMPLES
        # define data
        sample_titles = []
        sample_titles.append("")
        sample_titles_results = []
        sample_titles_results.append("")
        sample_titles_spectrum = []
        sample_limits = []
        sample_limits.append("Sample limits (d--hh:mm:ss)")
        sample_analysis_type = "Single samples"
        beat_correction = "Automatic correction"
        beats_total = []
        beats_total.append("Beats total")
        beats_corrected = []
        beats_corrected.append("Beats corrected")
        beats_corrected_ratio = []
        beats_corrected_ratio.append("Beats corrected (%)")
        effective_data_length = []
        effective_data_length.append("Effective data length (s)")
        effective_data_length_ratio = []
        effective_data_length_ratio.append("Effective data length (ratio)")
        # 2) RESULTS OVERVIEW
        pns_index = []
        pns_index.append("PNS index")
        sns_index = []
        sns_index.append("SNS index")
        stress_index = []
        stress_index.append("Stress index")
        # 3) TIME-DOMAIN RESULTS
        mean_rr = []
        mean_rr.append("Mean RR (ms)")
        sdnn = []
        sdnn.append("SDNN (ms)")
        mean_hr = []
        mean_hr.append("Mean HR (beats/min)")
        sd_hr = []
        sd_hr.append("SD HR (beats/min)")
        min_hr = []
        min_hr.append("Mim HR (beats/min)")
        max_hr = []
        max_hr.append("Max HR (beats/min)")
        rmssd = []
        rmssd.append("RMSSD (ms)")
        nnxx = []
        nnxx.append("NNxx (beats)")
        pnnxx = []
        pnnxx.append("pNNxx (%)")
        sdnn_index = []
        sdnn_index.append("SDNN index (ms)")
        rr_tri_index = []
        rr_tri_index.append("RR tri index")
        tinn = []
        tinn.append("TINN (ms)")
        # 4) FREQUENCY-DOMAIN RESULTS
        frequency_domain_title = ["Frequency-Domain Results"]
        peak_frequencies_vlf = []
        peak_frequencies_vlf.append("VLF (Hz)")
        peak_frequencies_lf = []
        peak_frequencies_lf.append("LF (Hz)")
        peak_frequencies_hf = []
        peak_frequencies_hf.append("HF (Hz)")
        absolute_powers_vlf_ms2 = []
        absolute_powers_vlf_ms2.append("VLF (ms^2)")
        absolute_powers_lf_ms2 = []
        absolute_powers_lf_ms2.append("LF (ms^2)")
        absolute_powers_hf_ms2 = []
        absolute_powers_hf_ms2.append("HF (ms^2)")
        absolute_powers_vlf_log = []
        absolute_powers_vlf_log.append("VLF (log)")
        absolute_powers_lf_log = []
        absolute_powers_lf_log.append("LF (log)")
        absolute_powers_hf_log = []
        absolute_powers_hf_log.append("HF (log)")
        relative_powers_vlf = []
        relative_powers_vlf.append("VLF (%)")
        relative_powers_lf = []
        relative_powers_lf.append("LF (%)")
        relative_powers_hf = []
        relative_powers_hf.append("HF (%)")
        normalized_powers_lf = []
        normalized_powers_lf.append("LF (n.u.)")
        normalized_powers_hf = []
        normalized_powers_hf.append("HF (n.u.)")
        total_power = []
        total_power.append("Total power (ms^2)")
        lf_hf_ratio = []
        lf_hf_ratio.append("LF/HF ratio")
        # 5) NONLINEAR RESULTS
        sd1 = []
        sd1.append("SD1 (ms)")
        sd2 = []
        sd2.append("SD2 (ms)")
        sd1_2 = []
        sd1_2.append("SD2/SD1 ratio")
        approximate_entropy = []
        approximate_entropy.append("Approximate entropy (ApEn)")
        sample_entropy = []
        sample_entropy.append("Sample entropy (SampEn)")
        alpha1 = []
        alpha1.append("alpha 1")
        alpha2 = []
        alpha2.append("alpha 2")
        # 6) RR interval data
        rr_row1 = []
        rr_row2 = []
        rr_row_units = []
        peaks_columns = []
        rr_intervals_columns = []

        from gui.viewer import PALMS
        from datetime import timedelta
        from logic.operation_mode.annotation import AnnotationConfig
        rr_intervals = PALMS.get().rr_intervals

        # for each sample (name -> index), get all the results and append them to the corresponding array
        all_samples = Partitions.all_names()
        if PALMS.get().ORIGINAL_DATETIME != None:
            previous_rr_sum = PALMS.get().ORIGINAL_DATETIME
        else:
            previous_rr_sum = 0
        for sample_name in all_samples:
            sample_indices = Partitions.find_partition_by_name(sample_name)
            for i, sample_index in enumerate(sample_indices):

                current_partition = sample_index

                sample_titles.append(sample_name+" "+str(i+1))
                sample_titles_results.append(sample_name+" "+str(i+1))
                sample_titles_results.append("")
                sample_titles_spectrum.append(sample_name+" "+str(i+1))
                sample_titles_spectrum.append("")

                current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
                current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)

                rr_local = rr_intervals[current_start:current_end]   
                rr_local = rr_local[rr_local != 0]

                if len(rr_local) < 5:
                    continue

                # append sample limits
                first_time = PALMS.get().FIRST_DATETIME
                datetime_obj = dtime.datetime.strptime(first_time, "%d--%H:%M:%S")
                new_start = datetime_obj + timedelta(seconds=current_partition.start)
                current_start_date = new_start.strftime("%d--%H:%M:%S")
                new_end = datetime_obj + timedelta(seconds=current_partition.end)
                current_end_date = new_end.strftime("%d--%H:%M:%S")
                sample_limits.append(f"{current_start_date} - {current_end_date}")

                # how many annotations there are
                #a = AnnotationConfig.get()[0]
                #points_x, points_y = a.annotation.find_annotation_between_two_ts(current_partition.start, current_partition.end)
                annotations = rr_local
                beats_total.append(len(annotations))

                # how many outliers there are
                points_x = PALMS.get().viewer.selectedDisplayPanel.plot_area.find_outliers_between_two_ts(current_partition.start, current_partition.end)
                beats_corrected.append(len(points_x))

                # ratio of beats corrected
                current_beats_corrected_ratio = (100 * len(points_x)) / (len(annotations) + len(points_x))
                beats_corrected_ratio.append(current_beats_corrected_ratio)

                # outliers time
                outliers_times = len(points_x)*0.7
                non_outliers_times = np.sum(annotations)-outliers_times

                # effective data
                effective_data_length.append(non_outliers_times)
                effective_data_length_ratio.append(non_outliers_times/(outliers_times+non_outliers_times))

                

                # ------------TIME RESULTS---------------
                mean_rr_local, sdnn_local, mean_hr_local, sd_hr_local, min_hr_local, max_hr_local, rmssd_local, nnxx_local, pnnxx_local, rr_tri_index_local, tinn_local, stress_index_local, sdnn_index_local = ResultsPanel.get().export_time_results(rr_local)
                # general results
                pns_index.append("0")
                pns_index.append("")
                sns_index.append("0")
                sns_index.append("")
                stress_index.append(stress_index_local)
                stress_index.append("")
                mean_rr.append(mean_rr_local)
                mean_rr.append("")
                sdnn.append(sdnn_local)
                sdnn.append("")
                mean_hr.append(mean_hr_local)
                mean_hr.append("")
                sd_hr.append(sd_hr_local)
                sd_hr.append("")
                min_hr.append(min_hr_local)
                min_hr.append("")
                max_hr.append(max_hr_local)
                max_hr.append("")
                rmssd.append(rmssd_local)
                rmssd.append("")
                nnxx.append(nnxx_local)
                nnxx.append("")
                pnnxx.append(pnnxx_local)
                pnnxx.append("")
                sdnn_index.append(sdnn_index_local)
                sdnn_index.append("")
                rr_tri_index.append(rr_tri_index_local)
                rr_tri_index.append("")
                tinn.append(tinn_local)
                tinn.append("")

                # ------------FREQUENCY RESULTS-------------
                frequency_domain_title.append("FFT spectrum")
                frequency_domain_title.append("AR spectrum")
                vlf_peak_welch, lf_peak_welch, hf_peak_welch, vlf_absolute_power_ms2_welch, lf_absolute_power_ms2_welch, hf_absolute_power_ms2_welch, vlf_absolute_power_log_welch, lf_absolute_power_log_welch, hf_absolute_power_log_welch, vlf_relative_power_welch, lf_relative_power_welch, hf_relative_power_welch, lf_normalized_power_welch, hf_normalized_power_welch, total_power_welch, lf_hf_ratio_welch, vlf_peak_ar, lf_peak_ar, hf_peak_ar, vlf_absolute_power_ms2_ar, lf_absolute_power_ms2_ar, hf_absolute_power_ms2_ar, vlf_absolute_power_log_ar, lf_absolute_power_log_ar, hf_absolute_power_log_ar, vlf_relative_power_ar, lf_relative_power_ar, hf_relative_power_ar, lf_normalized_power_ar, hf_normalized_power_ar, total_power_ar, lf_hf_ratio_ar = ResultsPanel.get().export_frequency_results(rr_local)
                peak_frequencies_vlf.append(vlf_peak_welch)
                peak_frequencies_vlf.append(vlf_peak_ar)
                peak_frequencies_lf.append(lf_peak_welch)
                peak_frequencies_lf.append(lf_peak_ar)
                peak_frequencies_hf.append(hf_peak_welch)
                peak_frequencies_hf.append(hf_peak_ar)
                
                absolute_powers_vlf_ms2.append(vlf_absolute_power_ms2_welch)
                absolute_powers_vlf_ms2.append(vlf_absolute_power_ms2_ar)
                absolute_powers_lf_ms2.append(lf_absolute_power_ms2_welch)
                absolute_powers_lf_ms2.append(lf_absolute_power_ms2_ar)
                absolute_powers_hf_ms2.append(hf_absolute_power_ms2_welch)
                absolute_powers_hf_ms2.append(hf_absolute_power_ms2_ar)
                absolute_powers_vlf_log.append(vlf_absolute_power_log_welch)
                absolute_powers_vlf_log.append(vlf_absolute_power_log_ar)
                absolute_powers_lf_log.append(lf_absolute_power_log_welch)
                absolute_powers_lf_log.append(lf_absolute_power_log_ar)
                absolute_powers_hf_log.append(hf_absolute_power_log_welch)
                absolute_powers_hf_log.append(hf_absolute_power_log_ar)
            
                relative_powers_vlf.append(vlf_relative_power_welch)
                relative_powers_vlf.append(vlf_relative_power_ar)
                relative_powers_lf.append(lf_relative_power_welch)
                relative_powers_lf.append(lf_relative_power_ar)
                relative_powers_hf.append(hf_relative_power_welch)
                relative_powers_hf.append(hf_relative_power_ar)
            
                normalized_powers_lf.append(lf_normalized_power_welch)
                normalized_powers_lf.append(lf_normalized_power_ar)
                normalized_powers_hf.append(hf_normalized_power_welch)
                normalized_powers_hf.append(hf_normalized_power_ar)
                total_power.append(total_power_welch)
                total_power.append(total_power_ar)
                lf_hf_ratio.append(lf_hf_ratio_welch)
                lf_hf_ratio.append(lf_hf_ratio_ar)

                # ------------NON LINEAR RESULTS------------
                sd1_local, sd2_local, sd_ratio_local, apen_local, sampen_local, dfa1_local, dfa2_local = ResultsPanel.get().export_nonlinear_results(rr_local)
                
                sd1.append(sd1_local)
                sd1.append("")
                sd2.append(sd2_local)
                sd2.append("")
                sd1_2.append(sd_ratio_local)
                sd1_2.append("")

                approximate_entropy.append(apen_local)
                approximate_entropy.append("")
                sample_entropy.append(sampen_local)
                sample_entropy.append("")

                alpha1.append(dfa1_local)
                alpha1.append("")
                alpha2.append(dfa2_local)
                alpha2.append("")

                # RR values
                rr_row1.append("RR data")
                rr_row1.append("")

                rr_row2.append("Time")
                rr_row2.append("RR interval")

                rr_row_units.append("(s)")
                rr_row_units.append("(s)")

                # rr values start in row 110
                rr_intervals_local = rr_local 
                if PALMS.get().ORIGINAL_DATETIME != None:
                    rr_sum = np.cumsum(rr_intervals_local)
                    rr_sum = np.insert(rr_sum, 0, 0)

                    from dateutil import parser
                    from dateutil.relativedelta import relativedelta
                    dt = parser.parse(PALMS.get().ORIGINAL_DATETIME)
                    peaks_values_local = [dt + relativedelta(seconds=seconds) for seconds in rr_sum[:-1]]
                else:
                    peaks_values_local = previous_rr_sum + np.cumsum(rr_intervals_local)
                
                rr_intervals_columns.append(rr_intervals_local)
                
                peaks_columns.append(peaks_values_local)
                
                previous_rr_sum = peaks_values_local[-1]
                

        # all the results are stored in "rows"
        rows = [
            ["RR Interval Samples Selected for Analysis"],
            sample_titles,
            sample_limits,
            [f"Sample Analysis Type: {sample_analysis_type}"],
            [f"Beat correction: {beat_correction}"],
            beats_total,
            beats_corrected,
            beats_corrected_ratio,
            effective_data_length,
            effective_data_length_ratio,
            [""],
            [""],
            ["RESULTS FOR SINGLE SAMPLES"],
            sample_titles_results,
            ["Results overview"],
            pns_index,
            sns_index,
            stress_index,
            [""],
            ["Time domain results"],
            ["Statistical parameters"],
            mean_rr,
            sdnn,
            mean_hr,
            sd_hr,
            min_hr,
            max_hr,
            rmssd,
            nnxx,
            pnnxx,
            sdnn_index,
            ["Geometric parameters"],
            rr_tri_index,
            tinn,
            [""],
            frequency_domain_title,
            ["Peak frequencies"],
            peak_frequencies_vlf,
            peak_frequencies_lf,
            peak_frequencies_hf,
            ["Absolute powers"],
            absolute_powers_vlf_ms2,
            absolute_powers_lf_ms2,
            absolute_powers_hf_ms2,
            absolute_powers_vlf_log,
            absolute_powers_lf_log,
            absolute_powers_hf_log,
            ["Relative powers"],
            relative_powers_vlf,
            relative_powers_lf,
            relative_powers_hf,
            ["Normalized powers"],
            normalized_powers_lf,
            normalized_powers_hf,
            total_power,
            lf_hf_ratio,
            [""],
            [""],
            ["Nonlinear results"],
            ["Poincare plot"],
            sd1,
            sd2,
            sd1_2,
            approximate_entropy,
            sample_entropy,
            ["Detrended fluctuation analysis (DFA)"],
            alpha1,
            alpha2,
            [""],
            [""],
            ["RR INTERVAL DATA and SPECTRUM ESTIMATES"],
            sample_titles_spectrum, 
            rr_row1, 
            rr_row2,
            rr_row_units,
        ]
        # writing in csv
        if output_file:
           # Write the data to the CSV file
            with open(output_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)

                # Determine the maximum length among the arrays
                max_length = max(len(sample) for sample in peaks_columns + rr_intervals_columns)

                # Loop through the positions
                for i in range(max_length):
                    # Loop through the samples
                    current_row_values = []
                    for sample_index in range(len(peaks_columns)):
                        # Get the value from peaks_column if available
                        if i < len(peaks_columns[sample_index]):
                            current_row_values.append(peaks_columns[sample_index][i])
                        else:
                            current_row_values.append("")

                        # Get the value from rr_intervals_column if available
                        if i < len(rr_intervals_columns[sample_index]):
                            current_row_values.append(rr_intervals_columns[sample_index][i])
                        else:
                            current_row_values.append("")

                    writer.writerow(current_row_values)

    #@jit
    def append_results(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog

        file_filter = f"CSV Files (*.csv)"

        file_name, _ = QFileDialog.getOpenFileName(
            self, f"Select CSV File", "", file_filter, options=options
        )

        if file_name:
            from gui import PALMS
            import csv
            from datetime import timedelta
            # Read the CSV file into a list of lists
            data = []
            with open(file_name, 'r') as file:
                csv_reader = csv.reader(file)
                for row in csv_reader:
                    data.append(row)
                
            # update end time
            previous_end = data[5][0]
            previous_date_start = previous_end.replace("Measurement date (start): ", "")
            measurement_date_end = PALMS.get().LAST_DATETIME
            data[6][0] = f"Measurement date (end): {measurement_date_end}"
            # update duration
            previous_duration = data[7][0]
            previous_duration = previous_duration.replace("Time duration (d--h:min:s): ", "")
            time_duration = dtime.datetime.strptime(measurement_date_end, "%d--%H:%M:%S") - dtime.datetime.strptime(previous_date_start, "%d--%H:%M:%S")
            data[7][0] = f"Time duration (d--h:min:s): {time_duration}"
            # update samples number
            previous_samples = data[11][0]
            previous_samples = previous_samples.replace("Number of samples: ", "")
            samples_number = len(Partitions.all_startpoints()) + int(previous_samples)
            data[11][0] = f"Number of samples: {samples_number}"

            rr_intervals = PALMS.get().rr_intervals

            previous_sample_names = data[32]
            name_last_number = {}
           # name_last_time = {}
            for index, item in enumerate(previous_sample_names):
                parts = item.split()  # Split each string into parts using space as a delimiter
                if len(parts) == 2:
                    name, number = parts[0], parts [1]  # Extract the name and number
                    name_last_number[name] = number
                    # get column and last value is last time for sample name
                    #column_data = data[:][-1]
                    #name_last_time[name] = column_data[0]

            # for each sample (name -> index), get all the results and append them to the corresponding array
            all_samples = Partitions.all_names()
            if PALMS.get().ORIGINAL_DATETIME != None:
                previous_rr_sum = PALMS.get().ORIGINAL_DATETIME
            else:
                previous_rr_sum = 0
            for sample_name in all_samples:
                previous_samples = 0
                #last_time = 0
                if sample_name in name_last_number.keys():
                    previous_samples = int(name_last_number[sample_name])
                    #last_time = name_last_time[sample_name]
                sample_indices = Partitions.find_partition_by_name(sample_name)
                for i, sample_index in enumerate(sample_indices):
    
                    sample_number = i + previous_samples
                    current_partition = sample_index

                    data[32].append(sample_name+" "+str(sample_number+1))
                    data[44].append(sample_name+" "+str(sample_number+1))
                    data[44].append("")
                    data[102].append(sample_name+" "+str(sample_number+1))
                    data[102].append("")

                    current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
                    current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)

                    rr_local = rr_intervals[current_start:current_end]   
                    rr_local = rr_local[rr_local != 0]

                    # append sample limits
                    first_time = PALMS.get().FIRST_DATETIME
                    datetime_obj = dtime.datetime.strptime(first_time, "%d--%H:%M:%S")
                    new_start = datetime_obj + timedelta(seconds=current_partition.start)
                    current_start_date = new_start.strftime("%d--%H:%M:%S")
                    new_end = datetime_obj + timedelta(seconds=current_partition.end)
                    current_end_date = new_end.strftime("%d--%H:%M:%S")
                    data[33].append(f"{current_start_date} - {current_end_date}")

                    # how many annotations there are
                    #a = AnnotationConfig.get()[0]
                    #points_x, points_y = a.annotation.find_annotation_between_two_ts(current_partition.start, current_partition.end)
                    annotations = rr_local
                    data[36].append(len(annotations))

                    # how many outliers there are
                    points_x = PALMS.get().viewer.selectedDisplayPanel.plot_area.find_outliers_between_two_ts(current_partition.start, current_partition.end)
                    data[37].append(len(points_x))

                    # ratio of beats corrected
                    current_beats_corrected_ratio = (100 * len(points_x)) / (len(annotations) + len(points_x))
                    data[38].append(current_beats_corrected_ratio)

                    # outliers time
                    outliers_times = len(points_x)*0.7
                    non_outliers_times = np.sum(annotations)-outliers_times

                    # effective data
                    data[39].append(non_outliers_times)
                    data[40].append(non_outliers_times/(outliers_times+non_outliers_times))

                

                    # ------------TIME RESULTS---------------
                    mean_rr_local, sdnn_local, mean_hr_local, sd_hr_local, min_hr_local, max_hr_local, rmssd_local, nnxx_local, pnnxx_local, rr_tri_index_local, tinn_local, stress_index_local, sdnn_index_local = ResultsPanel.get().export_time_results(rr_local)
                    # general results
                    data[46].append("0")
                    data[46].append("")
                    data[47].append("0")
                    data[47].append("")
                    data[48].append(stress_index_local)
                    data[48].append("")
                    data[52].append(mean_rr_local)
                    data[52].append("")
                    data[53].append(sdnn_local)
                    data[53].append("")
                    data[54].append(mean_hr_local)
                    data[54].append("")
                    data[55].append(sd_hr_local)
                    data[55].append("")
                    data[56].append(min_hr_local)
                    data[56].append("")
                    data[57].append(max_hr_local)
                    data[57].append("")
                    data[58].append(rmssd_local)
                    data[58].append("")
                    data[59].append(nnxx_local)
                    data[59].append("")
                    data[60].append(pnnxx_local)
                    data[60].append("")
                    data[61].append(sdnn_index_local)
                    data[61].append("")
                    data[63].append(rr_tri_index_local)
                    data[63].append("")
                    data[64].append(tinn_local)
                    data[64].append("")

                    # ------------FREQUENCY RESULTS-------------
                    data[66].append("FFT spectrum")
                    data[66].append("AR spectrum")
                    vlf_peak_welch, lf_peak_welch, hf_peak_welch, vlf_absolute_power_ms2_welch, lf_absolute_power_ms2_welch, hf_absolute_power_ms2_welch, vlf_absolute_power_log_welch, lf_absolute_power_log_welch, hf_absolute_power_log_welch, vlf_relative_power_welch, lf_relative_power_welch, hf_relative_power_welch, lf_normalized_power_welch, hf_normalized_power_welch, total_power_welch, lf_hf_ratio_welch, vlf_peak_ar, lf_peak_ar, hf_peak_ar, vlf_absolute_power_ms2_ar, lf_absolute_power_ms2_ar, hf_absolute_power_ms2_ar, vlf_absolute_power_log_ar, lf_absolute_power_log_ar, hf_absolute_power_log_ar, vlf_relative_power_ar, lf_relative_power_ar, hf_relative_power_ar, lf_normalized_power_ar, hf_normalized_power_ar, total_power_ar, lf_hf_ratio_ar = ResultsPanel.get().export_frequency_results(rr_local)
                    data[68].append(vlf_peak_welch)
                    data[68].append(vlf_peak_ar)
                    data[69].append(lf_peak_welch)
                    data[69].append(lf_peak_ar)
                    data[70].append(hf_peak_welch)
                    data[70].append(hf_peak_ar)
                
                    data[72].append(vlf_absolute_power_ms2_welch)
                    data[72].append(vlf_absolute_power_ms2_ar)
                    data[73].append(lf_absolute_power_ms2_welch)
                    data[73].append(lf_absolute_power_ms2_ar)
                    data[74].append(hf_absolute_power_ms2_welch)
                    data[74].append(hf_absolute_power_ms2_ar)
                    data[75].append(vlf_absolute_power_log_welch)
                    data[75].append(vlf_absolute_power_log_ar)
                    data[76].append(lf_absolute_power_log_welch)
                    data[76].append(lf_absolute_power_log_ar)
                    data[77].append(hf_absolute_power_log_welch)
                    data[77].append(hf_absolute_power_log_ar)
            
                    data[79].append(vlf_relative_power_welch)
                    data[79].append(vlf_relative_power_ar)
                    data[80].append(lf_relative_power_welch)
                    data[80].append(lf_relative_power_ar)
                    data[81].append(hf_relative_power_welch)
                    data[81].append(hf_relative_power_ar)
            
                    data[83].append(lf_normalized_power_welch)
                    data[83].append(lf_normalized_power_ar)
                    data[84].append(hf_normalized_power_welch)
                    data[84].append(hf_normalized_power_ar)
                    data[85].append(total_power_welch)
                    data[85].append(total_power_ar)
                    data[86].append(lf_hf_ratio_welch)
                    data[86].append(lf_hf_ratio_ar)

                    # ------------NON LINEAR RESULTS------------
                    sd1_local, sd2_local, sd_ratio_local, apen_local, sampen_local, dfa1_local, dfa2_local = ResultsPanel.get().export_nonlinear_results(rr_local)
                
                    data[91].append(sd1_local)
                    data[91].append("")
                    data[92].append(sd2_local)
                    data[92].append("")
                    data[93].append(sd_ratio_local)
                    data[93].append("")

                    data[94].append(apen_local)
                    data[94].append("")
                    data[95].append(sampen_local)
                    data[95].append("")

                    data[97].append(dfa1_local)
                    data[97].append("")
                    data[98].append(dfa2_local)
                    data[98].append("")

                    # RR values
                    data[103].append("RR data")
                    data[103].append("")

                    data[104].append("Time")
                    data[104].append("RR interval")

                    data[105].append("(s)")
                    data[105].append("(s)")

                    # rr values start in row 106
                    rr_intervals_local = rr_local
                    if PALMS.get().FIRST_DATETIME != None:
                        rr_sum = np.cumsum(rr_intervals_local)
                        rr_sum = np.insert(rr_sum, 0, 0)

                        from dateutil import parser
                        from dateutil.relativedelta import relativedelta
                        #if last_time != 0:
                        #    dt = parser.parse(last_time)
                        #else:
                        dt = parser.parse(PALMS.get().ORIGINAL_DATETIME)
                        peaks_values_local = [dt + relativedelta(seconds=seconds) for seconds in rr_sum[:-1]]
                    else:
                        peaks_values_local = previous_rr_sum + np.cumsum(rr_intervals_local)

                    j = 0
                    for rr_interval, peak_value in zip(rr_intervals_local, peaks_values_local):
                        data[106+j].append(peak_value)
                        data[106+j].append(rr_interval)
                        j += 1

                    previous_rr_sum = peaks_values_local[-1]


            # save file
            with open(file_name, 'w', newline='') as file:
                csv_writer = csv.writer(file)
                csv_writer.writerows(data)


    def open_doc(self):
        try:
            from PyQt5.QtCore import QUrl
            ql = QtWidgets.QLabel('Help')
            import pathlib
            from utils.utils_general import resource_path
            path = resource_path(pathlib.Path('docs', 'user_manual.pdf'))
            url = bytearray(QUrl.fromLocalFile(path.as_posix()).toEncoded()).decode()
            text = "<a href={}>Reference Link> </a>".format(url)
            ql.setText(text)
            ql.setVisible(False)
            ql.setOpenExternalLinks(True)
            ql.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
            ql.linkActivated.emit('str')
            ql.move(0, 0)
            ql.show()
            mouseevent = QtGui.QMouseEvent(QtCore.QEvent.MouseButtonRelease, QtCore.QPoint(0, 0), QtCore.Qt.LeftButton,
                                           QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
            ql.mousePressEvent(mouseevent)
            ql.hide()
            del ql
        except Exception as e:
            from utils.utils_gui import Dialog
            Dialog().warningMessage('Something went wrong while opening the document.\n'
                                    'You can continue your work.\n'
                                    'The error was: '+ str(e))
            

    def open_new_file(self):
        from gui import PALMS
        from logic.databases.DatabaseHandler import Database
        from PyQt5.QtCore import qInfo, qDebug
        from PyQt5.QtWidgets import QFileDialog
        import h5py
        from logic.operation_mode.annotation import AnnotationConfig
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Restart...",
                                                "Do you want to save the current file ?",
                                                QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Abort)
        if result == QtWidgets.QMessageBox.Save or result==QtWidgets.QMessageBox.Discard:
            #db = Database.get()

            if result == QtWidgets.QMessageBox.Save:
                #db.save()
                #qInfo('{} saved'.format(db.fullpath.stem))
                options = QFileDialog.Options()
                file_path, _ = QFileDialog.getSaveFileName(self, "Save HDF5 File", "", "HDF5 Files (*.h5);;All Files (*)", options=options)
                
                if file_path:
                    loading_box = QMessageBox()
                    loading_box.setWindowTitle("Saving file")
                    loading_box.setText("Saving file")
                    loading_box.show()

                    ecg_values = PALMS.get().ECG_DATA
                    annotations = [fiducial.annotation.idx for fiducial in AnnotationConfig.get().fiducials]
                    annotations = np.array(annotations[0])
                    algorithm_outliers = PALMS.get().algorithm_outliers
                    threshold_outliers = PALMS.get().threshold_outliers
                    start_missing_indexes = PALMS.get().START_MISSING_INDEXES
                    end_missing_indexes = PALMS.get().END_MISSING_INDEXES
                    noise_start_points = RRNoisePartitions.all_startpoints()
                    noise_end_points = RRNoisePartitions.all_endpoints()
                    frequency = PALMS.get().FREQUENCY
                    is_algorithm_outlier = False
                    is_threshold_outlier = False
                    current_outlier = 0
                    algorithm_correction = self.algorithm_active
                    is_algorithm_outlier = PALMS.get().viewer.getOutliersDisplayPanel().current_algorithm_outliers
                    is_threshold_outlier = PALMS.get().viewer.getOutliersDisplayPanel().current_threshold_outliers
                    current_outlier = PALMS.get().viewer.getOutliersDisplayPanel().currentSelector
                    # get partitions
                    samples_dictionary = {}
                    all_samples = Partitions.all_names()
                    for sample_name in all_samples:
                        sample_indices = Partitions.find_partition_by_name(sample_name)
                        for i, sample_index in enumerate(sample_indices):
                            current_partition = sample_index
                            current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
                            current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)

                            # Check if the sample_name exists in the dictionary, if not, create it
                            if sample_name not in samples_dictionary:
                                samples_dictionary[sample_name] = {}

                            if sample_index not in samples_dictionary[sample_name]:
                                samples_dictionary[sample_name][i] = {}

                            # add to dictionary name, start and end
                            samples_dictionary[sample_name][i] = {'start': current_start, 'end': current_end}

                    with h5py.File(file_path, 'w') as hdf_file:

                        # Create a group for numbers and arrays.
                        group1 = hdf_file.create_group('group1')

                        # Create a group for samples dictionary.
                        group2 = hdf_file.create_group('group2')

                        # group 3 for boolean and strings
                        group3 = hdf_file.create_group('group3')

                        # group 4 for algoruthm outliers dictionary
                        group4 = hdf_file.create_group('group4')

                        # fill group 1
                        group1.attrs['noise_level'] = self.noise_level.currentIndex()
                        group1.attrs['beat_correction_level'] = self.beat_threshold_level.currentIndex()
                        group1.attrs['frequency'] = frequency
                        group1.attrs['current_outlier'] = current_outlier
                        group1.attrs["RR_ONLY"] = PALMS.get().RR_ONLY
                        group1.attrs["DATA_TYPE"] = PALMS.get().DATA_TYPE
                        group1.create_dataset('ecg_values', data=ecg_values)
                        group1.create_dataset('annotations', data=annotations)
                        group1.create_dataset('original_rr', data=PALMS.get().original_rr.get_value())
                        group1.create_dataset('original_fiducials', data=PALMS.get().original_fiducials)
                        group1.create_dataset('original_annotations', data=PALMS.get().original_annotations)
                        group1.create_dataset('threshold_outliers', data=threshold_outliers)
                        group1.create_dataset('noise_start_indexes', data=noise_start_points)
                        group1.create_dataset('noise_end_indexes', data=noise_end_points)
                        group1.create_dataset('missing_start_indexes', data=start_missing_indexes)
                        group1.create_dataset('missing_end_indexes', data=end_missing_indexes)

                        # fill group 2
                        for sample_name, sample_data in samples_dictionary.items():
                            for sample_index, key in sample_data.items():
                                for sample_limit, value in key.items():
                                    group2.attrs[f'{sample_name}_{sample_index}_{sample_limit}'] = value

                        group3.attrs['is_algorithm_outlier'] = is_algorithm_outlier
                        group3.attrs['is_threshold_outlier'] = is_threshold_outlier
                        group3.attrs['algorithm_correction'] = algorithm_correction
                        group3.attrs['first_datetime'] = PALMS.get().FIRST_DATETIME
                        group3.attrs['last_datetime'] = PALMS.get().LAST_DATETIME
                        group3.attrs['current_file'] = PALMS.get().CURRENT_FILE

                        for key, value in algorithm_outliers.items():
                            group4.attrs[f'{key}'] = value

                    loading_box.close()

            PALMS.NEXT_FILE = None
            # PALMS.PREV_FILE = PALMS.CURRENT_FILE  # after reboot there is no previous file
            
            AnnotationConfig.get().clear()
            Partitions.delete_all()
            NoisePartitions.delete_all()
            RRNoisePartitions.delete_all()
            db = Database.get()
            db.tracks.clear()
            PALMS.get().delete_all()
            PALMS.get().viewer.REBOOT_APP = True
            QtGui.QGuiApplication.exit(PALMS.EXIT_CODE_REBOOT)
        
    def save_default(self):
        from gui import PALMS
        if PALMS.get().SAVE_FILE is None:
            self.save_file()
        else:
            import h5py
            from gui import PALMS
            from logic.operation_mode.annotation import AnnotationConfig

            file_path = PALMS.get().SAVE_FILE

            loading_box = QMessageBox()
            loading_box.setWindowTitle("Saving file")
            loading_box.setText("Saving file")
            loading_box.show()

            ecg_values = PALMS.get().ECG_DATA
            annotations = [fiducial.annotation.idx for fiducial in AnnotationConfig.get().fiducials]
            annotations = np.array(annotations[0])
            algorithm_outliers = PALMS.get().algorithm_outliers
            threshold_outliers = PALMS.get().threshold_outliers
            start_missing_indexes = PALMS.get().START_MISSING_INDEXES
            end_missing_indexes = PALMS.get().END_MISSING_INDEXES
            noise_start_points = RRNoisePartitions.all_startpoints()
            noise_end_points = RRNoisePartitions.all_endpoints()
            frequency = PALMS.get().FREQUENCY
            is_algorithm_outlier = False
            is_threshold_outlier = False
            current_outlier = 0
            algorithm_correction = self.algorithm_active
            is_algorithm_outlier = PALMS.get().viewer.getOutliersDisplayPanel().current_algorithm_outliers
            is_threshold_outlier = PALMS.get().viewer.getOutliersDisplayPanel().current_threshold_outliers
            current_outlier = PALMS.get().viewer.getOutliersDisplayPanel().currentSelector
            # get partitions
            samples_dictionary = {}
            all_samples = Partitions.all_names()
            for sample_name in all_samples:
                sample_indices = Partitions.find_partition_by_name(sample_name)
                for i, sample_index in enumerate(sample_indices):
                    current_partition = sample_index
                    current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
                    current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)

                    # Check if the sample_name exists in the dictionary, if not, create it
                    if sample_name not in samples_dictionary:
                        samples_dictionary[sample_name] = {}

                    if sample_index not in samples_dictionary[sample_name]:
                        samples_dictionary[sample_name][i] = {}

                    # add to dictionary name, start and end
                    samples_dictionary[sample_name][i] = {'start': current_start, 'end': current_end}

            with h5py.File(file_path, 'w') as hdf_file:
                # Create a group for numbers and arrays.
                group1 = hdf_file.create_group('group1')

                # Create a group for samples dictionary.
                group2 = hdf_file.create_group('group2')

                # group 3 for boolean and strings
                group3 = hdf_file.create_group('group3')

                # group 4 for algoruthm outliers dictionary
                group4 = hdf_file.create_group('group4')

                # fill group 1
                group1.attrs['noise_level'] = self.noise_level.currentIndex()
                group1.attrs['beat_correction_level'] = self.beat_threshold_level.currentIndex()
                group1.attrs['frequency'] = frequency
                group1.attrs['current_outlier'] = current_outlier
                group1.attrs["RR_ONLY"] = PALMS.get().RR_ONLY
                group1.attrs["DATA_TYPE"] = PALMS.get().DATA_TYPE
                group1.create_dataset('ecg_values', data=ecg_values)
                group1.create_dataset('annotations', data=annotations)
                group1.create_dataset('original_rr', data=PALMS.get().original_rr.get_value())
                group1.create_dataset('original_fiducials', data=PALMS.get().original_fiducials)
                group1.create_dataset('original_annotations', data=PALMS.get().original_annotations)
                group1.create_dataset('threshold_outliers', data=threshold_outliers)
                group1.create_dataset('noise_start_indexes', data=noise_start_points)
                group1.create_dataset('noise_end_indexes', data=noise_end_points)
                group1.create_dataset('missing_start_indexes', data=start_missing_indexes)
                group1.create_dataset('missing_end_indexes', data=end_missing_indexes)

                # fill group 2
                for sample_name, sample_data in samples_dictionary.items():
                    for sample_index, key in sample_data.items():
                        for sample_limit, value in key.items():
                            group2.attrs[f'{sample_name}_{sample_index}_{sample_limit}'] = value

                group3.attrs['is_algorithm_outlier'] = is_algorithm_outlier
                group3.attrs['is_threshold_outlier'] = is_threshold_outlier
                group3.attrs['algorithm_correction'] = algorithm_correction
                group3.attrs['first_datetime'] = PALMS.get().FIRST_DATETIME
                group3.attrs['last_datetime'] = PALMS.get().LAST_DATETIME
                group3.attrs['current_file'] = PALMS.get().CURRENT_FILE

                for key, value in algorithm_outliers.items():
                    group4.attrs[f'{key}'] = value

            PALMS.get().SAVE_FILE = file_path
            loading_box.close()


    def save_file(self):
        import h5py
        from gui import PALMS
        from logic.operation_mode.annotation import AnnotationConfig
        from PyQt5.QtWidgets import QFileDialog

        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save HDF5 File", "", "HDF5 Files (*.h5);;All Files (*)", options=options)

        if file_path:
            loading_box = QMessageBox()
            loading_box.setWindowTitle("Saving file")
            loading_box.setText("Saving file")
            loading_box.show()

            ecg_values = PALMS.get().ECG_DATA
            annotations = [fiducial.annotation.idx for fiducial in AnnotationConfig.get().fiducials]
            annotations = np.array(annotations[0])
            algorithm_outliers = PALMS.get().algorithm_outliers
            threshold_outliers = PALMS.get().threshold_outliers
            start_missing_indexes = PALMS.get().START_MISSING_INDEXES
            end_missing_indexes = PALMS.get().END_MISSING_INDEXES
            noise_start_points = RRNoisePartitions.all_startpoints()
            noise_end_points = RRNoisePartitions.all_endpoints()
            frequency = PALMS.get().FREQUENCY
            is_algorithm_outlier = False
            is_threshold_outlier = False
            current_outlier = 0
            algorithm_correction = self.algorithm_active
            is_algorithm_outlier = PALMS.get().viewer.getOutliersDisplayPanel().current_algorithm_outliers
            is_threshold_outlier = PALMS.get().viewer.getOutliersDisplayPanel().current_threshold_outliers
            current_outlier = PALMS.get().viewer.getOutliersDisplayPanel().currentSelector
            # get partitions
            samples_dictionary = {}
            all_samples = Partitions.all_names()
            for sample_name in all_samples:
                sample_indices = Partitions.find_partition_by_name(sample_name)
                for i, sample_index in enumerate(sample_indices):
                    current_partition = sample_index
                    current_start = PALMS.get().from_time_to_closest_sample(current_partition.start)
                    current_end = PALMS.get().from_time_to_closest_sample(current_partition.end)

                    # Check if the sample_name exists in the dictionary, if not, create it
                    if sample_name not in samples_dictionary:
                        samples_dictionary[sample_name] = {}

                    if sample_index not in samples_dictionary[sample_name]:
                        samples_dictionary[sample_name][i] = {}

                    # add to dictionary name, start and end
                    samples_dictionary[sample_name][i] = {'start': current_start, 'end': current_end}

            with h5py.File(file_path, 'w') as hdf_file:
                # Create a group for numbers and arrays.
                group1 = hdf_file.create_group('group1')

                # Create a group for samples dictionary.
                group2 = hdf_file.create_group('group2')

                # group 3 for boolean and strings
                group3 = hdf_file.create_group('group3')

                # group 4 for algoruthm outliers dictionary
                group4 = hdf_file.create_group('group4')

                # fill group 1
                group1.attrs['noise_level'] = self.noise_level.currentIndex()
                group1.attrs['beat_correction_level'] = self.beat_threshold_level.currentIndex()
                group1.attrs['frequency'] = frequency
                group1.attrs['current_outlier'] = current_outlier
                group1.attrs["RR_ONLY"] = PALMS.get().RR_ONLY
                group1.attrs["DATA_TYPE"] = PALMS.get().DATA_TYPE
                group1.create_dataset('ecg_values', data=ecg_values)
                group1.create_dataset('annotations', data=annotations)
                group1.create_dataset('original_rr', data=PALMS.get().original_rr.get_value())
                group1.create_dataset('original_fiducials', data=PALMS.get().original_fiducials)
                group1.create_dataset('original_annotations', data=PALMS.get().original_annotations)
                group1.create_dataset('threshold_outliers', data=threshold_outliers)
                group1.create_dataset('noise_start_indexes', data=noise_start_points)
                group1.create_dataset('noise_end_indexes', data=noise_end_points)
                group1.create_dataset('missing_start_indexes', data=start_missing_indexes)
                group1.create_dataset('missing_end_indexes', data=end_missing_indexes)

                # fill group 2
                for sample_name, sample_data in samples_dictionary.items():
                    for sample_index, key in sample_data.items():
                        for sample_limit, value in key.items():
                            group2.attrs[f'{sample_name}_{sample_index}_{sample_limit}'] = value

                group3.attrs['is_algorithm_outlier'] = is_algorithm_outlier
                group3.attrs['is_threshold_outlier'] = is_threshold_outlier
                group3.attrs['algorithm_correction'] = algorithm_correction
                group3.attrs['first_datetime'] = PALMS.get().FIRST_DATETIME
                group3.attrs['last_datetime'] = PALMS.get().LAST_DATETIME
                group3.attrs['current_file'] = PALMS.get().CURRENT_FILE

                for key, value in algorithm_outliers.items():
                    group4.attrs[f'{key}'] = value

            PALMS.get().SAVE_FILE = file_path
            loading_box.close()