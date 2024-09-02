from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtWidgets import QPushButton, QCheckBox, QApplication
from functools import partial
from logic.operation_mode.operation_mode import Modes, Mode
from config import shortcuts


class ButtonFrame(QtWidgets.QFrame):

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
        self.buttonPanel: ButtonPanel = None
        self.dragStartPos = QtCore.QPoint()
        self.drag = None

    def updateHeight(self):
        self.setFixedHeight(self.n)



class ButtonPanel(QtWidgets.QWidget):

    def __init__(self, frame: ButtonFrame):
        super().__init__()
        
        self.setParent(frame)

        
        from gui import PALMS
        from config import tooltips
        layout = QtWidgets.QHBoxLayout()
        # Create the buttons and set their properties
        self.button1 = QPushButton("Edit peak")
        self.button1.setObjectName("Edit peak")
        self.button1.setStyleSheet("background-color: blue; color: white;")
        self.button1.setToolTip(tooltips.edit_peak_shortcuts)
        #if PALMS.get().RR_ONLY:
        #    self.button1.setDisabled(True)
        self.button2 = QPushButton("Edit noise")
        self.button2.setObjectName("Edit noise")
        self.button2.setStyleSheet("background-color: blue; color: white;")
        self.button2.setToolTip(tooltips.edit_noise_shortcuts)
        self.button3 = QPushButton("Edit samples")
        self.button3.setObjectName("Edit samples")
        self.button3.setStyleSheet("background-color: blue; color: white;")
        self.button3.setToolTip(tooltips.edit_sample_shortcuts)

        
        if PALMS.get().RR_ONLY is False:
            self.checkbox = QCheckBox("Align graphs", self)
            self.checkbox.setChecked(True)
            self.checkbox.stateChanged.connect(self.toggle_zoom_synchronization)

        # Resize down button
        self.toogle_down_button = QPushButton()
        self.toogle_down_button.setFixedSize(50, 50)
        from utils.utils_general import resource_path
        import os
        import sys
        from pathlib import Path
        try:
            resize_icon = QtGui.QIcon(os.path.join(sys._MEIPASS,"config/icons/expand_up_down.png"))
        except:
            resize_icon = QtGui.QIcon(os.path.join(os.path.abspath("."),"config/icons/expand_up_down.png"))
        self.toogle_down_button.setIcon(resize_icon)
        self.toogle_down_button.setToolTip("Show or hide results")
        self.toogle_down_button.clicked.connect(self.expandWidget)

        # Create the layout and add the buttons to it
        if PALMS.get().RR_ONLY is False:
            layout.addWidget(self.checkbox)
        layout.addWidget(self.button1)
        layout.addWidget(self.button2)
        layout.addWidget(self.button3)
        

        # shortcuts button
        information_button = QPushButton()
        information_button.setFixedSize(50, 50)  # Set a fixed size for the icon buttons
        information_icon = QtGui.QIcon("config/icons/information.jpg")
        information_button.setIcon(information_icon)
        #layout.addWidget(information_button)

        layout.addWidget(self.toogle_down_button)
        
        frame.setLayout(layout)

        self.current_button = 0  # current active button
        self.button1.clicked.connect(self.button1_action)
        self.button2.clicked.connect(self.button2_action)
        self.button3.clicked.connect(self.button3_action)
        information_button.clicked.connect(self.open_shortcuts)


    def expandWidget(self):
        self.parent().parent().viewer.toggle_resize_down() 

    def open_shortcuts(self):
        settings_window = shortcuts.ShortcutsWindow()
        
        settings_window.show()

    # Set up the actions for each button
    def button1_action(self):
        if (self.current_button == 1):
            mode = Modes.browse.value
            Mode.switch_mode(Modes[mode])
            self.current_button = 0
            self.button1.setStyleSheet("background-color: blue; color: white;")
        else:
            mode = Modes.annotation.value
            Mode.switch_mode(Modes[mode])
            self.current_button = 1
            self.button1.setStyleSheet("background-color: red; color: white;")
            self.button2.setStyleSheet("background-color: blue; color: white;")
            self.button3.setStyleSheet("background-color: blue; color: white;")

    def button2_action(self):
        if (self.current_button == 2):
            mode = Modes.browse.value
            Mode.switch_mode(Modes[mode])
            self.current_button = 0
            self.button2.setStyleSheet("background-color: blue; color: white;")
        else:
            mode = Modes.noise_partition.value
            Mode.switch_mode(Modes[mode])
            self.current_button = 2
            self.button2.setStyleSheet("background-color: red; color: white;")
            self.button1.setStyleSheet("background-color: blue; color: white;")
            self.button3.setStyleSheet("background-color: blue; color: white;")


    def button3_action(self):
        if (self.current_button == 3):
            mode = Modes.browse.value
            Mode.switch_mode(Modes[mode])
            self.current_button = 0
            self.button3.setStyleSheet("background-color: blue; color: white;")
        else:
            mode = Modes.partition.value
            Mode.switch_mode(Modes[mode])
            self.current_button = 3
            self.button3.setStyleSheet("background-color: red; color: white;")
            self.button1.setStyleSheet("background-color: blue; color: white;")
            self.button2.setStyleSheet("background-color: blue; color: white;")


    def toggle_zoom_synchronization(self, state):
        from gui.viewer import Viewer
        
        if (state == 2):
            Viewer.get().synchronize_graphs()
        else:
            Viewer.get().desynchronize_graphs()

