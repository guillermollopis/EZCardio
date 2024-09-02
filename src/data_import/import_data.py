import sys
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QPushButton, QFrame, QComboBox, QFormLayout, QFileDialog, QStackedWidget
from qtpy import QtCore
from data_import.options import OptionsFrame, OptionsPanel
from data_import.data_preview import DataPreviewFrame, DataPreviewPanel
from data_import.signal_preview import SignalPreviewFrame, SignalPreviewPanel
import pandas as pd
import numpy as np
from qtpy.QtCore import Slot, Signal
from qtpy import QtCore, QtGui, QtWidgets


class ImportData(QWidget):
    
    def __init__(self, multiple=False):
        super().__init__()

        
        #self.setStyleSheet("background-color:white;")

        # Create the main vertical layout
        self.main_layout = QtWidgets.QVBoxLayout(self)

        # Create the scroll area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # Create the widget to hold the frames
        scroll_contents = QtWidgets.QWidget()
        self.layout = QFormLayout(scroll_contents)
        # Set the scroll area contents
        scroll_area.setWidget(scroll_contents)

        self.main_layout.addWidget(scroll_area)

        # Create the main selector layout
        #selector_widget = QWidget(self)
        selector_layout = QHBoxLayout()
        #selector_widget.setStyleSheet("background-color: grey;")

        # Create and add the components for the first line
        selector_left_button = QPushButton("<")
        selector_left_button.setFixedHeight(20)
        selector_layout.addWidget(selector_left_button)

        self.currentSelector = 1
        self.selector_label = QLabel("File " + str(self.currentSelector))
        self.selector_label.setFixedHeight(20)
        selector_layout.addWidget(self.selector_label)

        selector_right_button = QPushButton(">")
        selector_right_button.setFixedHeight(20)
        selector_layout.addWidget(selector_right_button)

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
        selector_layout.addWidget(self.file_type_combo)
        self.file_type_combo.currentTextChanged.connect(self.resetPath)

        add_button = QPushButton("ADD FILE")
        add_button.setStyleSheet("background-color: blue; color: white")
        add_button.clicked.connect(self.open_file_dialog)
        add_button.setFixedHeight(20)
        selector_layout.addWidget(add_button)

        # Create and add the other vertical components
        

        # Path row
        self.currentPaths = []
        if (len(self.currentPaths) < self.currentSelector):
            self.path_label = QLabel("No file selected")
            self.path_label.setAlignment(QtCore.Qt.AlignCenter)
            self.path_label.setFixedHeight(20)
        else:
            self.path_label = QLabel(self.currentPaths[self.currentSelector-1])
            self.path_label.setAlignment(QtCore.Qt.AlignCenter)
            self.path_label.setFixedHeight(20)
            

        if (multiple):
            self.layout.addRow(selector_layout)
            self.layout.addRow(self.path_label)
            self.path_label.setFixedWidth(750)
        else:
            # Create first row for single file
            first_widget = QWidget()
            first_layout = QHBoxLayout()
            first_widget.setLayout(first_layout)
            first_widget.setFixedWidth(750)
            first_layout.addWidget(self.path_label)
            first_layout.addWidget(self.file_type_combo)
            first_layout.addWidget(add_button)
            self.layout.addWidget(first_widget)

        

        # Options container list. StackedWidget where I add frames. Create first and new one when currentSelector increases
        self.stacked_widget = QStackedWidget()
        self.options_frame_list = []
        self.w_list = []
        self.createOptions(False, False)
        self.showOptions(self.currentSelector)
        self.stacked_widget.setFixedHeight(150)

        self.layout.addRow(self.stacked_widget)
        
        # Beat detection option
        #self.addDetectionOptions()

        # Data preview container
        self.addDataPreview()

        # Signal preview container
        self.addSignalPreview()


        # Connect the button signals to the slot functions
        if (multiple):
            selector_left_button.clicked.connect(lambda: self.update_label(self.currentSelector, -1))
            selector_right_button.clicked.connect(lambda: self.update_label(self.currentSelector, 1))

        # Set the layout for the main window
        #self.setLayout(self.layout)
        self.setFixedWidth(850)


    def createOptions(self, is_edf, is_copy):
        
        options_frame = OptionsFrame(main_window=self)
        w = OptionsPanel(frame=options_frame)

        options_frame.layout.addWidget(w)
        options_frame.optionsPanel = w
        
        self.options_frame_list.append(options_frame)
        self.w_list.append(w)
        self.stacked_widget.addWidget(options_frame)

        # Add change updates in options
        w.header_lines_space.textChanged.connect(self.testSignalPreview)
        w.data_column_space.textChanged.connect(self.testSignalPreview)
        w.time_units_combo.currentTextChanged.connect(self.testSignalPreview)
        w.column_separator_combo.currentTextChanged.connect(self.testSignalPreview)
        w.data_units_combo.currentTextChanged.connect(self.updateAxis)

        if is_copy: # same values as previous one
            w.header_lines_space.setText(self.w_list[self.currentSelector-2].header_lines_space.text())
            w.data_column_space.setText(self.w_list[self.currentSelector-2].data_column_space.text())
            w.column_separator_combo.setCurrentIndex(self.w_list[self.currentSelector-2].column_separator_combo.currentIndex())
            #w.extra_widget = self.w_list[self.currentSelector-2].extra_widget
            #w.extra_widget_space = self.w_list[self.currentSelector-2].extra_widget_space
            w.data_type_combo.setCurrentIndex(self.w_list[self.currentSelector-2].data_type_combo.currentIndex())
            w.data_units_combo.setCurrentIndex(self.w_list[self.currentSelector-2].data_units_combo.currentIndex())
            w.time_units_combo.setCurrentIndex(self.w_list[self.currentSelector-2].time_units_combo.currentIndex())

            try:
                w.frequency_sampling_space.setEnabled(self.w_list[self.currentSelector-2].frequency_sampling_space.isEnabled())
                w.frequency_sampling_space.setText(self.w_list[self.currentSelector-2].frequency_sampling_space.text())
            except:
                w.time_index_space.setEnabled(self.w_list[self.currentSelector-2].time_index_space.isEnabled())
                w.time_index_space.setText(self.w_list[self.currentSelector-2].time_index_space.text())
                w.time_format_combo.setEnabled(self.w_list[self.currentSelector-2].time_format_combo.isEnabled())
                w.time_format_combo.setCurrentIndex(self.w_list[self.currentSelector-2].time_format_combo.currentIndex())
                

    def testSignalPreview(self):
        self.updatePreviews()

    def showOptions(self, current_selector, is_copy=False):
        self.stacked_widget.setCurrentWidget(self.options_frame_list[current_selector-1])
        self.w_list[self.currentSelector-1].data_column_space.textEdited.connect(self.testSignalPreview)
            

    def addDetectionOptions(self):
        # title
        title_label = QLabel("Beat detection option")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.layout.addRow(title_label)

        # options
        self.detection_option = QComboBox()
        self.detection_option.addItem("Pan-Tompkins")
        self.detection_option.addItem("RPNet")
        self.detection_option.addItem("ECG2RR")
        self.detection_option.setFixedHeight(20)
        self.layout.addRow(self.detection_option)

    def addDataPreview(self, path=None, file_type=None):

        delimiter = ""
        if (self.file_type_combo.currentText() not in ["edf", "hea", "mat", "fit"]):
            separator = self.w_list[self.currentSelector-1].column_separator_combo.currentText()
            if (separator == "Semicolon"):
                delimiter = ";"
            elif (separator == "Comma"):
                delimiter = ","
            elif (separator == "Space"):
                delimiter = " "
            elif (separator == "Tab"):
                delimiter = "|"
            else:
                delimiter = ""

        file_type = self.file_type_combo.currentText()

        self.data_preview_frame = DataPreviewFrame(main_window=self)
        self.dp = DataPreviewPanel(frame=self.data_preview_frame, path=path, file_type=file_type, delimiter=delimiter)

        self.data_preview_frame.layout.addWidget(self.dp)
        self.data_preview_frame.optionsPanel = self.dp
        self.layout.addRow(self.data_preview_frame)


    def addSignalPreview(self, path=None, file_type=None):

        column = self.w_list[self.currentSelector-1].data_column_space.text()
        data_units = self.w_list[self.currentSelector-1].data_units_combo.currentText()
        frequency = 0
        frequencyColumn = ""
        dateType = ""
        if (self.w_list[self.currentSelector-1].time_units_combo.currentText().lower() == "none"):
            frequency = self.w_list[self.currentSelector-1].frequency_sampling_space.text()
        else:
            frequencyColumn = self.w_list[self.currentSelector-1].time_index_space.text()
            if (self.w_list[self.currentSelector-1].time_units_combo.currentText().lower() == "datetime"):
                dateType = self.w_list[self.currentSelector-1].time_format_combo.currentText()
            else:
                dateType = self.w_list[self.currentSelector-1].time_units_combo.currentText().lower()

        delimiter = ""
        header_lines = 0
        if (self.file_type_combo.currentText() not in ["edf", "hea", "mat", "fit"]):
            header_lines = self.w_list[self.currentSelector-1].header_lines_space.text()
            separator = self.w_list[self.currentSelector-1].column_separator_combo.currentText()
            if (separator == "Semicolon"):
                delimiter = ";"
            elif (separator == "Comma"):
                delimiter = ","
            elif (separator == "Space"):
                delimiter = " "
            elif (separator == "Tab"):
                delimiter = "|"
            else:
                delimiter = ""

        file_type = self.file_type_combo.currentText()

        self.signal_preview_frame = SignalPreviewFrame(main_window=self)
        self.sp = SignalPreviewPanel(frame=self.signal_preview_frame, path=path, file_type=file_type, header_lines=header_lines, column=column, delimiter=delimiter, frequency=frequency, frequencyColumn = frequencyColumn, dateType=dateType, data_units=data_units)

        try:
            if file_type in ["edf", "hea", "ecg"]:
                import pyedflib as pyedflib
                f = pyedflib.EdfReader(path)
                frequency = f.getSampleFrequency(int(column)-1)
                self.w_list[self.currentSelector-1].frequency_sampling_space.setText(str(frequency))
        except:
            pass

        self.signal_preview_frame.layout.addWidget(self.sp)
        self.signal_preview_frame.optionsPanel = self.sp
        self.layout.addRow(self.signal_preview_frame)


    def updateAxis(self):
        self.sp.ax.set_ylabel(f"ECG ({self.w_list[self.currentSelector-1].data_units_combo.currentText()})")
        self.sp.canvas.draw()

    def update_label(self, current_value, value):
        new_value = current_value + value
        if (new_value >= 1):

            if (value == -1 or len(self.currentPaths) >= self.currentSelector):
                
                self.currentSelector = new_value
                self.selector_label.setText("File " + str(new_value))
                if (value == -1 or len(self.currentPaths) == (new_value+1)):
                    
                    self.path_label.setText(self.currentPaths[new_value-1])
                    self.updatePreviews()
                    self.showOptions(self.currentSelector)

                else:
                    self.path_label.setText("No file selected")
                    if (self.file_type_combo.currentText() in ["edf", "hea", "mat", "fit"]):
                        self.createOptions(True, True)
                    else:
                        self.createOptions(False, True)
                    self.updatePreviews()
                    self.showOptions(self.currentSelector, True)
                

                # The data type must be the same, so it is disabled after choosing
                if (new_value != 1):
                    self.file_type_combo.setDisabled(True)
                else:
                    self.file_type_combo.setDisabled(False)

    def updatePreviews(self):
        # Delete both frame previews and last button
        self.layout.removeRow(self.data_preview_frame)
        self.layout.removeRow(self.signal_preview_frame)
        # Create the three things again
        if (len(self.currentPaths) >= self.currentSelector):
            self.addDataPreview(self.currentPaths[self.currentSelector-1], file_type=self.file_type_combo.currentText())
            self.addSignalPreview(self.currentPaths[self.currentSelector-1], file_type=self.file_type_combo.currentText())
        else:
            self.addDataPreview(None)
            self.addSignalPreview(None)
        # Add button functionality
        # Show table if csv


    def open_file_dialog(self):
        file_type = self.file_type_combo.currentText().lower()
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        
        if self.file_type_combo.currentText()=="Other delimiter":
            file_filter = f"All delimiter Files (*.*)"

            file_name, _ = QFileDialog.getOpenFileName(
                self, f"Select {file_type.upper()} File", "", file_filter, options=options
            )
        else:
            file_filter = f"{file_type.upper()} Files (*.{file_type})"

            file_name, _ = QFileDialog.getOpenFileName(
                self, f"Select {file_type.upper()} File", "", file_filter, options=options
            )
        if file_name:
            # Add path if it does not exist in current selector
            if (len(self.currentPaths) == self.currentSelector-1):
                self.currentPaths.append(file_name)
                self.path_label.setText(self.currentPaths[self.currentSelector-1])
                self.enableOptions()
                self.updatePreviews()
            # If path is just replacing, just set path label, disable and enable options and update previews
            else:
                self.currentPaths.remove(self.currentPaths[self.currentSelector-1])
                self.currentPaths.append(file_name)
                self.path_label.setText(self.currentPaths[self.currentSelector-1])
                # Enable options to edit when file is selected
                self.updatePreviews()

    def resetPath(self):
        self.currentPaths.clear()
        self.options_frame_list.clear()
        self.w_list.clear()
        self.path_label.setText("No file selected")
        if (self.file_type_combo.currentText() in ["edf", "hea", "mat", "fit"]):
            self.createOptions(True, False)
        else:
            self.createOptions(False, False)
        self.disableOptions()
        self.showOptions(self.currentSelector)
        self.updatePreviews()

    def enableOptions(self):
        if (self.file_type_combo.currentText() in ["edf", "hea", "mat", "fit"]):
            self.w_list[self.currentSelector-1].data_type.setDisabled(False)
            self.w_list[self.currentSelector-1].data_type_combo.setDisabled(False)
            self.w_list[self.currentSelector-1].data_column.setDisabled(False)
            self.w_list[self.currentSelector-1].data_column_space.setDisabled(False)
            self.w_list[self.currentSelector-1].data_units.setDisabled(False)
            self.w_list[self.currentSelector-1].data_units_combo.setDisabled(False)
            if (self.file_type_combo.currentText() not in ["edf"]):
                self.w_list[self.currentSelector-1].time_units.setDisabled(False)
                self.w_list[self.currentSelector-1].time_units_combo.setDisabled(False)
            self.w_list[self.currentSelector-1].extra_widget.setDisabled(False)
            self.w_list[self.currentSelector-1].extra_widget_space.setDisabled(False)

        else: # for txt and csv
            self.w_list[self.currentSelector-1].header_lines.setDisabled(False)
            self.w_list[self.currentSelector-1].header_lines_space.setDisabled(False)
            self.w_list[self.currentSelector-1].data_type.setDisabled(False)
            self.w_list[self.currentSelector-1].data_type_combo.setDisabled(False)
            self.w_list[self.currentSelector-1].column_separator.setDisabled(False)
            self.w_list[self.currentSelector-1].column_separator_combo.setDisabled(False)
            if (self.file_type_combo.currentText() == "txt"):
                self.w_list[self.currentSelector-1].column_separator_combo.setCurrentIndex(2)
            elif (self.file_type_combo.currentText() == "csv"):
                self.w_list[self.currentSelector-1].column_separator_combo.setCurrentIndex(1)
            elif (self.file_type_combo.currentText() == "dat"):
                self.w_list[self.currentSelector-1].column_separator_combo.setCurrentIndex(0)
            self.w_list[self.currentSelector-1].data_column.setDisabled(False)
            self.w_list[self.currentSelector-1].data_column_space.setDisabled(False)
            self.w_list[self.currentSelector-1].data_units.setDisabled(False)
            self.w_list[self.currentSelector-1].data_units_combo.setDisabled(False)
            self.w_list[self.currentSelector-1].time_units.setDisabled(False)
            self.w_list[self.currentSelector-1].time_units_combo.setDisabled(False)
            self.w_list[self.currentSelector-1].extra_widget.setDisabled(False)
            self.w_list[self.currentSelector-1].extra_widget_space.setDisabled(False)


    def disableOptions(self):
        if (self.file_type_combo.currentText() in ["edf", "hea", "mat", "fit"]):
            self.w_list[self.currentSelector-1].data_type.setDisabled(True)
            self.w_list[self.currentSelector-1].data_type_combo.setDisabled(True)
            self.w_list[self.currentSelector-1].data_type_combo.setCurrentIndex(0)
            self.w_list[self.currentSelector-1].data_column.setDisabled(True)
            self.w_list[self.currentSelector-1].data_column_space.setDisabled(True)
            self.w_list[self.currentSelector-1].data_column_space.clear()
            self.w_list[self.currentSelector-1].data_units.setDisabled(True)
            self.w_list[self.currentSelector-1].data_units_combo.setDisabled(True)
            self.w_list[self.currentSelector-1].data_units_combo.setCurrentIndex(0)
            self.w_list[self.currentSelector-1].extra_widget.setDisabled(True) 
            self.w_list[self.currentSelector-1].extra_widget_space.setDisabled(True)
            self.w_list[self.currentSelector-1].updateTimeColumn()
            self.w_list[self.currentSelector-1].time_units.setDisabled(True)
            self.w_list[self.currentSelector-1].time_units_combo.setDisabled(True)
            self.w_list[self.currentSelector-1].time_units_combo.setCurrentIndex(0)

        else: # for txt and csv
            self.w_list[self.currentSelector-1].header_lines.setDisabled(True)
            self.w_list[self.currentSelector-1].header_lines_space.setDisabled(True)
            self.w_list[self.currentSelector-1].header_lines_space.clear()
            self.w_list[self.currentSelector-1].data_type.setDisabled(True)
            self.w_list[self.currentSelector-1].data_type_combo.setDisabled(True)
            self.w_list[self.currentSelector-1].data_type_combo.setCurrentIndex(0)
            self.w_list[self.currentSelector-1].column_separator.setDisabled(True)
            self.w_list[self.currentSelector-1].column_separator_combo.setDisabled(True)
            self.w_list[self.currentSelector-1].column_separator_combo.setCurrentIndex(0)
            self.w_list[self.currentSelector-1].data_column.setDisabled(True)
            self.w_list[self.currentSelector-1].data_column_space.setDisabled(True)
            self.w_list[self.currentSelector-1].data_column_space.clear()
            self.w_list[self.currentSelector-1].data_units.setDisabled(True)
            self.w_list[self.currentSelector-1].data_units_combo.setDisabled(True)
            self.w_list[self.currentSelector-1].data_units_combo.setCurrentIndex(0)
            self.w_list[self.currentSelector-1].extra_widget.setDisabled(True) 
            self.w_list[self.currentSelector-1].extra_widget_space.setDisabled(True)
            self.w_list[self.currentSelector-1].updateTimeColumn()
            self.w_list[self.currentSelector-1].time_units.setDisabled(True)
            self.w_list[self.currentSelector-1].time_units_combo.setDisabled(True)
            self.w_list[self.currentSelector-1].time_units_combo.setCurrentIndex(0)

    

#if __name__ == "__main__":
#    app = QApplication(sys.argv)
#    window = ImportData()
#    window.show()
#    sys.exit(app.exec_())




