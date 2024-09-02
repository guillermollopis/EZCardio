import sys
import json
from PyQt5.QtWidgets import QMessageBox, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLabel, QLineEdit, QDesktopWidget, QFrame, QStackedWidget, QComboBox, QCheckBox
from qtpy import QtCore, QtGui
from pathlib import Path
from utils.utils_general import resource_path


class ShortcutsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Shortcuts")
        # Get the desktop widget
        desktop = QApplication.desktop()

        # Get the screen height
        screen_height = desktop.screenGeometry().height()

        # Calculate the new height as 30% of the screen height
        new_height = int(screen_height * 0.3)
        
        self.resize(400, new_height)  # Set the window size (width, height)
        self.move(QDesktopWidget().availableGeometry().center() - self.rect().center())  # Set the starting position of the window (x, y)

        # Set the fixed size of the window
        self.setFixedSize(850, new_height)

        # Load settings from JSON file
        with open(resource_path(Path('settings.json'))) as f:
            self.settings = json.load(f)

        # Create layout for the settings window
        layout = QHBoxLayout()

        # Create option blocks on the left
        option_block_layout = QVBoxLayout()

        self.button0 = QPushButton("Peak editing")
        self.button0.clicked.connect(lambda: self.show_suboptions(0))
        option_block_layout.addWidget(self.button0)
        
        self.button1 = QPushButton("Noise editing")
        self.button1.clicked.connect(lambda: self.show_suboptions(1))
        option_block_layout.addWidget(self.button1)

        self.button2 = QPushButton("Sample editing")
        self.button2.clicked.connect(lambda: self.show_suboptions(2))
        option_block_layout.addWidget(self.button2)

        # Add a stretch to push the buttons to the top
        option_block_layout.addStretch()


        # Create a vertical line separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)

        # Create suboptions on the right
        self.suboptions_widget_total_layout = QVBoxLayout()
        self.suboptions_widget_total = QWidget()
        self.suboptions_widget_total.setLayout(self.suboptions_widget_total_layout)
        self.suboptions_widget = QStackedWidget()
        
        # 1) create pre-processing suboptions
        self.peak_suboptions = QVBoxLayout()
        self.peak_suboptions_widget = QWidget()
        self.peak_suboptions_widget.setLayout(self.peak_suboptions)
        # NOISE DETECTION
        # Add peak
        add_peak_layout = QHBoxLayout()
        add_peak_widget = QWidget()
        add_peak_widget.setLayout(add_peak_layout)
        self.add_peak_label2_left = QLabel("Add peak: ")
        self.add_peak_space = QLabel()
        self.add_peak_space.setText('Left click')
        add_peak_layout.addWidget(self.add_peak_label2_left)
        add_peak_layout.addWidget(self.add_peak_space)
        self.peak_suboptions.addWidget(add_peak_widget)
        # Delete peak
        delete_peak_layout = QHBoxLayout()
        delete_peak_widget = QWidget()
        delete_peak_widget.setLayout(delete_peak_layout)
        self.delete_peak_label2_left = QLabel("Delete peak: ")
        self.delete_peak_space = QLabel()
        self.delete_peak_space.setText('Right click')
        delete_peak_layout.addWidget(self.delete_peak_label2_left)
        delete_peak_layout.addWidget(self.delete_peak_space)
        self.peak_suboptions.addWidget(delete_peak_widget)
        # Add interpolation
        add_interpolation_layout = QHBoxLayout()
        add_interpolation_widget = QWidget()
        add_interpolation_widget.setLayout(add_interpolation_layout)
        self.add_interpolation_label2_left = QLabel("Interpolate peak: ")
        self.add_interpolation_space = QLabel()
        self.add_interpolation_space.setText('CTRL + Left click')
        add_interpolation_layout.addWidget(self.add_interpolation_label2_left)
        add_interpolation_layout.addWidget(self.add_interpolation_space)
        self.peak_suboptions.addWidget(add_interpolation_widget)
        # Delete interpolation
        delete_interpolation_layout = QHBoxLayout()
        delete_interpolation_widget = QWidget()
        delete_interpolation_widget.setLayout(delete_interpolation_layout)
        self.delete_interpolation_label2_left = QLabel("Delete interpolation: ")
        self.delete_interpolation_space = QLabel()
        self.delete_interpolation_space.setText('CTRL + Right click')
        delete_interpolation_layout.addWidget(self.delete_interpolation_label2_left)
        delete_interpolation_layout.addWidget(self.delete_interpolation_space)
        self.peak_suboptions.addWidget(delete_interpolation_widget)


        # Add a stretch to push the buttons to the top
        self.peak_suboptions.addStretch()



        # 2) noise editing
        self.noise_suboptions = QVBoxLayout()
        self.noise_suboptions_widget = QWidget()
        self.noise_suboptions_widget.setLayout(self.noise_suboptions)
        # NOISE DETECTION
        # Add noise
        add_noise_layout = QHBoxLayout()
        add_noise_widget = QWidget()
        add_noise_widget.setLayout(add_noise_layout)
        self.add_noise_label2_left = QLabel("Add noise interval: ")
        self.add_noise_space = QLabel()
        self.add_noise_space.setText('CTRL + Left click')
        add_noise_layout.addWidget(self.add_noise_label2_left)
        add_noise_layout.addWidget(self.add_noise_space)
        self.noise_suboptions.addWidget(add_noise_widget)
        # Delete noise
        delete_noise_layout = QHBoxLayout()
        delete_noise_widget = QWidget()
        delete_noise_widget.setLayout(delete_noise_layout)
        self.delete_noise_label2_left = QLabel("Delete noise interval: ")
        self.delete_noise_space = QLabel()
        self.delete_noise_space.setText('CTRL + Right click')
        delete_noise_layout.addWidget(self.delete_noise_label2_left)
        delete_noise_layout.addWidget(self.delete_noise_space)
        self.noise_suboptions.addWidget(delete_noise_widget)
        # Add interpolation
        move_noise_layout = QHBoxLayout()
        move_noise_widget = QWidget()
        move_noise_widget.setLayout(move_noise_layout)
        self.move_noise_label2_left = QLabel("Move noise interval: ")
        self.move_noise_space = QLabel()
        self.move_noise_space.setText('SHIFT + Left click')
        move_noise_layout.addWidget(self.move_noise_label2_left)
        move_noise_layout.addWidget(self.move_noise_space)
        self.noise_suboptions.addWidget(move_noise_widget)

        # Add a stretch to push the buttons to the top
        self.noise_suboptions.addStretch()


        # 3) sample editing
        self.sample_suboptions = QVBoxLayout()
        self.sample_suboptions_widget = QWidget()
        self.sample_suboptions_widget.setLayout(self.sample_suboptions)
        # sample DETECTION
        # Add sample
        add_sample_layout = QHBoxLayout()
        add_sample_widget = QWidget()
        add_sample_widget.setLayout(add_sample_layout)
        self.add_sample_label2_left = QLabel("Add sample interval: ")
        self.add_sample_space = QLabel()
        self.add_sample_space.setText('CTRL + Left click')
        add_sample_layout.addWidget(self.add_sample_label2_left)
        add_sample_layout.addWidget(self.add_sample_space)
        self.sample_suboptions.addWidget(add_sample_widget)
        # Delete sample
        delete_sample_layout = QHBoxLayout()
        delete_sample_widget = QWidget()
        delete_sample_widget.setLayout(delete_sample_layout)
        self.delete_sample_label2_left = QLabel("Delete sample interval: ")
        self.delete_sample_space = QLabel()
        self.delete_sample_space.setText('CTRL + Right click')
        delete_sample_layout.addWidget(self.delete_sample_label2_left)
        delete_sample_layout.addWidget(self.delete_sample_space)
        self.sample_suboptions.addWidget(delete_sample_widget)
        # Add interpolation
        move_sample_layout = QHBoxLayout()
        move_sample_widget = QWidget()
        move_sample_widget.setLayout(move_sample_layout)
        self.move_sample_label2_left = QLabel("Move sample interval: ")
        self.move_sample_space = QLabel()
        self.move_sample_space.setText('SHIFT + Left click')
        move_sample_layout.addWidget(self.move_sample_label2_left)
        move_sample_layout.addWidget(self.move_sample_space)
        self.sample_suboptions.addWidget(move_sample_widget)


        # Add a stretch to push the buttons to the top
        self.sample_suboptions.addStretch()

        # add to main suboption frame
        self.suboptions_widget.addWidget(self.peak_suboptions_widget)
        self.suboptions_widget.addWidget(self.noise_suboptions_widget)
        self.suboptions_widget.addWidget(self.sample_suboptions_widget)

        self.suboptions_widget_total_layout.addWidget(self.suboptions_widget)

        layout.addLayout(option_block_layout)
        layout.addWidget(separator)
        layout.addWidget(self.suboptions_widget_total)

        self.setLayout(layout)

    def show_suboptions(self, option):
        for button in [self.button0, self.button1, self.button2]:
            button.setStyleSheet("background-color: None")

        if (option == 0):
            self.button0.setStyleSheet("background-color: lightblue")
            selected_widget = self.peak_suboptions_widget
        elif(option == 1):
            self.button1.setStyleSheet("background-color: lightblue")
            selected_widget = self.noise_suboptions_widget
        elif(option == 2):
            self.button2.setStyleSheet("background-color: lightblue")
            selected_widget = self.sample_suboptions_widget

        self.suboptions_widget.setCurrentWidget(selected_widget)
        

   