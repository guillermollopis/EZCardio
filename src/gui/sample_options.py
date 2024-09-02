from qtpy import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget, QPushButton, QMessageBox
import datetime as dtime
from logic.operation_mode.partitioning import SinglePartition, Partitions
from logic.operation_mode.noise_partitioning import NoisePartition, NoisePartitions
from config import settings
import json
import numpy as np
from pathlib import Path
from utils.utils_general import resource_path
from utils.utils_gui import Dialog


class SampleOptionsFrame(QtWidgets.QFrame):

    def __init__(self, main_window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setParent(main_window)
        self.setContentsMargins(0, 0, 0, 0)
        self.setFrameStyle(self.NoFrame)

        # Layout
        self.layout = QtWidgets.QFormLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Focus
        self.installEventFilter(self)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Sizing
        #self.n = 150
        #self.updateHeight()

        # Drag and Drop Related
        # TODO: only accept drag/drop of other Frames (through MIME data)
        self.setAcceptDrops(True)
        self.sampleOptionsPanel: SampleOptionsPanel = None
        self.dragStartPos = QtCore.QPoint()
        self.drag = None

    def updateHeight(self):
        self.setFixedHeight(self.n)



class SampleOptionsPanel(QtWidgets.QWidget):

    def __init__(self, frame: SampleOptionsFrame, split=False):
        super().__init__()
        
        self.setParent(frame)
        #self.setStyleSheet("background-color: grey;")

        layout = QtWidgets.QVBoxLayout()

        # Load settings from JSON file
        with open(resource_path(Path('settings.json'))) as f:
            self.settings = json.load(f)

        # Third row - Start and duration
        self.sample_selection_start_layout = QtWidgets.QHBoxLayout()
        self.sample_selection_start_widget = QtWidgets.QWidget()
        self.sample_selection_start_widget.setLayout(self.sample_selection_start_layout)

        from gui.viewer import PALMS
        self.sample_selection_start_label = QtWidgets.QLabel("Start(h:min:s)")
        start_time = PALMS.get().FIRST_DATETIME

        self.sample_selection_start_space = QtWidgets.QLineEdit(start_time)
        self.sample_selection_duration_label = QtWidgets.QLabel("Duration(h:min:s)")
        default_duration = self.settings['sample_length']
        seconds_length = default_duration
        m, s = divmod(seconds_length, 60)
        h, m = divmod(m, 60)
        time_str = f"{int(h)}:{int(m)}:{int(s)}"
        self.sample_selection_duration_space = QtWidgets.QLineEdit(time_str)

        self.sample_selection_start_layout.addWidget(self.sample_selection_start_label)
        self.sample_selection_start_layout.addWidget(self.sample_selection_start_space)
        self.sample_selection_start_layout.addWidget(self.sample_selection_duration_label)
        self.sample_selection_start_layout.addWidget(self.sample_selection_duration_space)
        layout.addWidget(self.sample_selection_start_widget)

        # Fourth row - Repetitions (number, until end, all signal)
        self.sample_selection_repetitions_layout = QtWidgets.QHBoxLayout()
        self.sample_selection_repetitions_widget = QtWidgets.QWidget()
        self.sample_selection_repetitions_widget.setLayout(self.sample_selection_repetitions_layout)

        self.sample_selection_repetition_combo = QtWidgets.QComboBox()
        self.sample_selection_repetition_combo.addItem("Number of repetitions")
        self.sample_selection_repetition_combo.addItem("Select end (d--h:min:s)")
        self.sample_selection_repetition_combo.addItem("All signal")
        self.sample_selection_repetition_combo.wheelEvent = lambda event: None
        #sample_selection_repetition_combo.setFixedHeight(20)

        self.sample_selection_repetition_combo.currentTextChanged.connect(lambda: self.selection_repetition_changed(self.sample_selection_repetition_combo.currentIndex()))

        self.sample_selection_repetitions_space = QtWidgets.QLineEdit(str(self.settings["number_samples"]))

        self.sample_selection_repetitions_layout.addWidget(self.sample_selection_repetition_combo)
        self.sample_selection_repetitions_layout.addWidget(self.sample_selection_repetitions_space)
        #sample_selection_repetition_combo.setFixedHeight(20)
        layout.addWidget(self.sample_selection_repetitions_widget)

        # Fifth row - Separation (space or overlap)
        sample_selection_between_layout = QtWidgets.QHBoxLayout()
        sample_selection_between_widget = QtWidgets.QWidget()
        sample_selection_between_widget.setLayout(sample_selection_between_layout)

        self.sample_selection_separation_combo = QtWidgets.QComboBox()
        self.sample_selection_separation_combo.addItem("Overlap (%)")
        self.sample_selection_separation_combo.addItem("Space between samples (d--h:min:s)")
        self.sample_selection_separation_combo.wheelEvent = lambda event: None
        #sample_selection_separation_combo.setFixedHeight(20)

        self.sample_selection_separation_combo.currentTextChanged.connect(lambda: self.selection_separation_changed(self.sample_selection_separation_combo.currentIndex()))

        self.sample_selection_between_space = QtWidgets.QLineEdit("0")
       
        sample_selection_between_layout.addWidget(self.sample_selection_separation_combo)
        sample_selection_between_layout.addWidget(self.sample_selection_between_space)
        layout.addWidget(sample_selection_between_widget)

        # Sixth row - Minimum sample size
        minimum_sample_size_layout = QtWidgets.QHBoxLayout()
        minimum_sample_size_widget = QtWidgets.QWidget()
        minimum_sample_size_widget.setLayout(minimum_sample_size_layout)

        self.minimum_sample_size_label = QtWidgets.QLabel("Minimum sample size (s)")
        self.minimum_sample_size_space = QtWidgets.QLineEdit(str(self.settings["minimum_sample_size"]))
        minimum_sample_size_layout.addWidget(self.minimum_sample_size_label)
        minimum_sample_size_layout.addWidget(self.minimum_sample_size_space)
        layout.addWidget(minimum_sample_size_widget)
        
        frame.setLayout(layout)


    def selection_repetition_changed(self, new_option_index):
        if (new_option_index == 0): # number of repetitions
            self.sample_selection_repetitions_space.setEnabled(True)
            self.sample_selection_repetitions_space.setText("1")

        elif (new_option_index == 1): # until certain point
            self.sample_selection_repetitions_space.setEnabled(True)
            # add 5 minutes to start datetime
            start_time_datetime = dtime.datetime.strptime(self.sample_selection_start_space.text(), "%d--%H:%M:%S")
            next_time_datetime = start_time_datetime + dtime.timedelta(seconds=300)
            next_time = next_time_datetime.strftime("%d--%H:%M:%S")
            self.sample_selection_repetitions_space.setText(next_time)

        else: # until end of signal
            self.sample_selection_repetitions_space.setEnabled(False)
            self.sample_selection_repetitions_space.setText("")

    def selection_separation_changed(self, new_option_index):
        if (new_option_index == 0): # overlap
            self.sample_selection_between_space.setEnabled(True)
            self.sample_selection_between_space.setText("0")
        elif (new_option_index == 1): # space between samples
            self.sample_selection_between_space.setEnabled(True)
            self.sample_selection_between_space.setText("0--0:00:00")
    
    def add_sample(self, name):
        try:

            # Create and show the "Loading data" message box
            loading_box = QMessageBox()
            loading_box.setWindowTitle("Loading")
            loading_box.setText("Adding samples...")
            loading_box.show()

            from gui import PALMS

            # first time
            first_time = PALMS.get().FIRST_DATETIME
            # Parse the components of the time string
            days, time = first_time.split('--')
            hours, minutes, seconds = time.split(':')
            first_seconds = int(days) * 24 * 3600 + int(hours) * 3600 + int(minutes) * 60 + int(seconds)

            # sample start
            sample_start = self.sample_selection_start_space.text()
            # Parse the components of the time string
            days, time = sample_start.split('--')
            hours, minutes, seconds = time.split(':')
            start_seconds = int(days) * 24 * 3600 + int(hours) * 3600 + int(minutes) * 60 + int(seconds)

            difference_seconds = start_seconds - first_seconds
            start_index = PALMS.get().from_time_to_closest_sample(difference_seconds)

            # duration
            duration_time = self.sample_selection_duration_space.text()
            # Parse the components of the time string
            hours, minutes, seconds = duration_time.split(':')
            duration_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            duration_index = PALMS.get().from_time_to_closest_sample(duration_seconds)

            adding_option = self.sample_selection_repetition_combo.currentIndex()

            if (adding_option == 0): # number of repetitions
                self.add_sample_from_repetitions(start_index, duration_index, name)
            
            elif (adding_option == 1): # until time
                try:
                    end_time = self.sample_selection_repetitions_space.text()
                    # Parse the components of the time string
                    days, time = end_time.split('--')
                    hours, minutes, seconds = time.split(':')
                    end_seconds = int(days) * 24 * 3600 + int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                    difference_seconds = end_seconds - first_seconds
                    end_index = PALMS.get().from_time_to_closest_sample(difference_seconds)
                    self.add_sample_from_end(start_index, duration_index, end_index, name)
                    self.disableOptions()
                except:
                    Dialog().warningMessage('Something went wrong while creating the samples.\n'
                                    'Make sure the time format is correct.')

            elif (adding_option == 2): # until end
                end_index = len(PALMS.get().ECG_DATA)
                self.add_sample_from_end(start_index, duration_index, end_index, name)
                self.disableOptions()

            
            loading_box.close()

        except Exception as e:
            import traceback
            # Display an error message box
            error_message = "An error has occurred!"
            QMessageBox.critical(None, "Error", str(e), QMessageBox.Ok)
            error_traceback = traceback.format_exc()
            print(error_traceback)
            loading_box.close()

    def add_sample_from_repetitions(self, start_index, duration_index, name):
        from gui import PALMS

        repetitions = self.sample_selection_repetitions_space.text()

        end_signal_index = len(PALMS.get().ECG_DATA)

        if (start_index + duration_index * (int(repetitions)-1) + int(self.minimum_sample_size_space.text())) > end_signal_index:
            QMessageBox.critical(None, "Error", "The signal is not long enough to have so many repetitions", QMessageBox.Ok)
            return

        if (start_index < 0):
            start_index = 0

        start_indexes = np.array([], dtype="int32")
        end_indexes = np.array([], dtype="int32")
        
        start_index = PALMS.get().from_sample_to_time(start_index)
        duration_index = PALMS.get().from_sample_to_time(duration_index)
        
        # Generate the remaining values
        for _ in range(int(repetitions)):
            if (self.is_too_noisy(start_index, (start_index+duration_index)) is False):

                start_indexes = np.append(start_indexes, start_index)
                end_indexes = np.append(end_indexes, start_index+duration_index)

                p = SinglePartition(name, start=start_index, end=(start_index+duration_index)) # The partition goes from end to start, as it is the missing part
                PALMS.get().viewer.RRDisplayPanel.plot_area.main_vb.addItem(p)
                PALMS.get().viewer.RRDisplayPanel.plot_area.main_vb.addItem(p.label)

            if (self.sample_selection_separation_combo.currentIndex() == 0): # overlap %
                start_index = start_index + duration_index - (duration_index) * (int(self.sample_selection_between_space.text()) / 100)
            else: # space between d--hh:mm:ss
                duration_time = self.sample_selection_between_space.text()
                # Parse the components of the time string
                days, time = duration_time.split('--')
                hours, minutes, seconds = time.split(':')
                space_seconds = int(days) * 24 * 3600 + int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                space_index = space_seconds

                start_index = start_index + duration_index + space_index
                # check that not the end
                if start_index > (end_signal_index+int(self.minimum_sample_size_space.text())):
                    self.disableOptions()
                    break

        self.disableOptions()


        

    
    def add_sample_from_end(self, start_index, duration_index, end_index, name):
        from gui import PALMS

        start_indexes = np.array([], dtype="int32")
        end_indexes = np.array([], dtype="int32")

        if (start_index < 0):
            start_index = 0

        start_index = PALMS.get().from_sample_to_time(start_index)
        duration_index = PALMS.get().from_sample_to_time(duration_index)
        end_index = PALMS.get().from_sample_to_time(end_index-1)

        while (start_index < end_index):

            if (self.is_too_noisy(start_index, (start_index+duration_index)) is False):

                start_indexes = np.append(start_indexes, start_index)
                end_indexes = np.append(end_indexes, start_index+duration_index)
                p = SinglePartition(name, start=start_index, end=(start_index+duration_index)) # The partition goes from end to start, as it is the missing part
                PALMS.get().viewer.RRDisplayPanel.plot_area.main_vb.addItem(p)
                PALMS.get().viewer.RRDisplayPanel.plot_area.main_vb.addItem(p.label)
            if (self.sample_selection_separation_combo.currentIndex() == 0): # overlap %
                start_index = start_index + duration_index - (duration_index) * (int(self.sample_selection_between_space.text()) / 100)
            else: # space between d--hh:mm:ss
                duration_time = self.sample_selection_between_space.text()
                # Parse the components of the time string
                days, time = duration_time.split('--')
                hours, minutes, seconds = time.split(':')
                space_seconds = int(days) * 24 * 3600 + int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                space_index = space_seconds

                start_index = start_index + duration_index + space_index



    def disableOptions(self):
        from gui import PALMS
        PALMS.get().viewer.top_left_w.sample_selection_add.setStyleSheet("background-color: lightgray; color: gray;")
        PALMS.get().viewer.top_left_w.sample_selection_remove.setStyleSheet("background-color: blue; color: white;")
        PALMS.get().viewer.top_left_w.sample_selection_right.setEnabled(True)
        self.sample_selection_start_space.setEnabled(False)
        self.sample_selection_duration_space.setEnabled(False)
        self.sample_selection_repetition_combo.setEnabled(False)
        self.sample_selection_repetitions_space.setEnabled(False)
        self.sample_selection_separation_combo.setEnabled(False)
        self.sample_selection_between_space.setEnabled(False)
        self.minimum_sample_size_label.setEnabled(False)
        self.minimum_sample_size_space.setEnabled(False)


    def is_too_noisy(self, start, end): # start and end are in time

        from gui import PALMS
        end = min(end, PALMS.get().from_sample_to_time(len(PALMS.get().ECG_DATA)-1))

        minimum_sample_size = int(self.minimum_sample_size_space.text()) # in time
        maximum_noise = (end-start)-minimum_sample_size

        # when for other reason sample is not long enough (for example if it is at the end of the signal)
        if ((end-start) < minimum_sample_size):
            return True

        # algorithm acts on each non-noisy interval. From noise indexes, get them (in seconds)
        noise_start_points = NoisePartitions.all_startpoints()
        noise_end_points = NoisePartitions.all_endpoints()

        noise_time = 0
        for noise_start, noise_end in zip(noise_start_points, noise_end_points):
            if (noise_start > start and noise_start < end): # some noise starts in the sample
                if (noise_end < end): # noise starts and finishes in the sample
                    noise_length = (noise_end-noise_start)
                    noise_time += noise_length
                else: # noise starts in the sample and goes until the end of it
                    noise_length = (end-noise_start)
                    noise_time += noise_length

            elif (noise_end > start and noise_end < end): # some noise ends in the sample (this means it started before the sample)
                noise_length = (noise_end-start)
                noise_time += noise_length

            # all the sampe is noise:
            if (noise_start < start and noise_end > end):
                noise_length = (noise_end-noise_start)
                noise_time += noise_length


        if (noise_time > maximum_noise):
            return True
        else:
            return False