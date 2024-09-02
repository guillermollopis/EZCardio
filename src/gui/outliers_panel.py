from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtWidgets import QPushButton, QCheckBox, QLabel, QApplication
from functools import partial
import numpy as np
from logic.operation_mode.rr_noise_partitioning import RRNoisePartition, RRNoisePartitions
from logic.operation_mode.noise_partitioning import NoisePartition, NoisePartitions


class OutliersFrame(QtWidgets.QFrame):

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
        #self.n = 100
        #self.updateHeight()

        # Drag and Drop Related
        # TODO: only accept drag/drop of other Frames (through MIME data)
        self.setAcceptDrops(True)
        self.outliersPanel: OutliersPanel = None
        self.dragStartPos = QtCore.QPoint()
        self.drag = None

    def updateHeight(self):
        self.setFixedHeight(self.n)



class OutliersPanel(QtWidgets.QWidget):

    def __init__(self, frame: OutliersFrame):
        super().__init__()
        
        self.setParent(frame)

        self.current_algorithm_outliers = False
        self.algorithm_outliers = np.array([])
        self.current_threshold_outliers = False
        self.threshold_outliers = np.array([], dtype="int32")

        layout = QtWidgets.QHBoxLayout()

        self.toogle_left_button = QPushButton()
        self.toogle_left_button.setFixedSize(50, 50)
        from utils.utils_general import resource_path
        import os
        import sys
        from pathlib import Path
        try:
            resize_icon = QtGui.QIcon(os.path.join(sys._MEIPASS,"config/icons/expand_left_right.png"))
        except:
            resize_icon = QtGui.QIcon(os.path.join(os.path.abspath("."),"config/icons/expand_left_right.png"))
        self.toogle_left_button.setIcon(resize_icon)
        layout.addWidget(self.toogle_left_button)
        self.toogle_left_button.setToolTip("Show or hide analysis options")
        self.toogle_left_button.clicked.connect(self.expandWidget)

        # dropdown to choose what the selector will be showing
        self.selector_option = QtWidgets.QComboBox()
        self.selector_option.addItem("Show noise")
        self.selector_option.addItem("Show algorithm outliers")
        self.selector_option.addItem("Show threshold outliers")
        self.selector_option.wheelEvent = lambda event: None
        layout.addWidget(self.selector_option)
        self.selector_option.currentIndexChanged.connect(self.switchSelectorOption)
        
        # Create and add the components for the first line
        self.selector_left_button = QPushButton("<")
        self.selector_left_button.setFixedHeight(20)
        self.selector_left_button.setDisabled(True)
        layout.addWidget(self.selector_left_button)

        self.currentSelector = 1
        self.selector_label = QLabel("Add noise or outliers correction to mark them")
        self.selector_label.setFixedHeight(20)
        layout.addWidget(self.selector_label)

        self.selector_right_button = QPushButton(">")
        self.selector_right_button.setFixedHeight(20)
        self.selector_right_button.setDisabled(True)
        layout.addWidget(self.selector_right_button)

        self.selector_left_button.clicked.connect(lambda: self.update_label(self.currentSelector, -1))
        self.selector_right_button.clicked.connect(lambda: self.update_label(self.currentSelector, 1))

        frame.setLayout(layout)


    def expandWidget(self):
        self.parent().parent().viewer.toggle_resize_left() 

    def switchSelectorOption(self):
        current_selector = self.selector_option.currentIndex()

        if current_selector == 0:
            self.initializeNoise()
        elif current_selector == 1:
            self.initializeAlgorithmOutliers()
        else:
            self.initializeThresholdOutliers()


    def initializeAlgorithmOutliers(self):

        self.current_algorithm_outliers = True
        self.current_threshold_outliers = False
        
        from gui.viewer import PALMS
        outliers = self.algorithm_outliers


        if (len(outliers) == 0):
            self.selector_label.setText("No algorithm outliers")
        else:
            outliers = np.unique(outliers)

            self.currentSelector = 1
            self.selector_label.setText("Algorithm Outlier 1")

            center_time = outliers[0]
            first_time = max(0, (center_time-5))
            end_time = min((center_time+5), PALMS.get().from_sample_to_time(len(PALMS.get().ECG_DATA)-1))

            PALMS.get().viewer.getRRDisplayPanel().plot_area.main_plot.getViewBox().setXRange(first_time, end_time)

        self.enable_selectors(1)


    def initializeThresholdOutliers(self):

        self.current_algorithm_outliers = False
        self.current_threshold_outliers = True
        
        from gui.viewer import PALMS
        outliers = self.threshold_outliers


        if (len(outliers) == 0):
            self.selector_label.setText("No threshold outliers")
        else:
            outliers = np.unique(outliers)

            self.currentSelector = 1
            self.selector_label.setText("Threshold Outlier 1")

            center_time = outliers[0]
            first_time = max(0, (center_time-5))
            end_time = min((center_time+5), PALMS.get().from_sample_to_time(len(PALMS.get().ECG_DATA)-1))

            PALMS.get().viewer.getRRDisplayPanel().plot_area.main_plot.getViewBox().setXRange(first_time, end_time)

        self.enable_selectors(2)


    def initializeNoise(self):

        self.current_algorithm_outliers = False
        self.current_threshold_outliers = False
        
        from gui.viewer import PALMS
        if PALMS.get().RR_ONLY:
            self.noise_starts = RRNoisePartitions.all_startpoints_by_two_names("", "ecg")
            self.noise_ends = RRNoisePartitions.all_endpoints_by_two_names("", "ecg")
        else:
            self.noise_starts = RRNoisePartitions.all_startpoints_by_two_names("", "ecg")
            self.noise_ends = RRNoisePartitions.all_endpoints_by_two_names("", "ecg")

        if (self.noise_starts.size == 0):
            self.selector_label.setText("No noise intervals")
        else:
            self.currentSelector = 1
            self.selector_label.setText("Noise interval 1")

            first_moment = self.noise_starts[0]
            last_moment = self.noise_ends[0]
            first_time = max(0, (first_moment-5))
            end_time = min((last_moment+5), PALMS.get().from_sample_to_time(len(PALMS.get().ECG_DATA)-1))

            PALMS.get().viewer.getRRDisplayPanel().plot_area.main_plot.getViewBox().setXRange(first_time, end_time)

        self.enable_selectors(0)


    def update_label(self, current_value, value):
        if self.current_algorithm_outliers:
            self.update_algorithm_outlier_label(current_value, value)
        elif self.current_threshold_outliers:
            self.update_threshold_outlier_label(current_value, value)
        else:
            self.update_noise_label(current_value, value)


    def update_algorithm_outlier_label(self, current_value, value):

        from gui.viewer import PALMS
        outliers = self.algorithm_outliers
        
        new_value = current_value + value
        if (new_value >= 1):

            if (value == -1 or len(outliers) > self.currentSelector):
                
                self.currentSelector = new_value
                self.selector_label.setText("Algorithm Outlier "+str(new_value))

                current_outlier = outliers[new_value-1] # time

                center_time = current_outlier
                first_time = max(0, (center_time-5))
                end_time = min((center_time+5), PALMS.get().from_sample_to_time(len(PALMS.get().ECG_DATA)-1))

                PALMS.get().viewer.getRRDisplayPanel().plot_area.main_plot.getViewBox().setXRange(first_time, end_time)

        self.enable_selectors(1)


    def update_threshold_outlier_label(self, current_value, value):

        from gui.viewer import PALMS
        outliers = self.threshold_outliers
        
        new_value = current_value + value
        if (new_value >= 1):

            if (value == -1 or len(outliers) > self.currentSelector):
                
                self.currentSelector = new_value
                self.selector_label.setText("Threshold Outlier "+str(new_value))

                current_outlier = outliers[new_value-1] # time

                center_time = current_outlier
                first_time = max(0, (center_time-5))
                end_time = min((center_time+5), PALMS.get().from_sample_to_time(len(PALMS.get().ECG_DATA)-1))

                PALMS.get().viewer.getRRDisplayPanel().plot_area.main_plot.getViewBox().setXRange(first_time, end_time)

        self.enable_selectors(2)


    def update_noise_label(self, current_value, value):

        from gui.viewer import PALMS
        noise_starts = self.noise_starts
        noise_ends = self.noise_ends
        
        new_value = current_value + value
        if (new_value >= 1):

            if (value == -1 or len(noise_starts) > self.currentSelector):
                
                self.currentSelector = new_value
                self.selector_label.setText("Noise interval "+str(new_value))

                current_start = noise_starts[new_value-1] # time
                current_end = noise_ends[new_value-1] # time

                first_time = max(0, (current_start-5))
                end_time = min((current_end+5), PALMS.get().from_sample_to_time(len(PALMS.get().ECG_DATA)-1))

                PALMS.get().viewer.getRRDisplayPanel().plot_area.main_plot.getViewBox().setXRange(first_time, end_time)

        self.enable_selectors(0)


    def enable_selectors(self, selector_type):
        # selector_type: 0 for noise, 1 for algorithm, 2 for threshold

        if selector_type==0:
            selector_len = len(self.noise_starts)
        
        elif selector_type==1:
            selector_len = len(self.algorithm_outliers)

        elif selector_type==2:
            selector_len = len(self.threshold_outliers)

        if self.currentSelector == 1:
            self.selector_left_button.setDisabled(True)
        else:
            self.selector_left_button.setDisabled(False)

        if self.currentSelector < selector_len:
            self.selector_right_button.setDisabled(False)
        else:
            self.selector_right_button.setDisabled(True)