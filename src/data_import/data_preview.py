from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtWidgets import QPushButton, QCheckBox, QLabel, QTableView
import pandas as pd
import csv
import numpy as np
import pyedflib as pyedflib
import subprocess
import fileinput
from PyQt5.QtCore import Qt, QModelIndex, QAbstractTableModel
from PyQt5.QtGui import QColor
from pyecg import ECGRecord


class DataPreviewFrame(QtWidgets.QFrame):

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
        self.n = 200
        self.updateHeight()

        # Drag and Drop Related
        # TODO: only accept drag/drop of other Frames (through MIME data)
        self.setAcceptDrops(True)
        self.dataPreviewPanel: DataPreviewPanel = None
        self.dragStartPos = QtCore.QPoint()
        self.drag = None

    def updateHeight(self):
        self.setFixedHeight(self.n)



class DataPreviewPanel(QtWidgets.QWidget):

    def __init__(self, frame: DataPreviewFrame, path = None, file_type=None, delimiter=";"):
        super().__init__()
        
        self.setParent(frame)

        self.layout = QtWidgets.QVBoxLayout()
        # Create the buttons and set their properties
        title_label = QLabel("Data preview")
        title_label.setAlignment(QtCore.Qt.AlignCenter)

        # Create the layout and add the buttons to it
        self.layout.addWidget(title_label)
        self.setTable(path, file_type, delimiter)
        
        frame.setLayout(self.layout)


    def setTable(self, path, file_type, delimiter):
        
        # Check if path is None
        if path is None:
            label = QLabel("No preview available")
            self.layout.addWidget(label, alignment=QtCore.Qt.AlignCenter)
        else:
            # Load CSV data
            #data = pd.read_csv(self.path)

            try:

                # Create QTableView for the table preview
                self.table_view = QTableView()
                self.table_view.setFixedSize(750, 200)
                self.table_view.setEditTriggers(QTableView.NoEditTriggers)
                self.table_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
                self.table_view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
                
                if (file_type in ["edf", "hea", "mat", "fit"]):
                    data, headers = self.preview_edf_data(file_type, path, delimiter)

                    model = CustomTableModel(data, headers)
                    self.table_view.setModel(model)

                else:
                    interest_data = self.preview_data(file_type, path, delimiter)

                    # Create a new QStandardItemModel to hold the extracted values
                    self.new_model = QtGui.QStandardItemModel()

                    # Set the number of rows and columns in the model
                    num_rows, num_cols = interest_data.shape[0], interest_data.shape[1]
                    self.new_model.setRowCount(num_rows)
                    self.new_model.setColumnCount(num_cols)

                    # Set numerical column headers from 1 to the number of columns
                    column_headers = [str(i + 1) for i in range(num_cols)]
                    self.new_model.setHorizontalHeaderLabels(column_headers)

                    # Iterate over the rows and columns of the DataFrame
                    for row in range(num_rows):
                        for col in range(num_cols):
                            # Get the cell value
                            cell_value = str(interest_data.iloc[row, col])

                            # Create a QStandardItem and set the value
                            item = QtGui.QStandardItem(cell_value)

                            # Set the item in the model at the corresponding row and column
                            self.new_model.setItem(row, col, item)

                    # Set the model to the table view
                    self.table_view.setModel(self.new_model)

                # Adjust column widths to fit the content
                self.table_view.resizeColumnsToContents()
    
                self.layout.addWidget(self.table_view)

            except Exception as e:
                label = QLabel("No preview available")
                self.layout.addWidget(label, alignment=QtCore.Qt.AlignCenter)
                print("error data")
                import traceback
                error_traceback = traceback.format_exc()
                print(error_traceback)


     # 1) The user sees the data import screen and selects what kind of data they want to import. 
    # After that, they choose the file path. This script receives these 2 pieces of information 
    # on the function preview_data

    # Conditionals to go to certain function depending on selected data type
    def preview_data(self, data_type, data_path, delimiter):
        if data_type == "dat":
            return self.preview_txt_data(data_path, delimiter)
        elif data_type == "txt": # txt
            return self.preview_txt_data(data_path, delimiter)
        elif data_type == "csv": # csv
            return self.preview_csv_data(data_path, delimiter)
        elif data_type == "Other delimiter": # csv
            return self.preview_csv_data(data_path, delimiter)
        
        
    def preview_edf_data(self, data_type, data_path, delimiter):
        
        if data_type == "edf": # edf
            data = {}
            labels = []
            f = pyedflib.EdfReader(data_path)
            labels = f.getSignalLabels()

            # Read signal labels and data
            for label in labels:
                if label not in data:
                    data[label] = []
                ecg_index = labels.index(label)
                signal_data = f.readSignal(ecg_index,n=1000)

                data[label] = signal_data.tolist()

            f.close()
            return data, labels
        
        elif data_type == "hea":
            # To load a wfdb formatted ECG record
            record = ECGRecord.from_wfdb(data_path)
            data = {}
            labels = record.lead_names
            for label in labels:
                if label not in data:
                    data[label] = []
                signal_data = record.get_lead(label)[1:1000]

                data[label] = signal_data

            return data, labels

        elif data_type == "mat":
            data = {}
            labels = []
            import h5py
            with h5py.File(data_path, 'r') as file:
                for dataset_name in file.keys():
                    if dataset_name not in data:
                        data[dataset_name] = []
                    # Access the dataset by name
                    dataset = file[dataset_name]

                    # Extract the data from the dataset and convert it to a NumPy array
                    current_data = dataset[()]

                    data[dataset_name] = current_data
                    labels.append(dataset_name)

            return data, labels

        elif data_type == "ecg":
            # To load a ishine formatted ECG record
            record = ECGRecord.from_ishine(data_path)
            data = {}
            labels = record.lead_names
            for label in labels:
                if label not in data:
                    data[label] = []
                signal_data = record.get_lead(label)[1:1000]

                data[label] = signal_data
                
            return data, labels

        elif data_type == "fit":
            import fitparse
            data = {}
            data_labels = []
            
            fitfile = fitparse.FitFile(data_path)
            for record in fitfile.get_messages():
                for data_message in record:
                    if data_message.name not in data:
                        data[data_message.name] = []

                    if hasattr(data_message, "value"):
                        data[data_message.name].append(data_message.value)
                        data_labels.append(data_message.name)

            return data, data_labels
        
    # Some file formats can have data preview
    # Get all the file and save it as json. Might be better to display it with python to make it
    # scrollable
    
    def preview_txt_data(self, data_path, delimiter):
        df = pd.read_csv(data_path, nrows=1000, sep=delimiter, header=None, engine="python")
        return df
    
    def preview_data_data(self, data_path, delimiter):
        df = pd.read_csv(data_path, nrows=1000, sep=delimiter, header=None, engine="python")
        return df
    
    def preview_csv_data(self, data_path, delimiter):
        df = pd.read_csv(data_path, nrows=1000, sep=delimiter, header=None, engine="python")
        return df




class CustomTableModel(QAbstractTableModel):
    def __init__(self, data, headers):
        super().__init__()
        self.data = data
        self.headers = headers

    def rowCount(self, parent=QModelIndex()):
        return len(self.data[self.headers[0]])

    def columnCount(self, parent=QModelIndex()):
        return len(self.data)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            row = index.row()
            col = index.column()
            if row < self.rowCount() and col < self.columnCount():
                return str(self.data[self.headers[col]][row])
        elif role == Qt.BackgroundRole:
            # For example, set background color for specific cells
            if index.column() == 1:
                pass
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal and section < len(self.headers):
                return self.headers[section]
            elif orientation == Qt.Vertical:
                return str(section + 1)  # Row numbers
        return None