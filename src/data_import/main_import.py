
import copy
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QAction, QMenu, QPushButton, QMessageBox, QDesktopWidget, QFileDialog, QDialog
from data_import.import_data import ImportData
from data_import.split_files import SplitFiles
from qtpy.QtCore import Slot, Signal
from qtpy import QtCore, QtGui, QtWidgets
import pandas as pd
import numpy as np
import datetime as dtime
import pyedflib as pyedflib
#import modin.pandas as modin_pandas
from pyecg import ECGRecord
#from numba import jit
from config.config import ICON_PATH


class MyMainImport(QDialog):
    
    def __init__(self, palms):
        super().__init__()
        
        self.initUI(palms=palms)

        # Get the desktop widget
        desktop = QApplication.desktop()

        # Get the screen height
        screen_height = desktop.screenGeometry().height()

        # Calculate the new height as 80% of the screen height
        new_height = int(screen_height * 0.8)

        self.setWindowIcon(QtGui.QIcon(str(ICON_PATH)))
        
        self.resize(850, new_height)  # Set the window size (width, height)
        self.move(QDesktopWidget().availableGeometry().center() - self.rect().center())  # Set the starting position of the window (x, y)

        # Set the fixed size of the window
        self.setFixedSize(850, new_height)


    def initUI(self, palms):
        self.clickIndex = 0
        self.palms = palms

        self.palms.START_INDEXES = np.array([], dtype="int32")
        self.palms.END_INDEXES = np.array([], dtype="int32")
        self.palms.START_MISSING_INDEXES = np.array([], dtype="int32")
        self.palms.END_MISSING_INDEXES = np.array([], dtype="int32")
        self.palms.threshold_outliers = np.array([], dtype="int32")
        self.palms.fiducials = np.array([], dtype="int32")
        self.palms.rr_intervals = np.array([], dtype="int32")

        # Create a menu
        self.button = QPushButton("Choose a different import option")
        self.button.clicked.connect(self.open_menu)

        # central widget
        self.widget = ImportData()
        central_widget = QWidget()

        # create layout and add components
        self.lay = QVBoxLayout(central_widget)
        self.lay.addWidget(self.button)
        self.setLayout(self.lay)

        self.lay.addWidget(self.widget)

        buttonText="Import file"
        self.import_button = QPushButton(buttonText)
        self.import_button.setStyleSheet("background-color: blue; color: white")
        self.import_button.setFixedHeight(20)
        self.import_button.clicked.connect(lambda: self.clickButton())

        self.lay.addWidget(self.import_button)

    def open_menu(self):
        menu = QMenu(self)
        # Create sub-actions for the menu
        action1 = QAction("Open file", self)
        action2 = QAction("Open multiple files", self)
        action3 = QAction("Load analysis", self)
        action4 = QAction("Split file", self)

        # Connect the sub-actions to a common slot
        action1.triggered.connect(lambda: self.changeContent(0))
        action2.triggered.connect(lambda: self.changeContent(1))
        action3.triggered.connect(lambda: self.changeContent(2))
        action4.triggered.connect(lambda: self.changeContent(3))

        # Add sub-actions to the menu
        menu.addAction(action1)
        menu.addAction(action2)
        menu.addAction(action3)
        menu.addAction(action4)

        selected_action = menu.exec_(self.button.mapToGlobal(self.button.rect().bottomLeft()))



    def changeContent(self, content):
        try:
            self.lay.removeWidget(self.widget)
            self.lay.removeWidget(self.import_button)
            self.widget.deleteLater()
            self.import_button.deleteLater()
        except:
            pass
        # Create a central widget
        if (content == 0):
            self.widget = ImportData()
            buttonText="Import file"
            self.clickIndex = 0
        elif (content == 1):
            self.widget = ImportData(True)
            buttonText="Import files"
            self.clickIndex = 1
            # multiple files
        elif (content == 2):
            self.show_load_file()
            buttonText="Import file"
            self.clickIndex = 2
            self.widget = ImportData()
            # load 
        elif (content == 3):
            self.widget = SplitFiles(self)
            buttonText="Split file"
            self.clickIndex = 3

        self.lay.addWidget(self.widget)

        self.import_button = QPushButton(buttonText)
        self.import_button.setStyleSheet("background-color: blue; color: white")
        self.import_button.setFixedHeight(20)
        self.import_button.clicked.connect(lambda: self.clickButton())
        self.lay.addWidget(self.import_button)

    def clickButton(self):
        self.palms.continue_value = True
        if (self.clickIndex == 0):
            self.closeSingleImport(0)
        elif (self.clickIndex == 1):
            self.closeMultipleImport()
        elif (self.clickIndex == 2):
            pass
        elif (self.clickIndex == 3):
            self.split_file()


    def closeMultipleImport(self):
        
        for current_index in range(len(self.widget.currentPaths)):
            if (self.widget.file_type_combo.currentText() not in ["edf", "hea", "fit", "ecg"] and self.widget.w_list[current_index].time_units_combo.currentText().lower() == "none"):
                error_message = "Data is not correct"
                QMessageBox.critical(None, "Error", "For a multiple import, you must specify ms, seconds or datetime", QMessageBox.Ok)
                break
            else:
                self.closeSingleImport(current_index)


    def closeSingleImport(self, index):

        # Create and show the "Loading data" message box
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading")
        loading_box.setText("Loading data...")
        loading_box.show()
        
        try: 
            path = self.widget.currentPaths[index]
            ecg_type = self.widget.w_list[index].data_type_combo.currentIndex()
            interest_column = self.widget.w_list[index].data_column_space.text()

            if (self.widget.file_type_combo.currentText() == "edf"):
                # Open the EDF file
                # f = pyedflib.EdfReader(path)

                # Read the ECG signal
                ecg_signal, signal_headers, header = pyedflib.highlevel.read_edf(path, ch_names=interest_column)
                ecg_signal = np.array(ecg_signal[0])
                if self.widget.w_list[index].data_units_combo.currentIndex() == 1 and ecg_type == 1: # rr and ms
                    subset = ecg_signal[:100]  # Take the first 100 elements of the array
                    limit = np.any(subset < 4)

                    if limit:
                        msgBox = QMessageBox()
                        msgBox.setIcon(QMessageBox.Question)
                        msgBox.setText("The data units is set to miliseconds, but some values are low. Do you want to switch to seconds?")
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        result = msgBox.exec_()
                    
                        if result:
                            ecg_signal  = ecg_signal/1000
                    else:
                        ecg_signal  = ecg_signal/1000

                elif self.widget.w_list[index].data_units_combo.currentIndex() == 0 and ecg_type == 1: # rr and s
                    subset = ecg_signal[:100]  # Take the first 100 elements of the array
                    limit = np.any(subset > 60)

                    if limit:
                        msgBox = QMessageBox()
                        msgBox.setIcon(QMessageBox.Question)
                        msgBox.setText("The data units is set to seconds, but some values are high. Do you want to switch to miliseconds?")
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        result = msgBox.exec_()
                    
                        if result:
                            ecg_signal  = ecg_signal/1000
                try: 
                    frequency = signal_headers[0]["sample_frequency"]
                    first_format_value = self.convert_one_to_time_format(0.0, "s")[0]
                    last_time = len(ecg_signal)/frequency
                    last_format_value = self.convert_one_to_time_format(last_time, "s")[0]
                except:
                    frequency, format_time_values, first_format_value, last_format_value = self.getSingleFrequency(index, len(ecg_signal))
                
                self.first_timestamp = 0

                # Close the EDF file
                #timeValues = np.arange(0, 600, 1/int(frequency))
                #f.close()
                if (index == 0):
                    # the global seconds values are compared to the minimum. The difference 
                    self.palms.CURRENT_FILE = self.widget.currentPaths[0]
                    self.palms.FREQUENCY = round(frequency)
                    self.palms.ECG_DATA = ecg_signal
                    self.palms.DATA_TYPE = ecg_type
                    if ecg_type == 1:
                        self.palms.RR_ONLY = True
                        self.palms.FREQUENCY = 100
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(sum(ecg_signal))*100)
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(sum(ecg_signal))*100)
                    else:
                        self.palms.RR_ONLY = False
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(len(ecg_signal)-1))
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(len(ecg_signal)-1))
                    self.palms.FIRST_DATETIME = first_format_value
                    self.palms.LAST_DATETIME = last_format_value
                    try: 
                        if self.first_timestamp != 0:
                            self.palms.ORIGINAL_DATETIME = self.first_timestamp
                    except:
                        pass
                    #self.palms.TIME_DATA = format_time_values
                    #self.palms.BEAT_DETECTION = self.widget.detection_option.currentIndex()
                    
                else:
                    # Get the previous saved signal and update it with the new one
                    # Determine the start and end times for the concatenated signal
                    previous_data = self.palms.ECG_DATA
                    # new_data is ecg_signal

                    # get last timestep of previous and new timestep of new
                    last_timestep = self.palms.LAST_DATETIME

                    new_first_timestep = first_format_value
                    new_last_timestep = last_format_value

                    # Determine the time duration between the end of signal 1 and the start of signal 2
                    time_duration = dtime.datetime.strptime(new_first_timestep, "%d--%H:%M:%S") - dtime.datetime.strptime(last_timestep, "%d--%H:%M:%S")

                    # Calculate the number of zeros needed based on the time duration
                    
                    if ecg_type == 1:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * 100)
                    else:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * frequency)
                    

                    # Create an array of zeros with the desired length
                    zero_array = np.zeros(num_zeros)

                    combined_voltage = None
                    new_start_index = None
                    new_end_index = None
                    
                    # add new indexes adding duration of next signal
                    combined_voltage = np.concatenate((previous_data, zero_array, ecg_signal))

                    if ecg_type == 1:
                        new_start_index = int((sum(previous_data)*100)+len(zero_array))
                        
                        new_end_index = int(new_start_index+((sum(ecg_signal))*100))
                    else:
                        new_start_index = len(previous_data)+len(zero_array)
                        
                        new_end_index = new_start_index+len(ecg_signal)-1
                    
                    

                    #midle_time_values = self.generate_timestamps_from_start_end(self.palms.LAST_DATETIME, new_first_timestep, num_zeros)
                    
                    # update timesteps which are the last ones
                    self.palms.LAST_DATETIME = new_last_timestep
                    
                    # update palms
                    self.palms.ECG_DATA = combined_voltage
                    self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(new_start_index))
                    self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(new_end_index))
                    self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(new_start_index))
                    self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(new_end_index))
                    #self.palms.TIME_DATA = np.concatenate(self.palms.TIME_DATA, midle_time_values, format_time_values)
                    # sort indexes
                
                
                if (self.clickIndex == 0 or (self.clickIndex == 1 and index+1==len(self.widget.currentPaths))):
                    loading_box.close()
                    self.close()

            elif (self.widget.file_type_combo.currentText() == "fit"):
                # Open the EDF file
                import fitparse
                data_labels = []
            
                with fitparse.FitFile(path) as fitfile:
                    for record in fitfile.get_messages():
                            for data_message in record:
                                if hasattr(data_message, "value"):
                                    data_labels.append(data_message.name)

                    data_name= interest_column
                    frequencyColumn = self.widget.w_list[index].time_index_space.text()
                    frequency_name= frequencyColumn

                    ecg_signal = np.array(fitfile.get_messages(name=data_name))
                    if self.widget.w_list[index].data_units_combo.currentIndex() == 1 and ecg_type == 1: # rr and ms
                        subset = ecg_signal[:100]  # Take the first 100 elements of the array
                        limit = np.any(subset < 4)

                        if limit:
                            msgBox = QMessageBox()
                            msgBox.setIcon(QMessageBox.Question)
                            msgBox.setText("The data units is set to miliseconds, but some values are low. Do you want to switch to seconds?")
                            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                            result = msgBox.exec_()
                    
                            if result:
                                ecg_signal  = ecg_signal/1000
                        else:
                            ecg_signal  = ecg_signal/1000

                    elif self.widget.w_list[index].data_units_combo.currentIndex() == 0 and ecg_type == 1: # rr and s
                        subset = ecg_signal[:100]  # Take the first 100 elements of the array
                        limit = np.any(subset > 60)

                        if limit:
                            msgBox = QMessageBox()
                            msgBox.setIcon(QMessageBox.Question)
                            msgBox.setText("The data units is set to seconds, but some values are high. Do you want to switch to miliseconds?")
                            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                            result = msgBox.exec_()
                    
                            if result:
                                ecg_signal  = ecg_signal/1000
                    try:
                        self.first_timestamp = fitfile.get_messages(name=frequency_name)[0]
                    except:
                        self.first_timestamp = 0
                    
                try:
                    frequency, format_time_values, first_format_value, last_format_value = self.getFrequencyByName(index, len(ecg_signal), frequency_name)
                except:
                    frequency, format_time_values, first_format_value, last_format_value = self.getSingleFrequency(index, len(ecg_signal))
    
                if (index == 0):
                    # the global seconds values are compared to the minimum. The difference 
                    self.palms.CURRENT_FILE = self.widget.currentPaths[0]
                    self.palms.FREQUENCY = round(frequency)
                    self.palms.ECG_DATA = ecg_signal
                    self.palms.DATA_TYPE = ecg_type
                    if ecg_type == 1: # rr
                        self.palms.RR_ONLY = True
                        self.palms.FREQUENCY = 100
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(sum(ecg_signal)*100)-1)
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(sum(ecg_signal)*100)-1)
                    else:
                        self.palms.RR_ONLY = False
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(len(ecg_signal)-1))
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(len(ecg_signal)-1))
                    self.palms.FIRST_DATETIME = first_format_value
                    self.palms.LAST_DATETIME = last_format_value
                    try: 
                        if self.first_timestamp != 0:
                            self.palms.ORIGINAL_DATETIME = self.first_timestamp
                    except:
                        pass
                    #self.palms.TIME_DATA = format_time_values
                    #self.palms.BEAT_DETECTION = self.widget.detection_option.currentIndex()
                    
                else:
                    # Get the previous saved signal and update it with the new one
                    # Determine the start and end times for the concatenated signal
                    previous_data = self.palms.ECG_DATA
                    # new_data is ecg_signal

                    # get last timestep of previous and new timestep of new
                    last_timestep = self.palms.LAST_DATETIME

                    new_first_timestep = first_format_value
                    new_last_timestep = last_format_value

                    # Determine the time duration between the end of signal 1 and the start of signal 2
                    time_duration = dtime.datetime.strptime(new_first_timestep, "%d--%H:%M:%S") - dtime.datetime.strptime(last_timestep, "%d--%H:%M:%S")

                    # Calculate the number of zeros needed based on the time duration
                    
                    if ecg_type == 1:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * 100)
                    else:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * frequency)
                    

                    # Create an array of zeros with the desired length
                    zero_array = np.zeros(num_zeros)

                    combined_voltage = None
                    new_start_index = None
                    new_end_index = None
                    
                    # add new indexes adding duration of next signal
                    combined_voltage = np.concatenate((previous_data, zero_array, ecg_signal))

                    if ecg_type == 1:
                        new_start_index = int((sum(previous_data)*100)+len(zero_array))
                        
                        new_end_index = int(new_start_index+((sum(ecg_signal))*100))
                    else:
                        new_start_index = len(previous_data)+len(zero_array)
                        
                        new_end_index = new_start_index+len(ecg_signal)-1
                    
                    

                    #midle_time_values = self.generate_timestamps_from_start_end(self.palms.LAST_DATETIME, new_first_timestep, num_zeros)
                    
                    # update timesteps which are the last ones
                    self.palms.LAST_DATETIME = new_last_timestep
                    
                    # update palms
                    self.palms.ECG_DATA = combined_voltage
                    self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(new_start_index))
                    self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(new_end_index))
                    self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(new_start_index))
                    self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(new_end_index))
                    #self.palms.TIME_DATA = np.concatenate(self.palms.TIME_DATA, midle_time_values, format_time_values)
                    # sort indexes
                
                
                if (self.clickIndex == 0 or (self.clickIndex == 1 and index+1==len(self.widget.currentPaths))):
                    loading_box.close()
                    self.close()


            elif (self.widget.file_type_combo.currentText() == "hea"):
                # Open the EDF file
                record = ECGRecord.from_wfdb(path)
                frequency = record.time.fs
                self.widget.w_list[index].time_units_combo.currentText().setText("Datetime")
                self.widget.w_list[index].time_format_combo.currentText().setText("s")
                try:
                    self.first_timestamp = record.time.samples[0]
                except:
                    self.first_timestamp = 0
                ecg_signal = np.array(record.get_lead(interest_column))
                if self.widget.w_list[index].data_units_combo.currentIndex() == 1 and ecg_type == 1: # rr and ms
                    subset = ecg_signal[:100]  # Take the first 100 elements of the array
                    limit = np.any(subset < 4)

                    if limit:
                        msgBox = QMessageBox()
                        msgBox.setIcon(QMessageBox.Question)
                        msgBox.setText("The data units is set to miliseconds, but some values are low. Do you want to switch to seconds?")
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        result = msgBox.exec_()
                    
                        if result:
                            ecg_signal  = ecg_signal/1000
                    else:
                        ecg_signal  = ecg_signal/1000

                elif self.widget.w_list[index].data_units_combo.currentIndex() == 0 and ecg_type == 1: # rr and s
                    subset = ecg_signal[:100]  # Take the first 100 elements of the array
                    limit = np.any(subset > 60)

                    if limit:
                        msgBox = QMessageBox()
                        msgBox.setIcon(QMessageBox.Question)
                        msgBox.setText("The data units is set to seconds, but some values are high. Do you want to switch to miliseconds?")
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        result = msgBox.exec_()
                    
                        if result:
                            ecg_signal  = ecg_signal/1000

                frequency, format_time_values, first_format_value, last_format_value = self.getSingleFrequency(index, len(ecg_signal))

    
                if (index == 0):
                    # the global seconds values are compared to the minimum. The difference 
                    self.palms.CURRENT_FILE = self.widget.currentPaths[0]
                    self.palms.FREQUENCY = round(frequency)
                    self.palms.ECG_DATA = ecg_signal
                    self.palms.DATA_TYPE = ecg_type
                    if ecg_type == 1:
                        self.palms.RR_ONLY = True
                        self.palms.FREQUENCY = 100
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(sum(ecg_signal))*100)
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(sum(ecg_signal))*100)
                    else:
                        self.palms.RR_ONLY = False
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(len(ecg_signal)-1))
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(len(ecg_signal)-1))
                    self.palms.FIRST_DATETIME = first_format_value
                    self.palms.LAST_DATETIME = last_format_value
                    try: 
                        if self.first_timestamp != 0:
                            self.palms.ORIGINAL_DATETIME = self.first_timestamp
                    except:
                        pass
                    #self.palms.TIME_DATA = format_time_values
                    #self.palms.BEAT_DETECTION = self.widget.detection_option.currentIndex()
                    
                else:
                    # Get the previous saved signal and update it with the new one
                    # Determine the start and end times for the concatenated signal
                    previous_data = self.palms.ECG_DATA
                    # new_data is ecg_signal

                    # get last timestep of previous and new timestep of new
                    last_timestep = self.palms.LAST_DATETIME

                    new_first_timestep = first_format_value
                    new_last_timestep = last_format_value

                    # Determine the time duration between the end of signal 1 and the start of signal 2
                    time_duration = dtime.datetime.strptime(new_first_timestep, "%d--%H:%M:%S") - dtime.datetime.strptime(last_timestep, "%d--%H:%M:%S")

                    # Calculate the number of zeros needed based on the time duration
                    
                    if ecg_type == 1:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * 100)
                    else:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * frequency)
                    

                    # Create an array of zeros with the desired length
                    zero_array = np.zeros(num_zeros)

                    combined_voltage = None
                    new_start_index = None
                    new_end_index = None
                    
                    # add new indexes adding duration of next signal
                    combined_voltage = np.concatenate((previous_data, zero_array, ecg_signal))

                    if ecg_type == 1:
                        new_start_index = int((sum(previous_data)*100)+len(zero_array))
                        
                        new_end_index = int(new_start_index+((sum(ecg_signal))*100))
                    else:
                        new_start_index = len(previous_data)+len(zero_array)
                        
                        new_end_index = new_start_index+len(ecg_signal)-1
                    
                    

                    #midle_time_values = self.generate_timestamps_from_start_end(self.palms.LAST_DATETIME, new_first_timestep, num_zeros)
                    
                    # update timesteps which are the last ones
                    self.palms.LAST_DATETIME = new_last_timestep
                    
                    # update palms
                    self.palms.ECG_DATA = combined_voltage
                    self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(new_start_index))
                    self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(new_end_index))
                    self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(new_start_index))
                    self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(new_end_index))
                    #self.palms.TIME_DATA = np.concatenate(self.palms.TIME_DATA, midle_time_values, format_time_values)
                    # sort indexes
                
                
                if (self.clickIndex == 0 or (self.clickIndex == 1 and index+1==len(self.widget.currentPaths))):
                    loading_box.close()
                    self.close()


            elif (self.widget.file_type_combo.currentText() == "ecg"):
                # Open the EDF file
                record = ECGRecord.from_ishine(path)
                frequency = record.time.fs
                self.widget.w_list[index].time_units_combo.currentText().setText("Datetime")
                self.widget.w_list[index].time_format_combo.currentText().setText("s")
                try:
                    self.first_timestamp = record.time.samples[0]
                except:
                    self.first_timestamp = 0
                
                ecg_signal = np.array(record.get_lead(interest_column))
                if self.widget.w_list[index].data_units_combo.currentIndex() == 1 and ecg_type == 1: # rr and ms
                    subset = ecg_signal[:100]  # Take the first 100 elements of the array
                    limit = np.any(subset < 4)

                    if limit:
                        msgBox = QMessageBox()
                        msgBox.setIcon(QMessageBox.Question)
                        msgBox.setText("The data units is set to miliseconds, but some values are low. Do you want to switch to seconds?")
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        result = msgBox.exec_()
                    
                        if result:
                            ecg_signal  = ecg_signal/1000
                    else:
                        ecg_signal  = ecg_signal/1000

                elif self.widget.w_list[index].data_units_combo.currentIndex() == 0 and ecg_type == 1: # rr and s
                    subset = ecg_signal[:100]  # Take the first 100 elements of the array
                    limit = np.any(subset > 60)

                    if limit:
                        msgBox = QMessageBox()
                        msgBox.setIcon(QMessageBox.Question)
                        msgBox.setText("The data units is set to seconds, but some values are high. Do you want to switch to miliseconds?")
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        result = msgBox.exec_()
                    
                        if result:
                            ecg_signal  = ecg_signal/1000

                frequency, format_time_values, first_format_value, last_format_value = self.getSingleFrequency(index, len(ecg_signal))

    
                if (index == 0):
                    # the global seconds values are compared to the minimum. The difference 
                    self.palms.CURRENT_FILE = self.widget.currentPaths[0]
                    self.palms.FREQUENCY = round(frequency)
                    self.palms.ECG_DATA = ecg_signal
                    self.palms.DATA_TYPE = ecg_type
                    if ecg_type == 1:
                        self.palms.RR_ONLY = True
                        self.palms.FREQUENCY = 100
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(sum(ecg_signal))*100)
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(sum(ecg_signal)*100))
                    else:
                        self.palms.RR_ONLY = False
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(len(ecg_signal)-1))
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(len(ecg_signal)-1))
                    self.palms.FIRST_DATETIME = first_format_value
                    self.palms.LAST_DATETIME = last_format_value
                    try: 
                        if self.first_timestamp != 0:
                            self.palms.ORIGINAL_DATETIME = self.first_timestamp
                    except:
                        pass
                    #self.palms.TIME_DATA = format_time_values
                    #self.palms.BEAT_DETECTION = self.widget.detection_option.currentIndex()
                    
                else:
                    # Get the previous saved signal and update it with the new one
                    # Determine the start and end times for the concatenated signal
                    previous_data = self.palms.ECG_DATA
                    # new_data is ecg_signal

                    # get last timestep of previous and new timestep of new
                    last_timestep = self.palms.LAST_DATETIME

                    new_first_timestep = first_format_value
                    new_last_timestep = last_format_value

                    # Determine the time duration between the end of signal 1 and the start of signal 2
                    time_duration = dtime.datetime.strptime(new_first_timestep, "%d--%H:%M:%S") - dtime.datetime.strptime(last_timestep, "%d--%H:%M:%S")

                    # Calculate the number of zeros needed based on the time duration
                    
                    if ecg_type == 1:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * 100)
                    else:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * frequency)
                    

                    # Create an array of zeros with the desired length
                    zero_array = np.zeros(num_zeros)

                    combined_voltage = None
                    new_start_index = None
                    new_end_index = None
                    
                    # add new indexes adding duration of next signal
                    combined_voltage = np.concatenate((previous_data, zero_array, ecg_signal))

                    if ecg_type == 1:
                        new_start_index = int((sum(previous_data)*100)+len(zero_array))
                        
                        new_end_index = int(new_start_index+((sum(ecg_signal))*100))
                    else:
                        new_start_index = len(previous_data)+len(zero_array)
                        
                        new_end_index = new_start_index+len(ecg_signal)-1
                    
                    

                    #midle_time_values = self.generate_timestamps_from_start_end(self.palms.LAST_DATETIME, new_first_timestep, num_zeros)
                    
                    # update timesteps which are the last ones
                    self.palms.LAST_DATETIME = new_last_timestep
                    
                    # update palms
                    self.palms.ECG_DATA = combined_voltage
                    self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(new_start_index))
                    self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(new_end_index))
                    self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(new_start_index))
                    self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(new_end_index))
                    #self.palms.TIME_DATA = np.concatenate(self.palms.TIME_DATA, midle_time_values, format_time_values)
                    # sort indexes
                
                
                if (self.clickIndex == 0 or (self.clickIndex == 1 and index+1==len(self.widget.currentPaths))):
                    loading_box.close()
                    self.close()


            elif (self.widget.file_type_combo.currentText() == "mat"):
                # Open the EDF file
                import h5py
                with h5py.File(path, 'r') as file:
                    file_names = file.keys()
                    data_name = interest_column
                    time_name = time_name
                    frequencyColumn = self.widget.w_list[index].time_index_space.text()
                    
                    ecg_signal = np.array(file[data_name])
                    if self.widget.w_list[index].data_units_combo.currentIndex() == 1 and ecg_type == 1: # rr and ms
                        subset = ecg_signal[:100]  # Take the first 100 elements of the array
                        limit = np.any(subset < 4)

                        if limit:
                            msgBox = QMessageBox()
                            msgBox.setIcon(QMessageBox.Question)
                            msgBox.setText("The data units is set to miliseconds, but some values are low. Do you want to switch to seconds?")
                            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                            result = msgBox.exec_()
                    
                            if result:
                                ecg_signal  = ecg_signal/1000
                        else:
                            ecg_signal  = ecg_signal/1000

                    elif self.widget.w_list[index].data_units_combo.currentIndex() == 0 and ecg_type == 1: # rr and s
                        subset = ecg_signal[:100]  # Take the first 100 elements of the array
                        limit = np.any(subset > 60)

                        if limit:
                            msgBox = QMessageBox()
                            msgBox.setIcon(QMessageBox.Question)
                            msgBox.setText("The data units is set to seconds, but some values are high. Do you want to switch to miliseconds?")
                            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                            msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                            result = msgBox.exec_()
                    
                            if result:
                                ecg_signal  = ecg_signal/1000
                    try:
                        frequency_name= data_labels[int(frequencyColumn)-1]
                        self.first_timestamp = file[frequency_name][0]
                    except:
                        self.first_timestamp = 0

                try: 
                    frequency, format_time_values, first_format_value, last_format_value = self.getFrequencyByName(index, len(ecg_signal), frequency_name)
                except:
                    frequency, format_time_values, first_format_value, last_format_value = self.getSingleFrequency(index, len(ecg_signal))
    
                if (index == 0):
                    # the global seconds values are compared to the minimum. The difference 
                    self.palms.CURRENT_FILE = self.widget.currentPaths[0]
                    self.palms.FREQUENCY = round(frequency)
                    self.palms.ECG_DATA = ecg_signal
                    self.palms.DATA_TYPE = ecg_type
                    if ecg_type == 1:
                        self.palms.RR_ONLY = True
                        self.palms.FREQUENCY = 100
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(sum(ecg_signal)))
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(sum(ecg_signal))*100)
                    else:
                        self.palms.RR_ONLY = False
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(len(ecg_signal)-1))
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(len(ecg_signal)-1))
                    self.palms.FIRST_DATETIME = first_format_value
                    self.palms.LAST_DATETIME = last_format_value
                    try: 
                        if self.first_timestamp != 0:
                            self.palms.ORIGINAL_DATETIME = self.first_timestamp
                    except:
                        pass
                    #self.palms.TIME_DATA = format_time_values
                    #self.palms.BEAT_DETECTION = self.widget.detection_option.currentIndex()
                    
                else:
                    # Get the previous saved signal and update it with the new one
                    # Determine the start and end times for the concatenated signal
                    previous_data = self.palms.ECG_DATA
                    # new_data is ecg_signal

                    # get last timestep of previous and new timestep of new
                    last_timestep = self.palms.LAST_DATETIME

                    new_first_timestep = first_format_value
                    new_last_timestep = last_format_value

                    # Determine the time duration between the end of signal 1 and the start of signal 2
                    time_duration = dtime.datetime.strptime(new_first_timestep, "%d--%H:%M:%S") - dtime.datetime.strptime(last_timestep, "%d--%H:%M:%S")

                    # Calculate the number of zeros needed based on the time duration
                    
                    if ecg_type == 1:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * 100)
                    else:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * frequency)
                    

                    # Create an array of zeros with the desired length
                    zero_array = np.zeros(num_zeros)

                    combined_voltage = None
                    new_start_index = None
                    new_end_index = None
                    
                    # add new indexes adding duration of next signal
                    combined_voltage = np.concatenate((previous_data, zero_array, ecg_signal))

                    if ecg_type == 1:
                        new_start_index = int((sum(previous_data)*100)+len(zero_array))
                        
                        new_end_index = int(new_start_index+((sum(ecg_signal))*100))
                    else:
                        new_start_index = len(previous_data)+len(zero_array)
                        
                        new_end_index = new_start_index+len(ecg_signal)-1
                    
                    

                    #midle_time_values = self.generate_timestamps_from_start_end(self.palms.LAST_DATETIME, new_first_timestep, num_zeros)
                    
                    # update timesteps which are the last ones
                    self.palms.LAST_DATETIME = new_last_timestep
                    
                    # update palms
                    self.palms.ECG_DATA = combined_voltage
                    self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(new_start_index))
                    self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(new_end_index))
                    self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(new_start_index))
                    self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(new_end_index))
                    #self.palms.TIME_DATA = np.concatenate(self.palms.TIME_DATA, midle_time_values, format_time_values)
                    # sort indexes
                
                
                if (self.clickIndex == 0 or (self.clickIndex == 1 and index+1==len(self.widget.currentPaths))):
                    loading_box.close()
                    self.close()


            else: # csv, txt and dat
                separator = self.widget.w_list[index].column_separator_combo.currentText()
                header_lines = self.widget.w_list[index].header_lines_space.text()
                

                delimiter = ""
                if (separator == "Semicolon"):
                    delimiter = ";"
                elif (separator == "Comma"):
                    delimiter = ","
                elif (separator == "Space"):
                    delimiter = " "
                elif (separator == "Tab"):
                    delimiter = "|"
                else:
                    delimiter = "/"
                
                # Check: that I can read the file, that frequency/time are correct
                txt_data = pd.read_csv(path, usecols=[int(interest_column)-1], header=None, sep=delimiter, engine="c")
            
                #ecg = txt_data.iloc[:, int(interest_column)-1].values
                ecg = np.array(txt_data.iloc[:, 0].values)[int(header_lines):].astype("float32")
                if self.widget.w_list[index].data_units_combo.currentIndex() == 1 and ecg_type == 1: # rr and ms
                    subset = ecg[:100]  # Take the first 100 elements of the array
                    limit = np.any(subset < 4)

                    if limit:
                        msgBox = QMessageBox()
                        msgBox.setIcon(QMessageBox.Question)
                        msgBox.setText("The data units is set to miliseconds, but some values are low. Do you want to switch to seconds?")
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        result = msgBox.exec_()
                    
                        if result:
                            ecg  = ecg/1000
                    else:
                        ecg  = ecg/1000

                elif self.widget.w_list[index].data_units_combo.currentIndex() == 0 and ecg_type == 1: # rr and s
                    subset = ecg[:100]  # Take the first 100 elements of the array
                    limit = np.any(subset > 60)

                    if limit:
                        msgBox = QMessageBox()
                        msgBox.setIcon(QMessageBox.Question)
                        msgBox.setText("The data units is set to seconds, but some values are high. Do you want to switch to miliseconds?")
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                        result = msgBox.exec_()
                    
                        if result:
                            ecg  = ecg/1000

                # if datetime, change to seconds. Change with np.datetime64
                frequency, format_time_values, first_format_value, last_format_value = self.getSingleFrequency(index, len(ecg))

                if format_time_values != []:
                    self.first_timestamp = format_time_values[0]
                
            
                if (index == 0):
                    # the global seconds values are compared to the minimum. The difference 
                    self.palms.CURRENT_FILE = self.widget.currentPaths[0]
                    self.palms.FREQUENCY = round(frequency)
                    self.palms.ECG_DATA = ecg
                    self.palms.DATA_TYPE = ecg_type
                    if ecg_type == 1:
                        self.palms.RR_ONLY = True
                        self.palms.FREQUENCY = 100
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(sum(ecg)))
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int((sum(ecg))*100))
                    else:
                        self.palms.RR_ONLY = False
                        self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(0))
                        self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(len(ecg)-1))
                        self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(0))
                        self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(len(ecg)-1))
                    self.palms.FIRST_DATETIME = first_format_value
                    self.palms.LAST_DATETIME = last_format_value
                    try: 
                        if self.first_timestamp != 0:
                            self.palms.ORIGINAL_DATETIME = self.first_timestamp
                    except:
                        pass
                    #self.palms.TIME_DATA = format_time_values
                    #self.palms.BEAT_DETECTION = self.widget.detection_option.currentIndex()
                    
                else:
                    # Get the previous saved signal and update it with the new one
                    # Determine the start and end times for the concatenated signal
                    previous_data = self.palms.ECG_DATA
                    # new_data is ecg_signal

                    # get last timestep of previous and new timestep of new
                    last_timestep = self.palms.LAST_DATETIME

                    new_first_timestep = first_format_value
                    new_last_timestep = last_format_value
                    
                    # Determine the time duration between the end of signal 1 and the start of signal 2
                    
                    time_duration = dtime.datetime.strptime(new_first_timestep, "%d--%H:%M:%S") - dtime.datetime.strptime(last_timestep, "%d--%H:%M:%S")
                    
                    # Calculate the number of zeros needed based on the time duration
                    if ecg_type == 1:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * 100)
                    else:
                        num_zeros = int(pd.Timedelta(time_duration).total_seconds() * frequency)
                    

                    # Create an array of zeros with the desired length
                    zero_array = np.zeros(num_zeros)

                    combined_voltage = None
                    new_start_index = None
                    new_end_index = None
                    
                    # add new indexes adding duration of next signal
                    combined_voltage = np.concatenate((previous_data, zero_array, ecg))

                    if ecg_type == 1:
                        new_start_index = int((sum(previous_data)*100)+len(zero_array))
                        
                        new_end_index = int(new_start_index+((sum(ecg))*100))
                    else:
                        new_start_index = len(previous_data)+len(zero_array)
                        
                        new_end_index = new_start_index+len(ecg)-1
                        
                    

                    #midle_time_values = self.generate_timestamps_from_start_end(self.palms.LAST_DATETIME, new_first_timestep, num_zeros)
                    
                    # update timesteps which are the last ones
                    self.palms.LAST_DATETIME = new_last_timestep
                    
                    # update palms
                    self.palms.ECG_DATA = combined_voltage
                    self.palms.START_INDEXES = np.append(self.palms.START_INDEXES, int(new_start_index))
                    self.palms.END_INDEXES = np.append(self.palms.END_INDEXES, int(new_end_index))
                    self.palms.START_MISSING_INDEXES = np.append(self.palms.START_MISSING_INDEXES, int(new_start_index))
                    self.palms.END_MISSING_INDEXES = np.append(self.palms.END_MISSING_INDEXES, int(new_end_index))
                    #self.palms.TIME_DATA = self.palms.TIME_DATA + midle_time_values + format_time_values
                    # sort indexes

                
                if (self.clickIndex == 0 or (self.clickIndex == 1 and index+1==len(self.widget.currentPaths))):
                    loading_box.close()
                    self.close()

        except Exception as e:
            import traceback
            # Display an error message box
            error_message = "An error has occurred!"
            QMessageBox.critical(None, "Error", str(e), QMessageBox.Ok)
            error_traceback = traceback.format_exc()
            print(error_traceback)


    def getSingleFrequency(self, index, duration): # for csv, txt, dat
        # get the frequency and the global second values
        frequency = None
        if (self.widget.w_list[index].time_units_combo.currentText().lower() == "none"):
            frequency = self.widget.w_list[index].frequency_sampling_space.text()
        else:
            frequencyColumn = self.widget.w_list[index].time_index_space.text()
            if (self.widget.w_list[index].time_units_combo.currentText().lower() == "datetime"):
                dateType = self.widget.w_list[index].time_format_combo.currentText()
            else:
                dateType = self.widget.w_list[index].time_units_combo.currentText().lower()

        df = None
        new_frequency=None
        format_time_values = []

        header_lines = self.widget.w_list[index].header_lines_space.text()
        separator = self.widget.w_list[index].column_separator_combo.currentText()

        delimiter = ""
        if (separator == "Semicolon"):
            delimiter = ";"
        elif (separator == "Comma"):
            delimiter = ","
        elif (separator == "Space"):
            delimiter = " "
        elif (separator == "Tab"):
            delimiter = "|"
        else:
            delimiter = "/"
        
        if frequency is not None:

            new_frequency = float(frequency)

            first_format_value = self.convert_one_to_time_format(0, "s")[0]
            last_time = duration/new_frequency
            last_format_value = self.convert_one_to_time_format(last_time, "s")[0]


        if frequency is None:
            df = pd.read_csv(self.widget.currentPaths[index], nrows=10000, usecols=[int(frequencyColumn)-1], header=None, sep=delimiter, engine="c")
            df_last = pd.read_csv(self.widget.currentPaths[index], skiprows=duration-1, usecols=[int(frequencyColumn)-1], header=None, sep=delimiter, engine="c")
            #time_values = df.iloc[:,int(frequencyColumn)-1]
            time_values_first = df.iloc[:, 0].values[int(header_lines):]
            last_value = df_last.iloc[:, 0].values
            time_values = np.append(time_values_first, last_value)
            new_frequency = 1

            #format_time_values = self.convert_to_time_format(time_values, dateType)
            format_time_values = np.array(time_values)
            del time_values
            
            if (dateType == "ms"):
                format_time_values = format_time_values.astype(int)

            first_format_value = self.convert_one_to_time_format(str(format_time_values[0]), dateType)[0]
            last_format_value = self.convert_one_to_time_format(str(format_time_values[len(format_time_values)-1]), dateType)[0]
            
            if (dateType == "s"):
                if (len(format_time_values) > 10000):
                    new_frequency = self.getFrequency(timeValues=time_values_first[0:10000])
                else:
                    new_frequency = self.getFrequency(timeValues=time_values_first)

            elif(dateType == "ms"):
                if (len(format_time_values) > 10000):
                    new_frequency = self.getFrequency(timeValues=time_values_first[0:min(duration, 10000)]/1000)
                else:
                    new_frequency = self.getFrequency(timeValues=time_values_first/1000)

            else:
                # change datetimeto seconds
                new_time_values = [self.convert_to_seconds(time_value, dateType) for time_value in time_values_first[0:min(duration, 10000)]]
                new_frequency = self.getFrequency(timeValues=new_time_values[0:min(duration, 10000)])
                    

        return float(new_frequency), format_time_values, first_format_value, last_format_value
    

    def getFrequencyByName(self, index, duration, timeColumn): # for fit, 
        # get the frequency and the global second values
        frequency = None
        if (self.widget.w_list[index].time_units_combo.currentText().lower() == "none"):
            frequency = self.widget.w_list[index].frequency_sampling_space.text()
        else:
            frequencyColumn = timeColumn
            if (self.widget.w_list[index].time_units_combo.currentText().lower() == "datetime"):
                dateType = self.widget.w_list[index].time_format_combo.currentText()
            else:
                dateType = self.widget.w_list[index].time_units_combo.currentText().lower()

        df = None
        new_frequency=None
        format_time_values = []

        header_lines = self.widget.w_list[index].header_lines_space.text()
        separator = self.widget.w_list[index].column_separator_combo.currentText()

        delimiter = ""
        if (separator == "Semicolon"):
            delimiter = ";"
        elif (separator == "Comma"):
            delimiter = ","
        elif (separator == "Space"):
            delimiter = " "
        elif (separator == "Tab"):
            delimiter = "|"
        else:
            delimiter = "/"
        
        if frequency is not None:

            new_frequency = float(frequency)

            first_format_value = self.convert_one_to_time_format(0.0, "s")[0]
            last_time = duration/new_frequency
            last_format_value = self.convert_one_to_time_format((last_time), "s")[0]


        if frequency is None:
            import fitparse
            path = self.widget.currentPaths[index]
            with fitparse.FitFile(path) as fitfile:
                time_values = fitfile.get_messages(name=frequencyColumn)
            new_frequency = 1

            #format_time_values = self.convert_to_time_format(time_values, dateType)
            format_time_values = np.array(time_values)
            del time_values
            
            first_format_value = self.convert_one_to_time_format(format_time_values[0], dateType)
            last_format_value = self.convert_one_to_time_format(format_time_values[len(format_time_values)-1], dateType)
            
            if (dateType == "s"):
                if (len(format_time_values) > 10000):
                    new_frequency = self.getFrequency(timeValues=format_time_values[0:10000])
                else:
                    new_frequency = self.getFrequency(timeValues=format_time_values)

            elif(dateType == "ms"):
                if (len(format_time_values) > 10000):
                    new_frequency = self.getFrequency(timeValues=format_time_values[0:10000]/1000)
                else:
                    new_frequency = self.getFrequency(timeValues=format_time_values/1000)

            else:
                # change datetimeto seconds
                if (len(format_time_values) > 100000):
                    new_time_values = [self.convert_to_seconds(time_value, dateType) for time_value in format_time_values[0:100000]]
                    new_frequency = self.getFrequency(timeValues=new_time_values[0:100000])
                    

                else:
                    new_time_values = [self.convert_to_seconds(time_value, dateType) for time_value in format_time_values]
                    new_frequency = self.getFrequency(timeValues=new_time_values)
                    

        return new_frequency, format_time_values, first_format_value[0], last_format_value[0]

    def split_file(self):
        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading")
        loading_box.setText("Split data...")
        loading_box.show()
        
        try:
            
            # Information
            input_file = self.widget.currentPath
            output_prefix = "_split"
            num_files = int(self.widget.w.data_type_combo.currentText())
            
            header_lines = self.widget.w.header_lines_space.text()
            # File type
            if (self.widget.file_type_combo.currentText().lower() == "csv"):
                self.split_csv(input_file=input_file, output_prefix=output_prefix, num_files=num_files, header_lines=header_lines)
            elif (self.widget.file_type_combo.currentText().lower() == "txt"):
                self.split_txt(input_file=input_file, output_prefix=output_prefix, num_files=num_files, header_lines=header_lines)
            elif (self.widget.file_type_combo.currentText().lower() == "dat"):
                self.split_dat(input_file=input_file, output_prefix=output_prefix, num_files=num_files, header_lines=header_lines)
            elif (self.widget.file_type_combo.currentText().lower() == "edf"):
                self.split_edf(input_file=input_file, output_prefix=output_prefix, num_files=num_files)
            elif (self.widget.file_type_combo.currentText().lower() == "fit"):
                self.split_fit(input_file=input_file, output_prefix=output_prefix, num_files=num_files)
            elif (self.widget.file_type_combo.currentText().lower() == "ecg"):
                self.split_ecg(input_file=input_file, output_prefix=output_prefix, num_files=num_files)
            elif (self.widget.file_type_combo.currentText().lower() == "hea"):
                self.split_hea(input_file=input_file, output_prefix=output_prefix, num_files=num_files)
            elif (self.widget.file_type_combo.currentText().lower() == "mat"):
                self.split_mat(input_file=input_file, output_prefix=output_prefix, num_files=num_files)
        except Exception as e:
            # Display an error message box
            error_message = "An error has occurred!"
            QMessageBox.critical(None, "Error", error_message, QMessageBox.Ok)
            print(e)
            import traceback
            error_traceback = traceback.format_exc()
            print(error_traceback)

        loading_box.close()

    def split_csv(self, input_file, output_prefix, num_files, header_lines):
        # Read the input CSV file into a pandas DataFrame
        interest_column = self.widget.w.data_column_space.text()
        frequency_column = self.widget.w.time_index_space.text()
        separator = self.widget.w.column_separator_combo.currentText()

        delimiter = ""
        if (separator == "Semicolon"):
            delimiter = ";"
        elif (separator == "Comma"):
            delimiter = ","
        elif (separator == "Space"):
            delimiter = " "
        elif (separator == "Tab"):
            delimiter = "|"
        else:
            delimiter = "/"

        if frequency_column != "":
            df = pd.read_csv(input_file, delimiter=delimiter, usecols=[int(interest_column)-1, int(frequency_column)-1], header=None, engine="c")
            #df = df[df.columns[int(interest_column)-1, int(frequency_column)-1]]
        else:
            df = pd.read_csv(input_file, delimiter=delimiter, usecols=[int(interest_column)-1], header=None, engine="c")
            #df = df[df.columns[int(interest_column)-1]]
        
        #heading_part = df[:int(header_lines)]
        # Calculate the number of files needed based on rows_per_file
        parts = np.array_split(df[:, 0].values, int(num_files))
        input_file = input_file.rstrip(".csv")
        # Create new CSV files for each chunk with specified headers
        for i, chunk in enumerate(parts):
            output_file = input_file + output_prefix + "_" + str(i+1) + ".csv"
            chunk.to_csv(output_file, index=False, header=df.head)

        msg = QMessageBox()
        msg.setWindowTitle("Action Completed")
        msg.setText("The action has been completed.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

        self.changeContent(0)

    def split_dat(self, input_file, output_prefix, num_files, header_lines):
        # Read the input CSV file into a pandas DataFrame
        interest_column = self.widget.w.data_column_space.text()
        frequency_column = self.widget.w.time_index_space.text()
        separator = self.widget.w.column_separator_combo.currentText()

        delimiter = ""
        if (separator == "Semicolon"):
            delimiter = ";"
        elif (separator == "Comma"):
            delimiter = ","
        elif (separator == "Space"):
            delimiter = " "
        elif (separator == "Tab"):
            delimiter = "|"
        else:
            delimiter = "/"

        if frequency_column != "":
            df = pd.read_csv(input_file, delimiter=delimiter, usecols=[int(interest_column)-1, int(frequency_column)-1], header=None, engine="c")
            #df = df[df.columns[int(interest_column)-1, int(frequency_column)-1]]
        else:
            df = pd.read_csv(input_file, delimiter=delimiter, usecols=[int(interest_column)-1], header=None, engine="c")
            #df = df[df.columns[int(interest_column)-1]]
        
        #heading_part = df[:int(header_lines)]
        # Calculate the number of files needed based on rows_per_file
        parts = np.array_split(df[:], int(num_files))
        input_file = input_file.rstrip(".dat")
        # Create new CSV files for each chunk with specified headers
        for i, chunk in enumerate(parts):
            output_file = input_file + output_prefix + "_" + str(i+1) + ".dat"
            chunk.to_csv(output_file, index=False, header=df.head)

        msg = QMessageBox()
        msg.setWindowTitle("Action Completed")
        msg.setText("The action has been completed.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

        self.changeContent(0)

    def split_txt(self, input_file, output_prefix, num_files, header_lines):
        # Read the input CSV file into a pandas DataFrame
        interest_column = self.widget.w.data_column_space.text()
        frequency_column = self.widget.w.time_index_space.text()
        separator = self.widget.w.column_separator_combo.currentText()

        delimiter = ""
        if (separator == "Semicolon"):
            delimiter = ";"
        elif (separator == "Comma"):
            delimiter = ","
        elif (separator == "Space"):
            delimiter = " "
        elif (separator == "Tab"):
            delimiter = "|"
        else:
            delimiter = "/"

        if frequency_column != "":
            df = pd.read_csv(input_file, delimiter=delimiter, usecols=[int(interest_column)-1, int(frequency_column)-1], header=None, engine="c")
            #df = df[df.columns[int(interest_column)-1, int(frequency_column)-1]]
        else:
            df = pd.read_csv(input_file, delimiter=delimiter, usecols=[int(interest_column)-1], header=None, engine="c")
            #df = df[df.columns[int(interest_column)-1]]
        
        #heading_part = df[:int(header_lines)]
        # Calculate the number of files needed based on rows_per_file
        parts = np.array_split(df[:], int(num_files))
        input_file = input_file.rstrip(".txt")
        # Create new CSV files for each chunk with specified headers
        for i, chunk in enumerate(parts):
            output_file = input_file + output_prefix + "_" + str(i+1) + ".txt"
            chunk.to_csv(output_file, index=False, header=df.head)

        msg = QMessageBox()
        msg.setWindowTitle("Action Completed")
        msg.setText("The action has been completed.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

        self.changeContent(0)

    def split_edf(self, input_file, output_prefix, num_files):
        
        # Load the original EDF file
        edf_file = pyedflib.EdfReader(input_file)

        # Determine the total number of samples
        total_samples = edf_file.getNSamples()[0]
        samples_per_part = total_samples // num_files

        # Create new EDF files for each part
        output_file_paths = [(input_file + "_" + output_prefix + str(i) + ".edf") for i in range(1, num_files + 1)]

        edf_file.close()
        interest_column = self.widget.w.data_column_space.text()
        signals, signal_headers, header = pyedflib.highlevel.read_edf(input_file, ch_names=interest_column)
        # Split and write data to each new EDF file
        for i in range(num_files):
            start_sample = i * samples_per_part
            end_sample = (i + 1) * samples_per_part if i < num_files - 1 else total_samples - 1
            
            current_signals = [single_signal[start_sample:end_sample] for single_signal in signals]
            pyedflib.highlevel.write_edf(output_file_paths[i], current_signals, signal_headers, header)

        msg = QMessageBox()
        msg.setWindowTitle("Action Completed")
        msg.setText("The action has been completed.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

        self.changeContent(0)


    def split_fit(self, input_file, output_prefix, num_files):

        import fitparse
        
        # Load the original EDF file
        fitfile = fitparse.FitFile(input_file)

        # Create new .fit files for each part
        output_file_paths = [(input_file + "_" + output_prefix + str(i) + ".fit") for i in range(1, num_files + 1)]
        fit_writers = [fitparse.FitFile(file_path, data_processor=fitfile._processor) for file_path in output_file_paths]

        # Split and write data to each new .fit file
        messages_per_output_file = len(fitfile.messages[interest_column]) // num_files
        interest_column = self.widget.w.data_column_space.text()
        for i in range(num_files):
            start_message = i * messages_per_output_file
            end_message = (i + 1) * messages_per_output_file if i < num_files - 1 else len(fitfile.messages[interest_column])
            fit_writers[i].messages = fitfile.messages[interest_column][start_message:end_message]

        # Close the new .fit files
        for fit_writer in fit_writers:
            fit_writer.close()

        msg = QMessageBox()
        msg.setWindowTitle("Action Completed")
        msg.setText("The action has been completed.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

        self.changeContent(0)


    def split_hea(self, input_file, output_prefix, num_files):

        record = ECGRecord.from_ishine(input_file)
        
        labels = record.lead_names

        output_file_paths = [(input_file + "_" + output_prefix + str(i) + ".hea") for i in range(1, num_files + 1)]
        hea_writers = [ECGRecord() for file in num_files]

        interest_column = self.widget.w.data_column_space.text()
        data = [[] for _ in range(num_files)]

        signal_data = record.get_lead(interest_column)

        data_per_part = len(signal_data) // num_files

        for i in range(num_files):
            start_message = i * data_per_part
            end_message = (i + 1) * data_per_part if i < num_files - 1 else len(signal_data)

            data[i-1].append(signal_data[start_message:end_message])

        current_time = ECGRecord.time

        for i, hea_writer in enumerate(hea_writers):
            hea_writer.from_np_array(output_file_paths[i], current_time, data[i-1], labels)

        
        msg = QMessageBox()
        msg.setWindowTitle("Action Completed")
        msg.setText("The action has been completed.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

        self.changeContent(0)


    def split_ecg(self, input_file, output_prefix, num_files):

        record = ECGRecord.from_ishine(input_file)
        
        labels = record.lead_names

        output_file_paths = [(input_file + "_" + output_prefix + str(i) + ".ecg") for i in range(1, num_files + 1)]
        hea_writers = [ECGRecord() for file in num_files]

        data = [[] for _ in range(num_files)]
        interest_column = self.widget.w.data_column_space.text()

        signal_data = record.get_lead(interest_column)

        data_per_part = len(signal_data) // num_files

        for i in range(num_files):
            start_message = i * data_per_part
            end_message = (i + 1) * data_per_part if i < num_files - 1 else len(signal_data)

            data[i-1].append(signal_data[start_message:end_message])

        current_time = ECGRecord.time

        for i, hea_writer in enumerate(hea_writers):
            hea_writer.from_np_array(output_file_paths[i], current_time, data[i-1], labels)

        
        msg = QMessageBox()
        msg.setWindowTitle("Action Completed")
        msg.setText("The action has been completed.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

        self.changeContent(0)


    def split_mat(self, input_file, output_prefix, num_files):
        
        import h5py
        
        with h5py.File(input_file, 'r') as file:
            # Get a list of dataset names in the original file
            dataset_names = list(file.keys())

            portion_size = len(dataset_names) // num_files
    
            # Create new HDF5 files for each portion of data
            for portion_index in range(num_files):
                with h5py.File(f'output_portion_{portion_index}.h5', 'w') as output_file:
                    # Iterate over the dataset names
                    interest_column = self.widget.w.data_column_space.text()
                    dataset_name = interest_column
                    # Get the data from the original dataset
                    original_dataset = file[dataset_name]
                    original_data = original_dataset[:]
                
                    # Calculate the start and end indices for the portion
                    start_index = portion_index * portion_size
                    end_index = (portion_index + 1) * portion_size
                
                    # Slice the data to get the desired portion
                    portion_data = original_data[start_index:end_index]
                
                    # Create a new dataset in the output file and write the portion data
                    output_file.create_dataset(dataset_name, data=portion_data)

        
        msg = QMessageBox()
        msg.setWindowTitle("Action Completed")
        msg.setText("The action has been completed.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()

        self.changeContent(0)
    
    def convert_to_seconds(self, value, format):

        
        if format == "HH:MM:SS.FFF":
            dt = dtime.datetime.strptime(value, "%H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "dd.mm.yyyy HH:MM:SS.FFF":
            dt = dtime.datetime.strptime(value, "%d.%m.%Y %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "yyyy.mm.dd HH:MM:SS.FFF":
            dt = dtime.datetime.strptime(value, "%Y.%m.%d %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "mm.dd.yyyy HH:MM:SS.FFF":
            dt = dtime.datetime.strptime(value, "%m.%d.%Y %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "dd/mm/yyyy HH:MM:SS:FFF":
            dt = dtime.datetime.strptime(value, "%d/%m/%Y %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "yyyy/mm/dd HH:MM:SS.FFF":
            dt = dtime.datetime.strptime(value, "%Y/%m/%d %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "mm/dd/yyyy HH:MM:SS.FFF":
            dt = dtime.datetime.strptime(value, "%m/%d/%Y %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "dd-mm-yyyy HH:MM:SS:FFF":
            dt = dtime.datetime.strptime(value, "%d-%m-%Y %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "yyyy-mm-dd HH:MM:SS.FFF":
            dt = dtime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "mm-dd-yyyy HH:MM:SS.FFF":
            dt = dtime.datetime.strptime(value, "%m-%d-%Y %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "yyyy-mm-ddTHH:MM:SS.FFF":
            dt = dtime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()
        elif format == "dd.m.yyyy HH:MM:SS:FFF":
            dt = dtime.datetime.strptime(value, "%d.%m.%Y %H:%M:%S.%f")
            td = dt - dtime.datetime.combine(dtime.date(2023, 5, 1), dtime.datetime.min.time())
            seconds = td.total_seconds()

        return seconds

    def convert_to_time_format(self, time_values, format):

        timestamps = []

        for time_value in time_values:
            if format == "HH:MM:SS.FFF":
                current_time = (dtime.datetime.strptime(time_value, "%H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "dd.mm.yyyy HH:MM:SS.FFF":
                current_time = (dtime.datetime.strptime(time_value, "%d.%m.%Y %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "yyyy.mm.dd HH:MM:SS.FFF":
                current_time = (dtime.datetime.strptime(time_value,"%Y.%m.%d %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "mm.dd.yyyy HH:MM:SS.FFF":
                current_time = (dtime.datetime.strptime(time_value, "%m.%d.%Y %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "dd/mm/yyyy HH:MM:SS:FFF":
                current_time = (dtime.datetime.strptime(time_value, "%d/%m/%Y %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "yyyy/mm/dd HH:MM:SS.FFF":
                current_time = (dtime.datetime.strptime(time_value,"%Y/%m/%d %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "mm/dd/yyyy HH:MM:SS.FFF":
                current_time = (dtime.datetime.strptime(time_value, "%m/%d/%Y %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "dd-mm-yyyy HH:MM:SS:FFF":
                current_time = (dtime.datetime.strptime(time_value, "%d-%m-%Y %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "yyyy-mm-dd HH:MM:SS.FFF":
                current_time = (dtime.datetime.strptime(time_value, "%Y-%m-%d %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "mm-dd-yyyy HH:MM:SS.FFF":
                current_time = (dtime.datetime.strptime(time_value, "%m-%d-%Y %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "yyyy-mm-ddTHH:MM:SS.FFF":
                current_time = (dtime.datetime.strptime(time_value, "%Y-%m-%dT%H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))
            elif format == "dd.m.yyyy HH:MM:SS:FFF":
                current_time = (dtime.datetime.strptime(time_value, "%d.%m.%Y %H:%M:%S.%f"))
                timestamps.append(current_time.strftime("%d--%H:%M:%S"))

        return timestamps
    
    def convert_one_to_time_format(self, time_value, format):

        timestamps = []
        if format == "s":
            # Calculate hours, minutes, and remaining seconds
            hours, remainder = divmod(time_value, 3600)
            minutes, seconds = divmod(remainder, 60)
            timestamps.append((f"1--{int(hours):02}:{int(minutes):02}:{int(seconds):02}").strip())
        elif format == "ms":
            current_time = (dtime.datetime.strptime(time_value, "%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "HH:MM:SS.FFF":
            current_time = (dtime.datetime.strptime(time_value, "%H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "dd.mm.yyyy HH:MM:SS.FFF":
            current_time = (dtime.datetime.strptime(time_value, "%d.%m.%Y %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "yyyy.mm.dd HH:MM:SS.FFF":
            current_time = (dtime.datetime.strptime(time_value,"%Y.%m.%d %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "mm.dd.yyyy HH:MM:SS.FFF":
            current_time = (dtime.datetime.strptime(time_value, "%m.%d.%Y %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "dd/mm/yyyy HH:MM:SS:FFF":
            current_time = (dtime.datetime.strptime(time_value, "%d/%m/%Y %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "yyyy/mm/dd HH:MM:SS.FFF":
            current_time = (dtime.datetime.strptime(time_value,"%Y/%m/%d %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "mm/dd/yyyy HH:MM:SS.FFF":
            current_time = (dtime.datetime.strptime(time_value, "%m/%d/%Y %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "dd-mm-yyyy HH:MM:SS:FFF":
            current_time = (dtime.datetime.strptime(time_value, "%d-%m-%Y %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "yyyy-mm-dd HH:MM:SS.FFF":
            current_time = (dtime.datetime.strptime(time_value, "%Y-%m-%d %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "mm-dd-yyyy HH:MM:SS.FFF":
            current_time = (dtime.datetime.strptime(time_value, "%m-%d-%Y %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "yyyy-mm-ddTHH:MM:SS.FFF":
            current_time = (dtime.datetime.strptime(time_value, "%Y-%m-%dT%H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))
        elif format == "dd.m.yyyy HH:MM:SS:FFF":
            current_time = (dtime.datetime.strptime(time_value, "%d.%m.%Y %H:%M:%S.%f"))
            timestamps.append(current_time.strftime("%d--%H:%M:%S"))

        return timestamps
    
    
    def generate_timestamps_from_duration(self, duration, frequency):
        # Convert first and last timestamps to datetime objects
        #first_datetime = dtime.datetime.strptime(first_timestamp, "%Y-%m-%dT%H:%M:%S.%f")
        #last_datetime = dtime.datetime.strptime(last_timestamp, "%Y-%m-%dT%H:%M:%S.%f")
 
        # Calculate the time step based on the duration and number of steps
        num_steps = duration + 1  # Including the first and last timestamps
        first_timestamp = "0:0:0"
        time_step = dtime.timedelta(seconds=1/frequency)

        # Generate the timestamps
        timestamps = []
        current_numpy = dtime.datetime.strptime(first_timestamp, "%H:%M:%S")
        for _ in range(num_steps):
            timestamps.append(current_numpy.strftime("%d--%H:%M:%S"))
            current_numpy += time_step

        return timestamps
    
    def generate_timestamps_from_start_end(self, first_timestamp, last_timestamp, duration):
        # Convert first and last timestamps to datetime objects
        #first_datetime = dtime.datetime.strptime(first_timestamp, "%Y-%m-%dT%H:%M:%S.%f")
        #last_datetime = dtime.datetime.strptime(last_timestamp, "%Y-%m-%dT%H:%M:%S.%f")
        
        # Calculate the time step based on the duration and number of steps
        num_steps = duration + 1  # Including the first and last timestamps
        #time_step = (dtime.datetime.strptime(last_timestamp, "%d--%H:%M:%S") - dtime.datetime.strptime(first_timestamp, "%d--%H:%M:%S")) / duration

        # Generate the timestamps
        timestamps = []
        current_timestamp = dtime.datetime.strptime(first_timestamp, "%d--%H:%M:%S")
        last_timestamp = dtime.datetime.strptime(last_timestamp, "%d--%H:%M:%S")
        while current_timestamp <= last_timestamp:
            #current_numpy = dtime.datetime.strptime(current_timestamp, "%d--%H:%M:%S")
            timestamps.append(current_timestamp.strftime("%d--%H:%M:%S"))
            current_timestamp += dtime.timedelta(seconds=num_steps)


        return timestamps
    
    #@jit
    def getFrequency(self, timeValues):

        
        # Calculate the time differences between consecutive timestamps
        time_diff = np.diff(timeValues)
        
        # Calculate the average time difference
        avg_time_diff = np.mean(time_diff)
        
        # Calculate the sampling frequency
        sampling_freq = 1 / avg_time_diff

        return sampling_freq
    

    def show_load_file(self):
        
        import h5py
        file_type = "h5"
        file_filter = f"HDF5 Files (*.{file_type})"

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(
            self, f"Select HDF5 File", "", file_filter, options=options
        )

        if file_name:

            loading_box = QMessageBox()
            loading_box.setWindowTitle("Loading")
            loading_box.setText("Loading data...")
            loading_box.show()

            # Open the HDF5 file in read mode
            with h5py.File(file_name, 'r') as file:

                # group 1 has numbers and arrays
                group1 = file['group1']

                self.palms.FREQUENCY = group1.attrs['frequency'][()]
                self.palms.ECG_DATA = group1['ecg_values'][:]
                if 'start_indexes' in group1:
                    self.palms.START_INDEXES = np.array(group1['start_indexes'][:], dtype="int32")
                if 'end_indexes' in group1:
                    self.palms.END_INDEXES = np.array(group1['end_indexes'][:], dtype="int32")
                if 'missing_start_indexes' in group1:
                    self.palms.START_MISSING_INDEXES = np.array(group1['missing_start_indexes'][:], dtype="int32")
                if 'missing_end_indexes' in group1:
                    self.palms.END_MISSING_INDEXES = np.array(group1['missing_end_indexes'][:], dtype="int32")
                #extra: 
                self.palms.noise_level = group1.attrs["noise_level"][()]
                self.palms.beat_correction_level = group1.attrs["beat_correction_level"][()]
                self.palms.current_outlier = group1.attrs["current_outlier"][()]
                self.palms.RR_ONLY = group1.attrs["RR_ONLY"][()]
                self.palms.DATA_TYPE = group1.attrs["DATA_TYPE"][()]
                if 'original_rr' in group1:
                    from gui.tracking import Wave
                    rr_values = np.array(group1["original_rr"][()])
                    rr_int_wave = Wave(rr_values, int(self.palms.FREQUENCY), offset=0, label='RR', unit='sec')
                    self.palms.original_rr = rr_int_wave
                if 'original_fiducials' in group1:
                    self.palms.original_fiducials = np.array(group1["original_fiducials"][()], dtype="int32")
                if 'original_annotations' in group1:
                    self.palms.original_annotations = np.array(group1["original_annotations"][()], dtype="int32")
                if 'annotations' in group1:
                    self.palms.annotations = np.array(group1["annotations"][()], dtype="int32")
                if 'threshold_outliers' in group1:
                   self.palms.threshold_outliers = np.array(group1["threshold_outliers"][()], dtype="int32")
                

                # group 2 has dictionary and boolean
                group2 = file['group2']
                # Initialize an empty dictionary to store the data
                samples_dictionary = {}

                # Iterate over the group's attributes
                for attr_name, attr_value in group2.attrs.items():
                    # Split the attribute name to extract sample_name and key
                    parts = attr_name.split('_')
                    sample_name = parts[0]
                    sample_index = parts[1]
                    sample_limit = parts[2]

                    # Check if the sample_name exists in the dictionary, if not, create it
                    if sample_name not in samples_dictionary:
                        samples_dictionary[sample_name] = {}

                    if sample_index not in samples_dictionary[sample_name]:
                        samples_dictionary[sample_name][sample_index] = {}

                    if sample_index not in samples_dictionary[sample_name][sample_index]:
                        samples_dictionary[sample_name][sample_index][sample_limit] = {}

                    # Add the attribute value to the corresponding key in the dictionary
                    samples_dictionary[sample_name][sample_index][sample_limit] = attr_value
                
                self.palms.samples_dictionary = samples_dictionary

                # group 3 for the boolean
                group3 = file['group3']
                self.palms.FIRST_DATETIME = group3.attrs['first_datetime']
                self.palms.LAST_DATETIME = group3.attrs['last_datetime']
                self.palms.CURRENT_FILE = group3.attrs['current_file']
                self.palms.is_threshold_outlier = bool(group3.attrs['is_threshold_outlier'][()])
                self.palms.is_algorithm_outlier = bool(group3.attrs['is_algorithm_outlier'][()])
                self.palms.algorithm_correction = bool(group3.attrs['algorithm_correction'][()])

                group4 = file['group4']
                # Initialize an empty dictionary to store the data
                algorithm_outliers = {}

                # Iterate over the group's attributes
                for attr_name, attr_value in group4.attrs.items():
                    # Split the attribute name to extract sample_name and key
                    algorithm_outliers[attr_name] = attr_value
                self.palms.algorithm_outliers = algorithm_outliers

            self.palms.is_load = True
            self.palms.continue_value = True

            self.close()

            loading_box.close()
            

#if __name__ == "__main__":
#    app = QApplication(sys.argv)
#    mainWindow = MyMainImport()
#    mainWindow.show()
#    sys.exit(app.exec_())