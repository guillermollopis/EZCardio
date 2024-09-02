import sys
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton, QFrame, QComboBox, QFormLayout, QFileDialog, QStackedWidget, QMessageBox
from qtpy import QtCore
from data_import.options import OptionsFrame, OptionsPanel
from data_import.data_preview import DataPreviewFrame, DataPreviewPanel
from data_import.signal_preview import SignalPreviewFrame, SignalPreviewPanel
import pandas as pd
import numpy as np
from qtpy.QtCore import Slot, Signal


class SplitFiles(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.parent = main_window
        #self.setStyleSheet("background-color:white;")

        # Create the main vertical layout
        self.layout = QFormLayout()
        self.frequency = None

        # Create the main selector layout
        #selector_widget = QWidget(self)
        first_layout = QHBoxLayout()
        #selector_widget.setStyleSheet("background-color: grey;")

        # Path row
        self.currentPath = None
        self.path_label = QLabel("No file selected")
        self.path_label.setFixedHeight(20)
        first_layout.addWidget(self.path_label)

        self.file_type_combo = QComboBox()
        self.file_type_combo.addItem("csv")
        self.file_type_combo.addItem("ecg")
        self.file_type_combo.addItem("edf")
        self.file_type_combo.addItem("dat")
        self.file_type_combo.addItem("fit")
        self.file_type_combo.addItem("hea")
        self.file_type_combo.addItem("mat")
        self.file_type_combo.addItem("txt")
        self.file_type_combo.addItem("Other delimiter")
        self.file_type_combo.setFixedHeight(20)
        first_layout.addWidget(self.file_type_combo)
        self.file_type_combo.currentTextChanged.connect(self.resetPath)

        add_button = QPushButton("ADD FILE")
        add_button.setStyleSheet("background-color: blue; color: white")
        add_button.clicked.connect(self.open_file_dialog)
        add_button.setFixedHeight(20)
        first_layout.addWidget(add_button)

        # Create and add the other vertical components
        self.layout.addRow(first_layout)

        

        # Options container list. StackedWidget where I add frames. Create first and new one when currentSelector increases
        self.options_frame = None
        self.w = None
        self.createOptions()
        self.options_frame.setFixedHeight(150)

        self.layout.addRow(self.options_frame)

        # Data preview container
        self.addDataPreview()

        # Signal preview container
        
        self.addSignalPreview()
        
        # Set the layout for the main window
        self.setLayout(self.layout)


    def createOptions(self):
        
        self.options_frame = OptionsFrame(main_window=self)
        self.w = OptionsPanel(frame=self.options_frame, split=True)
        
        self.options_frame.layout.addWidget(self.w)
        self.options_frame.optionsPanel = self.w
        
        # Add change updates in options
        self.w.header_lines_space.textChanged.connect(self.testSignalPreview)
        self.w.data_column_space.textChanged.connect(self.testSignalPreview)
        self.w.frequency_sampling_space.textChanged.connect(self.testSignalPreview)
        self.w.column_separator_combo.currentTextChanged.connect(self.testSignalPreview)
        self.w.data_type_combo.currentTextChanged.connect(self.testSignalPreview)
        self.w.data_units_combo.currentTextChanged.connect(self.updateAxis)

    def testSignalPreview(self):
        files_number = self.w.data_type_combo.currentText()

        if (self.currentPath is not None and files_number is not None):
            self.updatePreviews()


    def addDataPreview(self, path=None, file_type=None):

        separator = self.w.column_separator_combo.currentText()
        file_type = self.file_type_combo.currentText()

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

        self.data_preview_frame = DataPreviewFrame(main_window=self)
        self.dp = DataPreviewPanel(frame=self.data_preview_frame, path=path, file_type=file_type, delimiter=delimiter)

        self.data_preview_frame.layout.addWidget(self.dp)
        self.data_preview_frame.optionsPanel = self.dp
        self.layout.addRow(self.data_preview_frame)

    def addSignalPreview(self, path=None, file_type=None):

        # check if self.frequency should change

        header_lines = self.w.header_lines_space.text()
        column = self.w.data_column_space.text()
        separator = self.w.column_separator_combo.currentText()
        data_units = self.w.data_units_combo.currentText()
        file_type = self.file_type_combo.currentText()
        frequencyColumn = ""
        dateType = ""
        dateType = ""
        if (self.w.time_units_combo.currentText().lower() == "none"):
            self.frequency = self.w.frequency_sampling_space.text()
        else:
            frequencyColumn = self.w.time_index_space.text()
            if (self.w.time_units_combo.currentText().lower() == "datetime"):
                dateType = self.w.time_format_combo.currentText()
            else:
                dateType = self.w.time_units_combo.currentText().lower()

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

        self.signal_preview_frame = SignalPreviewFrame(main_window=self)
        self.sp = SignalPreviewPanel(frame=self.signal_preview_frame, path=path, file_type=file_type, header_lines=header_lines, column=column, delimiter=delimiter, frequency=self.frequency, frequencyColumn = frequencyColumn, dateType=dateType, data_units=data_units)

        self.signal_preview_frame.layout.addWidget(self.sp)
        self.signal_preview_frame.optionsPanel = self.sp
        self.layout.addRow(self.signal_preview_frame)

    def updateAxis(self):
        self.sp.ax.set_ylabel(f"ECG ({self.w.data_units_combo.currentText()})")
        self.sp.canvas.draw()

    def update_label(self, current_value, value):

        try:
            files_number = self.w.data_type_combo.currentText()

            new_value = current_value + value
            if (new_value >= 1):
                
                if (value == -1 or new_value <= int(files_number)):
                    self.currentSelector = new_value
                    #self.selector_label.setText("Segment "+str(self.currentSelector))
            
                    self.updatePreviews()

                    # The data type must be the same, so it is disabled after choosing
                    if (new_value != 1):
                        self.file_type_combo.setDisabled(True)
                    else:
                        self.file_type_combo.setDisabled(False)

        except Exception as e:
            print("no data")

    def updatePreviews(self):
        # Delete both frame previews and last button
        self.layout.removeRow(self.data_preview_frame)
        self.layout.removeRow(self.signal_preview_frame)
        # Create the three things again
        if (self.currentPath is not None):
            self.addDataPreview(self.currentPath, self.file_type_combo.currentIndex())
            self.addSignalPreview(self.currentPath, self.file_type_combo.currentIndex())
        else:
            self.addDataPreview(None)
            self.addSignalPreview(None)
        # Add button functionality
        # Show table if csv


    def open_file_dialog(self):
        file_type = self.file_type_combo.currentText().lower()
        file_filter = f"{file_type.upper()} Files (*.{file_type})"

        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(
            self, f"Select {file_type.upper()} File", "", file_filter, options=options
        )
        if file_name:
            self.currentPath = file_name
            self.path_label.setText(file_name)
            # Enable options to edit when file is selected
            #self.disableOptions()
            self.enableOptions()
            self.updatePreviews()
            

    def resetPath(self):
        self.currentPath = None
        #self.options_frame = None
        #self.w = None
        self.path_label.setText("No file selected")
        #self.createOptions()
        self.disableOptions()
        self.updatePreviews()

    def enableOptions(self):
        if (self.file_type_combo.currentText() in ["edf", "ecg", "hea", "mat"]):
            self.w.data_type.setDisabled(False)
            self.w.data_type_combo.setDisabled(False)
            self.w.data_column.setDisabled(False)
            self.w.data_column_space.setDisabled(False)
            #self.w_list[self.currentSelector-1].data_units.setDisabled(False)
            #self.w_list[self.currentSelector-1].data_units_combo.setDisabled(False)
            #self.w_list[self.currentSelector-1].time_units.setDisabled(False)
            #self.w_list[self.currentSelector-1].time_units_combo.setDisabled(False)
            #self.w_list[self.currentSelector-1].extra_widget.setDisabled(False)
            #self.w_list[self.currentSelector-1].extra_widget_space.setDisabled(False)
            #self.w_list[self.currentSelector-1].time_format.setDisabled(False)
            #self.w_list[self.currentSelector-1].time_format_combo.setDisabled(False)

        else: # for txt and csv
            self.w.header_lines.setDisabled(False)
            self.w.header_lines_space.setDisabled(False)
            #self.w_list[self.currentSelector-1].frequency_sampling.setDisabled(False)
            #self.w_list[self.currentSelector-1].frequency_sampling_space.setDisabled(False)
            self.w.data_type.setDisabled(False)
            self.w.data_type_combo.setDisabled(False)
            self.w.column_separator.setDisabled(False)
            self.w.column_separator_combo.setDisabled(False)
            self.w.data_column.setDisabled(False)
            self.w.data_column_space.setDisabled(False)
            self.w.data_units.setDisabled(False)
            self.w.data_units_combo.setDisabled(False)
            self.w.time_units.setDisabled(False)
            self.w.time_units_combo.setDisabled(False)
            self.w.extra_widget.setDisabled(False)
            self.w.extra_widget_space.setDisabled(False)
            #self.w_list[self.currentSelector-1].time_index_column.setDisabled(False)
            #self.w_list[self.currentSelector-1].time_index_space.setDisabled(False)
            #self.w_list[self.currentSelector-1].time_units.setDisabled(False)
            #self.w_list[self.currentSelector-1].time_format.setDisabled(False)


    def disableOptions(self):
        self.w.header_lines.setDisabled(True)
        self.w.header_lines_space.setDisabled(True)
        self.w.header_lines_space.clear()
        #self.w_list[self.currentSelector-1].frequency_sampling.setDisabled(True)
        #self.w_list[self.currentSelector-1].frequency_sampling_space.setDisabled(True)
        #self.w_list[self.currentSelector-1].frequency_sampling_space.clear()
        self.w.data_type.setDisabled(True)
        self.w.data_type_combo.setDisabled(True)
        self.w.data_type_combo.setCurrentIndex(0)
        self.w.column_separator.setDisabled(True)
        self.w.column_separator_combo.setDisabled(True)
        self.w.column_separator_combo.setCurrentIndex(0)
        self.w.data_column.setDisabled(True)
        self.w.data_column_space.setDisabled(True)
        self.w.data_column_space.clear()
        self.w.data_units.setDisabled(True)
        self.w.data_units_combo.setDisabled(True)
        self.w.data_units_combo.setCurrentIndex(0)
        self.w.extra_widget.setDisabled(True) 
        self.w.extra_widget_space.setDisabled(True)
        self.w.updateTimeColumn()
        #self.w_list[self.currentSelector-1].time_index_space.setDisabled(True)
        #self.w_list[self.currentSelector-1].time_index_space.clear()
        self.w.time_units.setDisabled(True)
        self.w.time_units_combo.setDisabled(True)
        self.w.time_units_combo.setCurrentIndex(0)
        #self.w_list[self.currentSelector-1].time_format.setDisabled(True)
        #self.w_list[self.currentSelector-1].time_format_combo.setDisabled(True)
        #self.w_list[self.currentSelector-1].time_format_combo.setCurrentIndex(0)
