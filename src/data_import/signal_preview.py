from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtWidgets import QPushButton, QCheckBox, QLabel, QTableView, QGraphicsScene, QScrollArea
import pandas as pd
import csv
import pyedflib as pyedflib
import pyqtgraph as pg
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import datetime as dtime
from pyecg import ECGRecord


class SignalPreviewFrame(QtWidgets.QFrame):

    def __init__(self, main_window, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setParent(main_window)
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
        self.n = 400
        self.updateHeight()

        # Drag and Drop Related
        # TODO: only accept drag/drop of other Frames (through MIME data)
        self.setAcceptDrops(True)
        self.dataPreviewPanel: SignalPreviewPanel = None
        self.dragStartPos = QtCore.QPoint()
        self.drag = None

    def updateHeight(self):
        self.setFixedHeight(self.n)



class SignalPreviewPanel(QtWidgets.QWidget):

    def __init__(self, frame: SignalPreviewFrame, path=None, file_type=None, header_lines=None, column=None, delimiter=None, frequency="", frequencyColumn=None, dateType=None, data_units= None):
        super().__init__()
        
        self.setParent(frame)

        self.layout = QtWidgets.QVBoxLayout()
        # Create the buttons and set their properties
        title_label = QLabel("Signal preview")
        title_label.setAlignment(QtCore.Qt.AlignCenter)

        # Create the layout and add the buttons to it
        self.layout.addWidget(title_label)
        self.setSignal(path, file_type, header_lines, column, delimiter, frequencyColumn, dateType, data_units, frequency)
        
        frame.setLayout(self.layout)

    def setSignal(self, path, file_type, header_lines, column, delimiter, frequencyColumn, dateType, data_units, frequency=""):

        if (file_type in ["csv", "txt", "dat"]):
            # Check if path is None
            if (path is None):
                label = QLabel("No preview available")
                self.layout.addWidget(label, alignment=QtCore.Qt.AlignCenter)
            
            else:
                try: 
                    if frequency is None:
                        frequency = 0

                    new_data, time_values = self.preview_signal(data_type=file_type, data_path=path, interest_column=column, header_lines=header_lines, frequency=frequency, frequencyColumn=frequencyColumn, delimiter=delimiter, dateType=dateType)

                    self.figure = Figure(figsize=(7,2.5))
                    self.canvas = FigureCanvas(self.figure)
                
                    # Plot the ECG signal on the Figure
                    self.ax = self.figure.add_subplot(111)
                    self.ax.plot(pd.to_numeric(new_data))
                 

                    self.layout.addWidget(self.canvas)
                    #self.range_slider_ECG = QRangeSlider()
                    #self.range_slider_ECG.setOrientation(QtCore.Qt.Horizontal)
                    #self.range_slider_ECG.setFixedHeight(20)
                    #self.range_slider_ECG.setMinimum(0)
                
                    #self.range_slider_ECG.setMaximum(len(self.first_data))
                    #self.range_slider_ECG.setRange(0, len(self.first_data))
                
                    #self.range_slider_ECG.setSliderPosition(0)
                
                    #self.range_slider_ECG.setValue([0, max_range])
                    # Enable zoom functionality
                    # Add the NavigationToolbar for zooming
                    toolbar = NavigationToolbar(self.canvas, self)
                    self.layout.addWidget(toolbar)
                    #median_values = np.median(np.abs(self.first_data))*2
                    #self.range_slider_ECG.valueChanged.connect(self.on_range_slider_ECG_changed)
                
                    self.ax.set_xlabel("Time (s)", labelpad=10)
                    # if ecg type
                    self.ax.set_ylabel(f"ECG ({data_units})", labelpad=10)
                    ticks = np.arange(0, time_values[-1], 100)
                    self.ax.set_xlim(0, len(new_data))
                    # Set the x-axis ticks and labels
                
                    self.ax.set_xticklabels(ticks)
                    #self.ax.set_xticklabels(np.arange(0, 10 + 1))
                    self.figure.tight_layout()
                    #self.ax.set_ylim(-median_values, median_values)
                    # Add the FigureCanvas to the QVBoxLayout
                
                    #self.layout.addWidget(self.range_slider_ECG)

                except Exception as e:
                    label = QLabel("No preview available")
                    self.layout.addWidget(label, alignment=QtCore.Qt.AlignCenter)
                    print("error signal")
                    print(e)
                    import traceback
                    error_traceback = traceback.format_exc()
                    print(error_traceback)
        else: # edf and others

            # Check if path is None
            if (path is None or file_type is None):
                label = QLabel("No preview available")
                self.layout.addWidget(label, alignment=QtCore.Qt.AlignCenter)
            
            else:
                try:
                    # Get data
                    self.first_data, self.time_values = self.preview_signal(file_type, path, frequency=frequency, header_lines=header_lines, interest_column=column)
                
                    #ten_seconds = frequency*10
                    #max_range = min(int(ten_seconds), len(self.first_data))
                    # Create plot
                    # Create a Figure and a FigureCanvas
                    self.figure = Figure(figsize=(7,2.5))
                    self.canvas = FigureCanvas(self.figure)
                
                    # Plot the ECG signal on the Figure
                    self.ax = self.figure.add_subplot(111)
                    self.ax.plot(pd.to_numeric(self.first_data))
                

                    self.layout.addWidget(self.canvas)
                    #self.range_slider_ECG = QRangeSlider()
                    #self.range_slider_ECG.setOrientation(QtCore.Qt.Horizontal)
                    #self.range_slider_ECG.setFixedHeight(20)
                    #self.range_slider_ECG.setMinimum(0)
                
                    #self.range_slider_ECG.setMaximum(len(self.first_data))
                    #self.range_slider_ECG.setRange(0, len(self.first_data))
                
                    #self.range_slider_ECG.setSliderPosition(0)
                
                    #self.range_slider_ECG.setValue([0, max_range])
                    # Enable zoom functionality
                    # Add the NavigationToolbar for zooming
                    toolbar = NavigationToolbar(self.canvas, self)
                    self.layout.addWidget(toolbar)
                    #median_values = np.median(np.abs(self.first_data))*2
                    #self.range_slider_ECG.valueChanged.connect(self.on_range_slider_ECG_changed)
                
                    self.ax.set_xlabel("Time (s)", labelpad=10)
                    # if ecg type
                    self.ax.set_ylabel(f"ECG ({data_units})", labelpad=10)
                    ticks = np.arange(0, self.time_values[-1], 100)
                    self.ax.set_xlim(0, len(self.first_data))
                    # Set the x-axis ticks and labels
                
                    self.ax.set_xticklabels(ticks)
                    #self.ax.set_xticklabels(np.arange(0, 10 + 1))
                    self.figure.tight_layout()
                    #self.ax.set_ylim(-median_values, median_values)
                    # Add the FigureCanvas to the QVBoxLayout
                
                    #self.layout.addWidget(self.range_slider_ECG)

                except Exception as e:
                    label = QLabel("No preview available")
                    self.layout.addWidget(label, alignment=QtCore.Qt.AlignCenter)
                    print("error signal")
                    print(e)
                    import traceback
                    error_traceback = traceback.format_exc()
                    print(error_traceback)


    # 2) 
    # When having chosen what to import, we can show the signal preview
    # ecg_type is 0 for ecg, 1 for hr and 2 for rr
    def preview_signal(self, data_type, data_path, header_lines = 0, ecg_type = 0, delimiter="", interest_column="", frequency="", frequencyColumn="", dateType=""):
        
        if data_type == "edf": # edf
            new_data = self.preview_edf_signal(data_path, ecg_type, interest_column)
            return new_data
        
        elif data_type == "hea":
            new_data = self.preview_hea_signal(data_path, ecg_type, interest_column)
            return new_data

        elif data_type == "mat":
            new_data = self.preview_mat_signal(data_path, ecg_type, interest_column, frequencyColumn, dateType)
            return new_data
        elif data_type == "fit":
            new_data = self.preview_fit_signal(data_path, ecg_type, interest_column, frequencyColumn, dateType)
            return new_data
        elif data_type == "dat":
            new_data =  self.preview_txt_signal(data_path, header_lines, delimiter, interest_column, frequency, frequencyColumn, dateType)
            return new_data

        elif data_type == "ecg":
            new_data = self.preview_ecg_signal(data_path, ecg_type, interest_column)
            return new_data
        elif data_type == "txt": # txt
            new_data =  self.preview_txt_signal(data_path, header_lines, delimiter, interest_column, frequency, frequencyColumn, dateType)
            return new_data
        elif data_type == "csv": # csv
            new_data = self.preview_csv_signal(data_path, header_lines, delimiter, interest_column, frequency, frequencyColumn, dateType)
            return new_data
        elif data_type == "Other delimiter": # csv
            new_data = self.preview_csv_signal(data_path, header_lines, delimiter, interest_column, frequency, frequencyColumn, dateType)
            return new_data
        
    # edf files should not have data preview, just signal preview
    def preview_edf_signal(self, data_path, ecg_type, interest_column):
        
        # Open the EDF file
        f = pyedflib.EdfReader(data_path)

        # Read the ECG signal
        try: 
            column_names = f.getSignalHeaders()
            frequency = f.getSampleFrequency(column_names[int(interest_column)-1])
            ten_minutes = int(frequency)*60
            ecg_signal = f.readSignal(column_names[int(interest_column)-1], n=int(ten_minutes))
        
        
            # Close the EDF file
            timeValues = np.arange(0, 600, 1/int(frequency))
            
        except Exception as e:
            import traceback
            error_traceback = traceback.format_exc()
            print(error_traceback)
            
        
        f.close()
        return ecg_signal[0:599], timeValues
    

    def preview_fit_signal(self, data_path, ecg_type, interest_column, frequency_column, dateType):
        import fitparse
        data_labels = []
            
        fitfile = fitparse.FitFile(data_path)
        for record in fitfile.get_messages():
            for data_message in record:
                if hasattr(data_message, "value"):
                    data_labels.append(data_message.name)

        data_name= interest_column
        frequency_name= frequency_column

        data = fitfile.get_messages(name=data_name)[0:599]
        time_values = fitfile.get_messages(name=frequency_name)[0:599]
        if (dateType == "s"):
            new_frequency = self.getFrequency(timeValues=time_values)
            timeValues = np.arange(0, 600, 1/int(new_frequency))
        elif(dateType == "ms"):
            new_frequency = self.getFrequency(timeValues=time_values/1000)
            timeValues = np.arange(0, 600, 1/int(new_frequency))
        else:
            # change datetimeto seconds
            new_time_values = list(map(lambda time_value: self.convert_to_seconds(time_value, dateType), time_values[0:50]))
            new_frequency = self.getFrequency(timeValues=new_time_values)

            timeValues = np.arange(0, len(time_values)*1/int(new_frequency), 1/int(new_frequency))

        return data, timeValues


    def preview_hea_signal(self, data_path, ecg_type, interest_column):
        record = ECGRecord.from_wfdb(data_path)
        frequency = record.time.fs
        timeValues = np.arange(0, 600, 1/int(frequency))
        ten_minutes = int(frequency)*60
        signal_data = record.get_lead(interest_column)[0:ten_minutes]
        
        return signal_data, timeValues


    def preview_mat_signal(self, data_path, ecg_type, interest_column, frequency_column, dateType):
        import h5py
        with h5py.File(data_path, 'r') as file:
            data = file[interest_column][0:599]
            time_values = file[frequency_column][0:599]
            if (dateType == "s"):
                new_frequency = self.getFrequency(timeValues=time_values)
                timeValues = np.arange(0, 600, 1/int(new_frequency))
            elif(dateType == "ms"):
                new_frequency = self.getFrequency(timeValues=time_values/1000)
                timeValues = np.arange(0, 600, 1/int(new_frequency))
            else:
                # change datetimeto seconds
                new_time_values = list(map(lambda time_value: self.convert_to_seconds(time_value, dateType), time_values[0:50]))
                new_frequency = self.getFrequency(timeValues=new_time_values)

                timeValues = np.arange(0, len(time_values)*1/int(new_frequency), 1/int(new_frequency))

        return data, timeValues


    def preview_ecg_signal(self, data_path, ecg_type, interest_column):
        record = ECGRecord.from_ishine(data_path)
        frequency = record.time.fs
        timeValues = np.arange(0, 600, 1/int(frequency))
        ten_minutes = int(frequency)*60
        signal_data = record.get_lead(interest_column)[0:ten_minutes]
        
        return signal_data, timeValues
        
    
    def preview_txt_signal(self, data_path, header_lines: int, delimiter, interest_column, frequency, frequencyColumn=None, dateType=None):
        df = None
        new_frequency=None
        timeValues = []
        
        if frequency != 0 and frequency != '':
            ten_minutes = int(frequency)*60

            df = pd.read_csv(data_path, skiprows=int(header_lines), nrows=int(ten_minutes), header=None, sep=delimiter, engine="python")

            timeValues = np.arange(0, 600, 1/int(frequency))

        elif frequencyColumn != None:
            df = pd.read_csv(data_path, skiprows=int(header_lines), nrows=int(10000), header=None, sep=delimiter, engine="python")
            time_values = df.iloc[:,int(frequencyColumn)-1]
            new_frequency = 1
            if (dateType == "s"):
                new_frequency = self.getFrequency(timeValues=time_values)
                timeValues = np.arange(0, 600, 1/int(new_frequency))
            elif(dateType == "ms"):
                new_frequency = self.getFrequency(timeValues=time_values/1000)
                timeValues = np.arange(0, 600, 1/int(new_frequency))
            else:
                # change datetimeto seconds
                new_time_values = list(map(lambda time_value: self.convert_to_seconds(time_value, dateType), time_values[0:50]))
                new_frequency = self.getFrequency(timeValues=new_time_values)

                timeValues = np.arange(0, len(time_values)*1/int(new_frequency), 1/int(new_frequency))
            
        column_values = df.iloc[:,int(interest_column)-1]

        return column_values, timeValues
    
    def preview_csv_signal(self, data_path, header_lines, delimiter, interest_column, frequency, frequencyColumn, dateType):
        df = None
        new_frequency=None
        timeValues = []
        
        if frequency != "":
            ten_minutes = int(frequency)*60

            df = pd.read_csv(data_path, skiprows=int(header_lines), nrows=int(ten_minutes), header=None, sep=delimiter, engine="python")

            timeValues = np.arange(0, 600, 1/int(frequency))


        if frequency == "":
            df = pd.read_csv(data_path, skiprows=int(header_lines), nrows=int(10000), header=None, sep=delimiter, engine="python")
            time_values = df.iloc[:,int(frequencyColumn)-1]
            new_frequency = 1
            if (dateType == "s"):
                new_frequency = self.getFrequency(timeValues=time_values)
                timeValues = np.arange(0, 600, 1/int(new_frequency))
            elif(dateType == "ms"):
                new_frequency = self.getFrequency(timeValues=time_values/1000)
                timeValues = np.arange(0, 600, 1/int(new_frequency))
            else:
                # change datetimeto seconds
                new_time_values = list(map(lambda time_value: self.convert_to_seconds(time_value, dateType), time_values[0:50]))
                new_frequency = self.getFrequency(timeValues=new_time_values)

                timeValues = np.arange(0, len(time_values)*1/int(new_frequency), 1/int(new_frequency))
            
        column_values = df.iloc[:,int(interest_column)-1]

        return column_values, timeValues
    

    def convert_to_seconds(self, value, format):
        seconds = []
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
    

    def getFrequency(self, timeValues):

        
        # Calculate the time differences between consecutive timestamps
        time_diff = np.diff(timeValues)
        
        # Calculate the average time difference
        avg_time_diff = np.mean(time_diff)
        
        # Calculate the sampling frequency
        sampling_freq = 1 / avg_time_diff

        return sampling_freq