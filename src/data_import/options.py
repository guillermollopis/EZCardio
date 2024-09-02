from qtpy import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget


class OptionsFrame(QtWidgets.QFrame):

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
        self.n = 150
        self.updateHeight()
        self.setFixedWidth(750)

        # Drag and Drop Related
        # TODO: only accept drag/drop of other Frames (through MIME data)
        self.setAcceptDrops(True)
        self.optionsPanel: OptionsPanel = None
        self.dragStartPos = QtCore.QPoint()
        self.drag = None

    def updateHeight(self):
        self.setFixedHeight(self.n)



class OptionsPanel(QtWidgets.QWidget):

    def __init__(self, frame: OptionsFrame, split=False):
        super().__init__()
        
        self.setParent(frame)
        #self.setStyleSheet("background-color: grey;")

        layout = QtWidgets.QGridLayout()

        # Create three vertical separators using QFrames
        separator1 = QtWidgets.QFrame()
        separator1.setFrameShape(QtWidgets.QFrame.VLine)
        separator2 = QtWidgets.QFrame()
        separator2.setFrameShape(QtWidgets.QFrame.VLine)

        # Create labels
        self.header_lines = QtWidgets.QLabel("Header lines")
        self.header_lines.setDisabled(True)
        if (split == True):
            self.data_type = QtWidgets.QLabel("Number of files")
        else:
            self.data_type = QtWidgets.QLabel("Data type")
        self.data_type.setDisabled(True)
        
        self.column_separator = QtWidgets.QLabel("Column separator")
        self.column_separator.setDisabled(True)
        self.data_column = QtWidgets.QLabel("Data column label")
        self.data_column.setDisabled(True)
        self.data_units = QtWidgets.QLabel("Data units")
        self.data_units.setDisabled(True)
        
        # Create the widget that will be shown based on the main ComboBox selection
        self.extra_widget = QWidget()
        self.extra_widget.setDisabled(True)
        self.extra_widget.setLayout(QtWidgets.QVBoxLayout())
        
        self.extra_widget_space = QWidget()
        self.extra_widget_space.setDisabled(True)
        self.extra_widget_space.setLayout(QtWidgets.QVBoxLayout())
        
        self.time_units = QtWidgets.QLabel("Time units")
        self.time_units.setDisabled(True)
        
        
        # Create text spaces
        self.header_lines_space = QtWidgets.QLineEdit()
        self.header_lines_space.setDisabled(True)
        
        self.data_type_combo = QtWidgets.QComboBox()
        if (split == False):
            self.data_type_combo.addItem("ECG")
            self.data_type_combo.addItem("RR")
            self.data_type_combo.addItem("PPG")
            self.data_type_combo.currentTextChanged.connect(self.updateDataUnitsCombo)
        else:
            self.data_type_combo.addItem("2")
            self.data_type_combo.addItem("3")
            self.data_type_combo.addItem("4")
            self.data_type_combo.addItem("5")
            self.data_type_combo.addItem("6")
            self.data_type_combo.addItem("7")
            self.data_type_combo.addItem("8")
            self.data_type_combo.addItem("9")
            self.data_type_combo.addItem("10")
        self.data_type_combo.setDisabled(True)
        self.column_separator_combo = QtWidgets.QComboBox()
        self.column_separator_combo.addItem("Tab/Space")
        self.column_separator_combo.addItem("Comma")
        self.column_separator_combo.addItem("Semicolon")
        self.column_separator_combo.addItem("Tab")
        self.column_separator_combo.addItem("Space")
        self.column_separator_combo.setDisabled(True)
        self.data_column_space = QtWidgets.QLineEdit()
        self.data_column_space.setDisabled(True)
        self.data_units_combo = QtWidgets.QComboBox()
        self.data_units_combo.addItem("V")
        self.data_units_combo.addItem("mV")
        self.data_units_combo.setDisabled(True)
        
        self.time_units_combo = QtWidgets.QComboBox()
        self.time_units_combo.addItem("None")
        self.time_units_combo.addItem("s")
        self.time_units_combo.addItem("ms")
        self.time_units_combo.addItem("DateTime")
        self.time_units_combo.setDisabled(True)
        self.time_units_combo.currentTextChanged.connect(self.updateTimeColumn)
        
        

        # Create the layout and add the buttons to it
        # First block
        layout.addWidget(self.header_lines, 0, 0)
        
        layout.addWidget(self.column_separator, 1, 0)
        layout.addWidget(self.header_lines_space, 0, 1)
        
        layout.addWidget(self.column_separator_combo, 1, 1)
        layout.addWidget(separator1, 0, 2, 3, 1)

        # Second block
        layout.addWidget(self.data_type, 0, 3)
        layout.addWidget(self.data_column, 1, 3)
        layout.addWidget(self.data_units, 2, 3)
        layout.addWidget(self.data_type_combo, 0, 4)
        layout.addWidget(self.data_column_space, 1, 4)
        layout.addWidget(self.data_units_combo, 2, 4)
        layout.addWidget(separator2, 0, 5, 3, 1)

        # Third block
        layout.addWidget(self.time_units, 0, 6)
        layout.addWidget(self.extra_widget, 1, 6, 2, 1)
        layout.addWidget(self.time_units_combo, 0, 7)
        layout.addWidget(self.extra_widget_space, 1, 7, 2, 1)
        self.updateTimeColumn()
        
        frame.setLayout(layout)

    def updateTimeColumn(self):

        layout = self.extra_widget.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                widget.deleteLater()

        layout = self.extra_widget_space.layout()
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                widget.deleteLater()

        #self.extra_widget.clear()
        #self.extra_widget_space.clear()

        if (self.time_units_combo.currentText().lower() == "none"):
            self.frequency_sampling = QtWidgets.QLabel("Frequency")
            #self.frequency_sampling.setDisabled(True)
            
            self.extra_widget.layout().addWidget(self.frequency_sampling)

            self.frequency_sampling_space = QtWidgets.QLineEdit()
            #self.frequency_sampling_space.setDisabled(True)
            
            self.extra_widget_space.layout().addWidget(self.frequency_sampling_space)
            self.frequency_sampling_space.textChanged.connect(self.updateImport)
        else:
            
            self.time_index_column = QtWidgets.QLabel("Time column label")
            #self.time_index_column.setDisabled(True)

            self.time_index_space = QtWidgets.QLineEdit()
            
            #self.time_index_space.setDisabled(True)

            self.time_format = QtWidgets.QLabel("Time format")
            self.time_format.setDisabled(True)
            

            self.time_format_combo = QtWidgets.QComboBox()
            self.time_format_combo.addItem("HH:MM:SS.FFF")
            self.time_format_combo.addItem("dd.mm.yyyy HH:MM:SS:FFF")
            self.time_format_combo.addItem("yyyy.mm.dd HH:MM:SS.FFF")
            self.time_format_combo.addItem("mm.dd.yyyy HH:MM:SS.FFF")
            self.time_format_combo.addItem("dd/mm/yyyy HH:MM:SS:FFF")
            self.time_format_combo.addItem("yyyy/mm/dd HH:MM:SS.FFF")
            self.time_format_combo.addItem("mm/dd/yyyy HH:MM:SS.FFF")
            self.time_format_combo.addItem("dd-mm-yyyy HH:MM:SS:FFF")
            self.time_format_combo.addItem("yyyy-mm-dd HH:MM:SS.FFF")
            self.time_format_combo.addItem("mm-dd-yyyy HH:MM:SS.FFF")
            self.time_format_combo.addItem("yyyy-mm-ddTHH:MM:SS.FFF")
            self.time_format_combo.addItem("dd.m.yyyy HH:MM:SS:FFF")
            self.time_format_combo.setDisabled(True)

            self.extra_widget.layout().addWidget(self.time_index_column)
            self.extra_widget.layout().addWidget(self.time_format)
            self.extra_widget_space.layout().addWidget(self.time_index_space)
            self.extra_widget_space.layout().addWidget(self.time_format_combo)

            self.updateTimeIndex()
            self.time_index_space.textChanged.connect(self.updateImport)
            self.time_format_combo.currentTextChanged.connect(self.updateImport)

    def updateImport(self):
        previos_text = self.data_column_space.text()
        self.data_column_space.setText("0")
        self.data_column_space.setText(previos_text)
        #self.data_column_space.setText("100")

    def updateDataUnitsCombo(self):
        selectedOption = self.data_type_combo.currentText().lower()

        if (selectedOption == "ecg"):
            self.data_units_combo.clear()
            self.data_units_combo.addItems(["V", "mV"])
        elif (selectedOption == "rr"):
            self.data_units_combo.clear()
            self.data_units_combo.addItems(["s", "ms"])


    def updateTimeIndex(self):
        
        if (self.time_units_combo.currentText().lower() == "datetime"):
            self.time_format.setDisabled(False)
            self.time_format_combo.setDisabled(False)
        else:
            self.time_format.setDisabled(True)
            self.time_format_combo.setDisabled(True)