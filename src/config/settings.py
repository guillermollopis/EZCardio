import sys
import json
from PyQt5.QtWidgets import QMessageBox, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPushButton, QLabel, QLineEdit, QDesktopWidget, QFrame, QStackedWidget, QComboBox, QCheckBox
from qtpy import QtCore, QtGui
from pathlib import Path
from utils.utils_general import resource_path


class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Settings")
        # Get the desktop widget
        desktop = QApplication.desktop()

        # Get the screen height
        screen_height = desktop.screenGeometry().height()

        # Calculate the new height as 80% of the screen height
        new_height = int(screen_height * 0.8)
        
        self.resize(850, new_height)  # Set the window size (width, height)
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

        self.button0 = QPushButton("User information")
        self.button0.clicked.connect(lambda: self.show_suboptions(0))
        option_block_layout.addWidget(self.button0)

        self.button1 = QPushButton("Pre-processing")
        self.button1.clicked.connect(lambda: self.show_suboptions(1))
        option_block_layout.addWidget(self.button1)
        
        self.button2 = QPushButton("Analysis options")
        self.button2.clicked.connect(lambda: self.show_suboptions(2))
        option_block_layout.addWidget(self.button2)

        self.button3 = QPushButton("Time/frequency domain")
        self.button3.clicked.connect(lambda: self.show_suboptions(3))
        option_block_layout.addWidget(self.button3)

        self.button4 = QPushButton("Nonlinear")
        self.button4.clicked.connect(lambda: self.show_suboptions(4))
        option_block_layout.addWidget(self.button4)

        # Add a stretch to push the buttons to the top
        option_block_layout.addStretch()
        # Add a QLabel for the note at the middle bottom
        note_label = QLabel("The changes made will change the default values,\nnot the selected options of the current analysis")
        option_block_layout.addWidget(note_label)

        # Create a vertical line separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setFrameShadow(QFrame.Sunken)

        # Create suboptions on the right
        self.suboptions_widget_total_layout = QVBoxLayout()
        self.suboptions_widget_total = QWidget()
        self.suboptions_widget_total.setLayout(self.suboptions_widget_total_layout)
        self.suboptions_widget = QStackedWidget()

        # 0) create user information
        self.user_suboptions = QVBoxLayout()
        self.user_suboptions_widget = QWidget()
        self.user_suboptions_widget.setLayout(self.user_suboptions)

        # sex
        sex_layout = QHBoxLayout()
        sex_widget = QWidget()
        sex_widget.setLayout(sex_layout)
        sex_label = QLabel("Sex: ")
        self.sex_level = QComboBox()
        self.sex_level.addItem("Female")
        self.sex_level.addItem("Male")
        self.sex_level.setCurrentIndex(self.settings['sex'])
        self.sex_level.wheelEvent = lambda event: None
        sex_layout.addWidget(sex_label)
        sex_layout.addWidget(self.sex_level)
        #self.user_suboptions.addWidget(sex_layout)

        # HR rest
        hr_rest_layout = QHBoxLayout()
        hr_rest_widget = QWidget()
        hr_rest_widget.setLayout(hr_rest_layout)
        self.hr_rest_label_left = QLabel("HR rest (bpm): ")
        self.hr_rest_space = QLineEdit()
        self.hr_rest_space.setText(str(self.settings['hr_rest']))
        hr_rest_layout.addWidget(self.hr_rest_label_left)
        hr_rest_layout.addWidget(self.hr_rest_space)
        hr_rest_layout.addWidget(hr_rest_widget)

        # HR max
        hr_max_layout = QHBoxLayout()
        hr_max_widget = QWidget()
        hr_max_widget.setLayout(hr_max_layout)
        self.hr_max_label_left = QLabel("HR max (bpm): ")
        self.hr_max_space = QLineEdit()
        self.hr_max_space.setText(str(self.settings['hr_max']))
        hr_max_layout.addWidget(self.hr_max_label_left)
        hr_max_layout.addWidget(self.hr_max_space)
        hr_max_layout.addWidget(hr_max_widget)
        
        # 1) create pre-processing suboptions
        self.preprocessing_suboptions = QVBoxLayout()
        self.preprocessing_suboptions_widget = QWidget()
        self.preprocessing_suboptions_widget.setLayout(self.preprocessing_suboptions)
    
        # NOISE DETECTION
        noise_detection_layout = QVBoxLayout()
        noise_detection_widget = QWidget()
        noise_detection_widget.setLayout(noise_detection_layout)
        # First row - Centered label
        noise_label1 = QLabel("<b>Noise detection</b>")
        noise_label1.setAlignment(QtCore.Qt.AlignCenter)
        noise_detection_layout.addWidget(noise_label1)
        # Second row - Level option
        noise_slider_layout = QHBoxLayout()
        noise_slider_widget = QWidget()
        noise_slider_widget.setLayout(noise_slider_layout)
        noise_label2_left = QLabel("Detection level: ")
        self.noise_level = QComboBox()
        self.noise_level.addItem("None")
        self.noise_level.addItem("Very low")
        self.noise_level.addItem("Low")
        self.noise_level.addItem("Medium")
        self.noise_level.addItem("High")
        self.noise_level.addItem("Custom")
        self.noise_level.wheelEvent = lambda event: None
        self.noise_level.setCurrentIndex(self.settings['noise_detection_level'])
        noise_slider_layout.addWidget(noise_label2_left)
        noise_slider_layout.addWidget(self.noise_level)
        noise_detection_layout.addWidget(noise_slider_widget)
        self.noise_level.currentTextChanged.connect(self.updateNoiseOptions)
        # Third row - Outlier level
        noise_outlier_layout = QHBoxLayout()
        noise_outlier_widget = QWidget()
        noise_outlier_widget.setLayout(noise_outlier_layout)
        self.noise_outlier_label2_left = QLabel("Outlier level: ")
        self.noise_outlier_level = QComboBox()
        self.noise_outlier_level.addItem("None")
        self.noise_outlier_level.addItem("Very low correction (threshold = 0.45 s)")
        self.noise_outlier_level.addItem("Low correction (threshold = 0.35 s)")
        self.noise_outlier_level.addItem("Medium correction (threshold = 0.25 s)")
        self.noise_outlier_level.addItem("High correction (threshold = 0.15 s)")
        self.noise_outlier_level.addItem("Very high correction (threshold = 0.05 s)")
        self.noise_outlier_level.addItem("Automatic correction")
        self.noise_outlier_level.wheelEvent = lambda event: None
        self.noise_outlier_level.setCurrentIndex(self.settings['noise_outlier_level'])
        noise_outlier_layout.addWidget(self.noise_outlier_label2_left)
        noise_outlier_layout.addWidget(self.noise_outlier_level)
        noise_outlier_layout.addWidget(noise_outlier_widget)
        if (self.noise_level.currentIndex() != 5):
            self.noise_outlier_label2_left.setEnabled(False)
            self.noise_outlier_level.setEnabled(False)
        noise_detection_layout.addWidget(noise_outlier_widget)
        # Fourth row - Between beats distance
        between_beats_layout = QHBoxLayout()
        between_beats_widget = QWidget()
        between_beats_widget.setLayout(between_beats_layout)
        self.between_beats_label2_left = QLabel("Between beats space: ")
        # Create a QLabel to display the icon
        self.between_beats_icon_label = QLabel()
        between_beats_icon_path = "config/icons/information.jpg"
        between_beats_icon_pixmap = QtGui.QPixmap(between_beats_icon_path)
        between_beats_icon_pixmap = between_beats_icon_pixmap.scaled(*(20,20))
        self.between_beats_icon_label.setPixmap(between_beats_icon_pixmap)
        between_beats_tooltip_text = "Two outliers will be considered in the same noise interval if they are this difference away from each other"
        self.between_beats_icon_label.setToolTip(between_beats_tooltip_text)
        self.between_beats_space = QLineEdit()
        self.between_beats_space.setText(str(self.settings['between_beats']))
        between_beats_layout.addWidget(self.between_beats_label2_left)
        between_beats_layout.addWidget(self.between_beats_icon_label)
        between_beats_layout.addWidget(self.between_beats_space)
        between_beats_layout.addWidget(between_beats_widget)
        if (self.noise_level.currentIndex() != 5):
            self.between_beats_label2_left.setEnabled(False)
            self.between_beats_icon_label.setEnabled(False)
            self.between_beats_space.setEnabled(False)
        noise_detection_layout.addWidget(between_beats_widget)
        # Fifth row - Minimum noise percentage
        minimum_noise_layout = QHBoxLayout()
        minimum_noise_widget = QWidget()
        minimum_noise_widget.setLayout(minimum_noise_layout)
        self.minimum_noise_label2_left = QLabel("Minimum noise (%): ")
        self.minimum_noise_space = QLineEdit()
        self.minimum_noise_space.setText(str(self.settings['minimum_noise']))
        minimum_noise_layout.addWidget(self.minimum_noise_label2_left)
        minimum_noise_layout.addWidget(self.minimum_noise_space)
        minimum_noise_layout.addWidget(minimum_noise_widget)
        if (self.noise_level.currentIndex() != 6):
            self.minimum_noise_label2_left.setEnabled(False)
            self.minimum_noise_space.setEnabled(False)
        noise_detection_layout.addWidget(minimum_noise_widget)
        # frame
        noise_detection_frame = QFrame()
        noise_detection_frame.setLayout(noise_detection_layout)
        noise_detection_frame.setFrameShape(QFrame.Box)
        noise_detection_frame.setLineWidth(2)
        noise_detection_frame.setStyleSheet("QFrame { border-color: black; }")
        self.preprocessing_suboptions.layout().addWidget(noise_detection_frame)

        # outlier with algorithm
        beat_algorithm_layout = QVBoxLayout()
        beat_algorithm_widget = QWidget()
        beat_algorithm_widget.setLayout(beat_algorithm_layout)
        # First row - Centered label
        beat_algorithm_label1 = QLabel("<b>Outlier correction with algorithm</b>")
        beat_algorithm_label1.setAlignment(QtCore.Qt.AlignCenter)
        beat_algorithm_layout.addWidget(beat_algorithm_label1)
        # Second row - Slider
        beat_algorithm_slider_layout = QHBoxLayout()
        beat_algorithm_slider_widget = QWidget()
        beat_algorithm_slider_widget.setLayout(beat_algorithm_slider_layout)
        self.beat_algorithm_button = QPushButton("Apply")
        self.beat_algorithm_button.setStyleSheet("background-color: blue; color: white;")
        self.algorithm_active = False
        if (self.settings["algorithm_option"]):
            self.changeAlgorithmOption()
        beat_algorithm_slider_layout.addWidget(self.beat_algorithm_button)
        self.beat_algorithm_button.clicked.connect(self.changeAlgorithmOption)
        beat_algorithm_layout.addWidget(beat_algorithm_slider_widget)
        # frame
        beat_algorithm_frame = QFrame()
        beat_algorithm_frame.setLayout(beat_algorithm_layout)
        beat_algorithm_frame.setFrameShape(QFrame.Box)
        beat_algorithm_frame.setLineWidth(2)
        beat_algorithm_frame.setStyleSheet("QFrame { border-color: black; }")
        self.preprocessing_suboptions.layout().addWidget(beat_algorithm_frame)

        # BEAT CORRECTION
        beat_correction_layout = QVBoxLayout()
        beat_correction_widget = QWidget()
        beat_correction_widget.setLayout(beat_correction_layout)
        # First row - Centered label
        beat_correction_label1 = QLabel("<b>Outlier correction with threshold</b>")
        beat_correction_label1.setAlignment(QtCore.Qt.AlignCenter)
        # Second row - Level option
        beat_correction_slider_layout = QHBoxLayout()
        beat_correction_slider_widget = QWidget()
        beat_correction_slider_widget.setLayout(beat_correction_slider_layout)
        beat_correction_label2_left = QLabel("Outlier threshold: ")
        self.beat_correction_level = QComboBox()
        self.beat_correction_level.addItem("None")
        self.beat_correction_level.addItem("Very low correction (threshold = 0.45 s)")
        self.beat_correction_level.addItem("Low correction (threshold = 0.35 s)")
        self.beat_correction_level.addItem("Medium correction (threshold = 0.25 s)")
        self.beat_correction_level.addItem("Strong correction (threshold = 0.15 s)")
        self.beat_correction_level.addItem("Very strong correction (threshold = 0.05 s)")
        self.beat_correction_level.wheelEvent = lambda event: None
        self.beat_correction_level.setCurrentIndex(self.settings['beat_correction_level'])
        beat_correction_slider_layout.addWidget(beat_correction_label2_left)
        beat_correction_slider_layout.addWidget(self.beat_correction_level)
        beat_correction_layout.addWidget(beat_correction_slider_widget)
        # frame
        beat_correction_frame = QFrame()
        beat_correction_frame.setLayout(beat_correction_layout)
        beat_correction_frame.setFrameShape(QFrame.Box)
        beat_correction_frame.setLineWidth(2)
        beat_correction_frame.setStyleSheet("QFrame { border-color: black; }")
        self.preprocessing_suboptions.layout().addWidget(beat_correction_frame)

        # DETRENDING OPTION
        detrending_layout = QVBoxLayout()
        detrending_widget = QWidget()
        detrending_widget.setLayout(detrending_layout)
        # First row - Centered label
        detrending_label1 = QLabel("<b>RR interval detrending</b>")
        detrending_label1.setAlignment(QtCore.Qt.AlignCenter)
        detrending_layout.addWidget(detrending_label1)
        # Second row - Level option
        detrending_slider_layout = QHBoxLayout()
        detrending_slider_widget = QWidget()
        detrending_slider_widget.setLayout(detrending_slider_layout)
        detrending_label2_left = QLabel("Detrending method: ")
        self.detrending_level = QComboBox()
        self.detrending_level.addItem("None")
        self.detrending_level.addItem("Smooth priors")
        self.detrending_level.addItem("1st Order")
        self.detrending_level.addItem("2nd Order")
        self.detrending_level.addItem("3rd Order")
        self.detrending_level.wheelEvent = lambda event: None
        self.detrending_level.setCurrentIndex(self.settings['detrending_method'])
        detrending_slider_layout.addWidget(detrending_label2_left)
        detrending_slider_layout.addWidget(self.detrending_level)
        detrending_layout.addWidget(detrending_slider_widget)
        # Third row - Smoothing parameter
        smoothing_parameter_layout = QHBoxLayout()
        smoothing_parameter_widget = QWidget()
        smoothing_parameter_widget.setLayout(smoothing_parameter_layout)
        self.smoothing_parameter_label2_left = QLabel("Smoothing parameter: ")
        self.smoothing_parameter_space = QLineEdit()
        self.smoothing_parameter_space.setText(str(self.settings['smoothing_parameter']))
        smoothing_parameter_layout.addWidget(self.smoothing_parameter_label2_left)
        smoothing_parameter_layout.addWidget(self.smoothing_parameter_space)
        smoothing_parameter_layout.addWidget(smoothing_parameter_widget)
        if (self.detrending_level.currentIndex() != 1):
            self.smoothing_parameter_label2_left.setEnabled(False)
            self.smoothing_parameter_space.setEnabled(False)
        self.detrending_level.currentTextChanged.connect(self.updateDetrendingLevel)
        detrending_layout.addWidget(smoothing_parameter_widget)
        # Fourth row - Cutoff frequency
        # unnecesary
        # frame
        detrending_frame = QFrame()
        detrending_frame.setLayout(detrending_layout)
        detrending_frame.setFrameShape(QFrame.Box)
        detrending_frame.setLineWidth(2)
        detrending_frame.setStyleSheet("QFrame { border-color: black; }")
        self.preprocessing_suboptions.layout().addWidget(detrending_frame)

        
        self.suboptions_widget.addWidget(self.preprocessing_suboptions_widget)


        # 2) create sample suboptions
        self.analysis_suboptions = QVBoxLayout()
        self.analysis_suboptions_widget = QWidget()
        self.analysis_suboptions_widget.setLayout(self.analysis_suboptions)
        # First row - Time domain
        number_samples_layout = QHBoxLayout()
        number_samples_widget = QWidget()
        number_samples_widget.setLayout(number_samples_layout)
        self.number_samples_label = QLabel("Number of samples")
        self.number_samples_space = QLineEdit("")
        self.number_samples_space.setText(str(self.settings['number_samples']))
        number_samples_layout.addWidget(self.number_samples_label)
        number_samples_layout.addWidget(self.number_samples_space)
        self.analysis_suboptions.addWidget(number_samples_widget)
        # Second row - Sample length
        sample_length_layout = QHBoxLayout()
        sample_length_widget = QWidget()
        sample_length_widget.setLayout(sample_length_layout)
        self.sample_length_label = QLabel("Sample length (s)")
        self.sample_length_space = QLineEdit("")
        self.sample_length_space.setText(str(self.settings['sample_length']))
        sample_length_layout.addWidget(self.sample_length_label)
        sample_length_layout.addWidget(self.sample_length_space)
        self.analysis_suboptions.addWidget(sample_length_widget)
        # First row - Minimum sample size
        minimum_sample_size_layout = QHBoxLayout()
        minimum_sample_size_widget = QWidget()
        minimum_sample_size_widget.setLayout(minimum_sample_size_layout)
        self.minimum_sample_size_label = QLabel("Minimum sample length (s)")
        self.minimum_sample_size_space = QLineEdit("")
        self.minimum_sample_size_space.setText(str(self.settings['minimum_sample_size']))
        minimum_sample_size_layout.addWidget(self.minimum_sample_size_label)
        minimum_sample_size_layout.addWidget(self.minimum_sample_size_space)
        self.analysis_suboptions.addWidget(minimum_sample_size_widget)
        self.checkbox = QCheckBox("Auto update results", self)
        self.checkbox.setChecked(self.settings['auto_update_results'])
        self.analysis_suboptions.addWidget(self.checkbox)
        self.analysis_suboptions.addStretch()

        self.suboptions_widget.addWidget(self.analysis_suboptions_widget)


        # 3) TIME FREQUENCY SUBOPTIONS
        self.time_frequency_layout = QVBoxLayout()
        self.time_frequency_widget = QWidget()
        self.time_frequency_widget.setLayout(self.time_frequency_layout)

        # TIME DOMAIN OPTIONS
        time_domain_layout = QVBoxLayout()
        time_domain_widget = QWidget()
        time_domain_widget.setLayout(time_domain_layout)
        # First row - label
        time_domain_label1 = QLabel("<b>Time-domain analysis options</b>")
        time_domain_label1.setAlignment(QtCore.Qt.AlignCenter)
        time_domain_layout.addWidget(time_domain_label1)
        # Second row - min max hr
        min_max_hr_layout = QHBoxLayout()
        min_max_hr_widget = QWidget()
        min_max_hr_widget.setLayout(min_max_hr_layout)
        self.min_max_hr_label1 = QLabel("Min/max HR as average of: ")
        self.min_max_hr_space = QLineEdit("")
        self.min_max_hr_space.setText(str(self.settings['average_hr']))
        self.min_max_hr_label2 = QLabel("beats")
        min_max_hr_layout.addWidget(self.min_max_hr_label1)
        min_max_hr_layout.addWidget(self.min_max_hr_space)
        min_max_hr_layout.addWidget(self.min_max_hr_label2)
        time_domain_layout.addWidget(min_max_hr_widget)
        # Third row - threshold for nnxx
        threshold_nnxx_layout = QHBoxLayout()
        threshold_nnxx_widget = QWidget()
        threshold_nnxx_widget.setLayout(threshold_nnxx_layout)
        self.threshold_nnxx_label1 = QLabel("Threshold for NNxx and pNNxx: ")
        self.threshold_nnxx_space = QLineEdit("")
        self.threshold_nnxx_space.setText(str(self.settings['nnxx_threshold']))
        self.threshold_nnxx_label2 = QLabel("ms")
        threshold_nnxx_layout.addWidget(self.threshold_nnxx_label1)
        threshold_nnxx_layout.addWidget(self.threshold_nnxx_space)
        threshold_nnxx_layout.addWidget(self.threshold_nnxx_label2)
        time_domain_layout.addWidget(threshold_nnxx_widget)
        # frame
        time_domain_frame = QFrame()
        time_domain_frame.setLayout(time_domain_layout)
        time_domain_frame.setFrameShape(QFrame.Box)
        time_domain_frame.setLineWidth(2)
        time_domain_frame.setStyleSheet("QFrame { border-color: black; }")
        self.time_frequency_layout.layout().addWidget(time_domain_frame)

        # HRV frequency bands
        hrv_bands_layout = QVBoxLayout()
        hrv_bands_widget = QWidget()
        hrv_bands_widget.setLayout(hrv_bands_layout)
        # First row - label
        hrv_bands_label1 = QLabel("<b>HRV frequency bands</b>")
        hrv_bands_label1.setAlignment(QtCore.Qt.AlignCenter)
        hrv_bands_layout.addWidget(hrv_bands_label1)
        # Second row - vlf
        vlf_layout = QHBoxLayout()
        vlf_widget = QWidget()
        vlf_widget.setLayout(vlf_layout)
        self.vlf_label1 = QLabel("Very low frequency (VLF): ")
        self.vlf_space1 = QLineEdit("")
        self.vlf_space1.setText(str(self.settings['vlf_min']))
        self.vlf_label2 = QLabel("-")
        self.vlf_space2 = QLineEdit("")
        self.vlf_space2.setText(str(self.settings['vlf_max']))
        self.vlf_label3 = QLabel("Hz")
        vlf_layout.addWidget(self.vlf_label1)
        vlf_layout.addWidget(self.vlf_space1)
        vlf_layout.addWidget(self.vlf_label2)
        vlf_layout.addWidget(self.vlf_space2)
        vlf_layout.addWidget(self.vlf_label3)
        hrv_bands_layout.addWidget(vlf_widget)
        # Third row - lf
        lf_layout = QHBoxLayout()
        lf_widget = QWidget()
        lf_widget.setLayout(lf_layout)
        self.lf_label1 = QLabel("Low frequency (LF): ")
        self.lf_space1 = QLineEdit("")
        self.lf_space1.setText(str(self.settings['lf_min']))
        self.lf_label2 = QLabel("-")
        self.lf_space2 = QLineEdit("")
        self.lf_space2.setText(str(self.settings['lf_max']))
        self.lf_label3 = QLabel("Hz")
        lf_layout.addWidget(self.lf_label1)
        lf_layout.addWidget(self.lf_space1)
        lf_layout.addWidget(self.lf_label2)
        lf_layout.addWidget(self.lf_space2)
        lf_layout.addWidget(self.lf_label3)
        hrv_bands_layout.addWidget(lf_widget)
        # Fourth row - hf
        hf_layout = QHBoxLayout()
        hf_widget = QWidget()
        hf_widget.setLayout(hf_layout)
        self.hf_label1 = QLabel("High frequency (HF): ")
        self.hf_space1 = QLineEdit("")
        self.hf_space1.setText(str(self.settings['hf_min']))
        self.hf_label2 = QLabel("-")
        self.hf_space2 = QLineEdit("")
        self.hf_space2.setText(str(self.settings['hf_max']))
        self.hf_label3 = QLabel("Hz")
        hf_layout.addWidget(self.hf_label1)
        hf_layout.addWidget(self.hf_space1)
        hf_layout.addWidget(self.hf_label2)
        hf_layout.addWidget(self.hf_space2)
        hf_layout.addWidget(self.hf_label3)
        hrv_bands_layout.addWidget(hf_widget)
        # frame
        hrv_bands_frame = QFrame()
        hrv_bands_frame.setLayout(hrv_bands_layout)
        hrv_bands_frame.setFrameShape(QFrame.Box)
        hrv_bands_frame.setLineWidth(2)
        hrv_bands_frame.setStyleSheet("QFrame { border-color: black; }")
        self.time_frequency_layout.layout().addWidget(hrv_bands_frame)

        # SPECTRUM ESTIMATION OPTIONS
        spectrum_estimation_layout = QVBoxLayout()
        spectrum_estimation_widget = QWidget()
        spectrum_estimation_widget.setLayout(spectrum_estimation_layout)
        # First row - label
        spectrum_estimation_label1 = QLabel("<b>Spectrum estimation options</b>")
        spectrum_estimation_label1.setAlignment(QtCore.Qt.AlignCenter)
        spectrum_estimation_layout.addWidget(spectrum_estimation_label1)
        # Second row - points
        spectrum_estimation_layout = QHBoxLayout()
        spectrum_estimation_widget = QWidget()
        spectrum_estimation_widget.setLayout(spectrum_estimation_layout)
        self.spectrum_estimation_label1 = QLabel("Number of points computed for the FFT: ")
        self.spectrum_estimation_space = QLineEdit("")
        self.spectrum_estimation_space.setText(str(self.settings['spectrum_points']))
        self.spectrum_estimation_label2 = QLabel("points")
        spectrum_estimation_layout.addWidget(self.spectrum_estimation_label1)
        spectrum_estimation_layout.addWidget(self.spectrum_estimation_space)
        spectrum_estimation_layout.addWidget(self.spectrum_estimation_label2)
        # frame
        spectrum_estimation_frame = QFrame()
        spectrum_estimation_frame.setLayout(spectrum_estimation_layout)
        spectrum_estimation_frame.setFrameShape(QFrame.Box)
        spectrum_estimation_frame.setLineWidth(2)
        spectrum_estimation_frame.setStyleSheet("QFrame { border-color: black; }")
        self.time_frequency_layout.layout().addWidget(spectrum_estimation_frame)

        # FFT SPECTRUM USING WELCH
        fft_welch_layout = QVBoxLayout()
        fft_welch_widget = QWidget()
        fft_welch_widget.setLayout(fft_welch_layout)
        # First row - label
        welch_fft_label1 = QLabel("<b>FFT spectrum using Welch's periodogram method</b>")
        welch_fft_label1.setAlignment(QtCore.Qt.AlignCenter)
        fft_welch_layout.addWidget(welch_fft_label1)
        # Second row - window width
        welch_width_layout = QHBoxLayout()
        welch_width_widget = QWidget()
        welch_width_widget.setLayout(welch_width_layout)
        self.welch_width_label1 = QLabel("Order of moving avrage filter: ")
        self.welch_width_space = QLineEdit("")
        self.welch_width_space.setText(str(self.settings['ma_order']))
        self.welch_width_label2 = QLabel("s")
        welch_width_layout.addWidget(self.welch_width_label1)
        welch_width_layout.addWidget(self.welch_width_space)
        welch_width_layout.addWidget(self.welch_width_label2)
        fft_welch_layout.addWidget(welch_width_widget)
        # Third row - window overlap
        # not used
        # Fourth row - checkbox
        self.checkbox_fft = QCheckBox("Use Lomb-Scargle periodogram instead of FFT", self)
        self.checkbox_fft.setChecked(self.settings['lomb_scargle'])
        fft_welch_layout.addWidget(self.checkbox_fft)
        # Fifth row - lomb smoothing
        # not used
        # frame
        fft_welch_frame = QFrame()
        fft_welch_frame.setLayout(fft_welch_layout)
        fft_welch_frame.setFrameShape(QFrame.Box)
        fft_welch_frame.setLineWidth(2)
        fft_welch_frame.setStyleSheet("QFrame { border-color: black; }")
        self.time_frequency_layout.layout().addWidget(fft_welch_frame)

        # AR spectrum
        ar_spectrum_layout = QVBoxLayout()
        ar_spectrum_widget = QWidget()
        ar_spectrum_widget.setLayout(ar_spectrum_layout)
        # First row - label
        ar_spectrum_label1 = QLabel("<b>AR spectrum</b>")
        ar_spectrum_label1.setAlignment(QtCore.Qt.AlignCenter)
        ar_spectrum_layout.addWidget(ar_spectrum_label1)
        # Second row - ar model order
        ar_order_layout = QHBoxLayout()
        ar_order_widget = QWidget()
        ar_order_widget.setLayout(ar_order_layout)
        self.ar_order_label1 = QLabel("AR model order: ")
        self.ar_order_space = QLineEdit("")
        self.ar_order_space.setText(str(self.settings['ar_order']))
        ar_order_layout.addWidget(self.ar_order_label1)
        ar_order_layout.addWidget(self.ar_order_space)
        ar_spectrum_layout.addWidget(ar_order_widget)
        # Third row - window overlap
        # not useful
        # frame
        ar_spectrum_frame = QFrame()
        ar_spectrum_frame.setLayout(ar_spectrum_layout)
        ar_spectrum_frame.setFrameShape(QFrame.Box)
        ar_spectrum_frame.setLineWidth(2)
        ar_spectrum_frame.setStyleSheet("QFrame { border-color: black; }")
        self.time_frequency_layout.layout().addWidget(ar_spectrum_frame)

        self.suboptions_widget.addWidget(self.time_frequency_widget)


        # 4) NONLINEAR
        self.nonlinear_layout = QVBoxLayout()
        self.nonlinear_widget = QWidget()
        self.nonlinear_widget.setLayout(self.nonlinear_layout)

        # DETRENDING
        detrending_nonlinear_layout = QVBoxLayout()
        detrending_nonlinear_widget = QWidget()
        detrending_nonlinear_widget.setLayout(detrending_nonlinear_layout)
        # First row - label
        nonlinear_detrending_label1 = QLabel("<b>Nonlinear analysis options</b>")
        nonlinear_detrending_label1.setAlignment(QtCore.Qt.AlignCenter)
        detrending_nonlinear_layout.addWidget(nonlinear_detrending_label1)
        # Second row - checkbox
        self.checkbox_nonlinear = QCheckBox("Apply detrending for nonlinear analysis", self)
        self.checkbox_nonlinear.setChecked(self.settings['nonlinear_detrending'])
        detrending_nonlinear_layout.addWidget(self.checkbox_nonlinear)
        # frame
        detrending_nonlinear_frame = QFrame()
        detrending_nonlinear_frame.setLayout(detrending_nonlinear_layout)
        detrending_nonlinear_frame.setFrameShape(QFrame.Box)
        detrending_nonlinear_frame.setLineWidth(2)
        detrending_nonlinear_frame.setStyleSheet("QFrame { border-color: black; }")
        self.nonlinear_layout.layout().addWidget(detrending_nonlinear_frame)
        
        # Approximate and sample entropy
        apsam_entropy_layout = QVBoxLayout()
        apsam_entropy_widget = QWidget()
        apsam_entropy_widget.setLayout(apsam_entropy_layout)
        # First row - label
        apsam_entropy_label1 = QLabel("<b>Approximate and sample entropy</b>")
        apsam_entropy_label1.setAlignment(QtCore.Qt.AlignCenter)
        apsam_entropy_layout.addWidget(apsam_entropy_label1)
        # Second row - vlf
        embedding_dimension_layout = QHBoxLayout()
        embedding_dimension_widget = QWidget()
        embedding_dimension_widget.setLayout(embedding_dimension_layout)
        self.embedding_dimension_label1 = QLabel("Embedding dimension: ")
        self.embedding_dimension_space1 = QLineEdit("")
        self.embedding_dimension_space1.setText(str(self.settings['embedding_dimension']))
        self.embedding_dimension_label2 = QLabel("beats")
        embedding_dimension_layout.addWidget(self.embedding_dimension_label1)
        embedding_dimension_layout.addWidget(self.embedding_dimension_space1)
        embedding_dimension_layout.addWidget(self.embedding_dimension_label2)
        apsam_entropy_layout.addWidget(embedding_dimension_widget)
        # Third row - tolerance
        tolerance_layout = QHBoxLayout()
        tolerance_widget = QWidget()
        tolerance_widget.setLayout(tolerance_layout)
        self.tolerance_label1 = QLabel("Tolerance: ")
        self.tolerance_space1 = QLineEdit("")
        self.tolerance_space1.setText(str(self.settings['tolerance']))
        self.tolerance_label2 = QLabel("x SD")
        tolerance_layout.addWidget(self.tolerance_label1)
        tolerance_layout.addWidget(self.tolerance_space1)
        tolerance_layout.addWidget(self.tolerance_label2)
        apsam_entropy_layout.addWidget(tolerance_widget)
        # frame
        apsam_entropy_frame = QFrame()
        apsam_entropy_frame.setLayout(apsam_entropy_layout)
        apsam_entropy_frame.setFrameShape(QFrame.Box)
        apsam_entropy_frame.setLineWidth(2)
        apsam_entropy_frame.setStyleSheet("QFrame { border-color: black; }")
        self.nonlinear_layout.layout().addWidget(apsam_entropy_frame)

        # DFA
        dfa_layout = QVBoxLayout()
        dfa_widget = QWidget()
        dfa_widget.setLayout(dfa_layout)
        # First row - label
        dfa_label1 = QLabel("<b>Detrended Fluctuation Analysis (DFA)</b>")
        dfa_label1.setAlignment(QtCore.Qt.AlignCenter)
        dfa_layout.addWidget(dfa_label1)
        # Second row - n1
        n1_layout = QHBoxLayout()
        n1_widget = QWidget()
        n1_widget.setLayout(n1_layout)
        self.n1_label1 = QLabel("Short-term fluctuations  (N1): ")
        self.n1_space1 = QLineEdit("")
        self.n1_space1.setText(str(self.settings['n1_min']))
        self.n1_label2 = QLabel("-")
        self.n1_space2 = QLineEdit("")
        self.n1_space2.setText(str(self.settings['n1_max']))
        self.n1_label3 = QLabel("beats")
        n1_layout.addWidget(self.n1_label1)
        n1_layout.addWidget(self.n1_space1)
        n1_layout.addWidget(self.n1_label2)
        n1_layout.addWidget(self.n1_space2)
        n1_layout.addWidget(self.n1_label3)
        dfa_layout.addWidget(n1_widget)
        # Third row - n2
        n2_layout = QHBoxLayout()
        n2_widget = QWidget()
        n2_widget.setLayout(n2_layout)
        self.n2_label1 = QLabel("Short-term fluctuations  (N2): ")
        self.n2_space1 = QLineEdit("")
        self.n2_space1.setText(str(self.settings['n2_min']))
        self.n2_label2 = QLabel("-")
        self.n2_space2 = QLineEdit("")
        self.n2_space2.setText(str(self.settings['n2_max']))
        self.n2_label3 = QLabel("beats")
        n2_layout.addWidget(self.n2_label1)
        n2_layout.addWidget(self.n2_space1)
        n2_layout.addWidget(self.n2_label2)
        n2_layout.addWidget(self.n2_space2)
        n2_layout.addWidget(self.n2_label3)
        dfa_layout.addWidget(n2_widget)
        # frame
        dfa_frame = QFrame()
        dfa_frame.setLayout(dfa_layout)
        dfa_frame.setFrameShape(QFrame.Box)
        dfa_frame.setLineWidth(2)
        dfa_frame.setStyleSheet("QFrame { border-color: black; }")
        self.nonlinear_layout.layout().addWidget(dfa_frame)

        self.suboptions_widget.addWidget(self.nonlinear_widget)

        # Populate the suboptions layout with the default values from the JSON file
        self.show_suboptions(0)

        import_button = QPushButton("Save changes")
        import_button.setStyleSheet("background-color: blue; color: white")
        import_button.setFixedHeight(20)
        import_button.clicked.connect(lambda: self.save_settings())

        self.suboptions_widget_total_layout.addWidget(self.suboptions_widget)
        self.suboptions_widget_total_layout.addWidget(import_button)

        layout.addLayout(option_block_layout)
        layout.addWidget(separator)
        layout.addWidget(self.suboptions_widget_total)

        self.setLayout(layout)


    def changeAlgorithmOption(self):
        if self.algorithm_active: # cancel
            self.beat_algorithm_button.setStyleSheet("background-color: blue; color: white;")
            self.algorithm_active = False
            self.beat_algorithm_button.setText("Apply")

        else: # activate
            self.beat_algorithm_button.setStyleSheet("background-color: red; color: white;")
            self.algorithm_active = True
            self.beat_algorithm_button.setText("Do not apply")

    def show_suboptions(self, option):
        for button in [self.button0, self.button1, self.button2, self.button3]:
            button.setStyleSheet("background-color: None")

        if (option == 0):
            self.button0.setStyleSheet("background-color: lightblue")
            selected_widget = self.preprocessing_suboptions_widget
        elif(option == 1):
            self.button1.setStyleSheet("background-color: lightblue")
            selected_widget = self.analysis_suboptions_widget
        elif(option == 2):
            self.button2.setStyleSheet("background-color: lightblue")
            selected_widget = self.time_frequency_widget
        elif(option == 3):
            self.button3.setStyleSheet("background-color: lightblue")
            selected_widget = self.nonlinear_widget

        self.suboptions_widget.setCurrentWidget(selected_widget)
        

    def updateNoiseOptions(self):
        new_option = self.noise_level.currentIndex()

        if (new_option == 5): #custom
            self.noise_outlier_label2_left.setEnabled(True)
            self.noise_outlier_level.setEnabled(True)
            self.between_beats_label2_left.setEnabled(True)
            self.between_beats_icon_label.setEnabled(True)
            self.between_beats_space.setEnabled(True)
            self.minimum_noise_label2_left.setEnabled(True)
            self.minimum_noise_space.setEnabled(True)
        
        else:
            self.noise_outlier_label2_left.setEnabled(False)
            self.noise_outlier_level.setEnabled(False)
            self.between_beats_label2_left.setEnabled(False)
            self.between_beats_icon_label.setEnabled(False)
            self.between_beats_space.setEnabled(False)
            self.minimum_noise_label2_left.setEnabled(False)
            self.minimum_noise_space.setEnabled(False)

            if (new_option == 1):
                self.noise_outlier_level.setCurrentIndex(1)
                self.between_beats_space.setText("15")
                self.minimum_noise_space.setText("0.4")
            elif (new_option == 2):
                self.noise_outlier_level.setCurrentIndex(2)
                self.between_beats_space.setText("25")
                self.minimum_noise_space.setText("0.35")
            if (new_option == 3):
                self.noise_outlier_level.setCurrentIndex(3)
                self.between_beats_space.setText("35")
                self.minimum_noise_space.setText("0.3")
            if (new_option == 4):
                self.noise_outlier_level.setCurrentIndex(4)
                self.between_beats_space.setText("45")
                self.minimum_noise_space.setText("0.25")
            if (new_option == 0):
                self.noise_outlier_level.setCurrentIndex(0)
                self.between_beats_space.setText("0")
                self.minimum_noise_space.setText("0")


    def updateDetrendingLevel(self):
        if (self.detrending_level.currentIndex() != 1):
            self.smoothing_parameter_label2_left.setEnabled(False)
            self.smoothing_parameter_space.setEnabled(False)
        else:
            self.smoothing_parameter_label2_left.setEnabled(True)
            self.smoothing_parameter_space.setEnabled(True)

    def save_settings(self):

        try: 
            # Update the JSON file with the changes made in the suboptions
            self.settings["sex"] = self.sex_level.currentIndex()
            self.settings["hr_rest"] = int(self.hr_rest_space.text())
            self.settings["hr_max"] = int(self.hr_max_space.text())
            self.settings["noise_detection_level"] = self.noise_level.currentIndex()
            self.settings["noise_outlier_level"] = self.noise_outlier_level.currentIndex()
            self.settings["between_beats"] = int(self.between_beats_space.text())
            self.settings["minimum_noise"] = float(self.minimum_noise_space.text())
            self.settings["beat_correction_level"] = self.beat_correction_level.currentIndex()
            self.settings["algorithm_option"] = self.algorithm_active
            self.settings["detrending_method"] = self.detrending_level.currentIndex()
            self.settings["smoothing_parameter"] = int(self.smoothing_parameter_space.text())
            self.settings["number_samples"] = int(self.number_samples_space.text())
            self.settings["sample_length"] = int(self.sample_length_space.text())
            self.settings["minimum_sample_size"] = int(self.minimum_sample_size_space.text())
            self.settings["auto_update_results"] = self.checkbox.isChecked()
            self.settings["average_hr"] = int(self.min_max_hr_space.text())
            self.settings["nnxx_threshold"] = int(self.threshold_nnxx_space.text())
            self.settings["vlf_min"] = float(self.vlf_space1.text())
            self.settings["vlf_max"] = float(self.vlf_space2.text())
            self.settings["lf_min"] = float(self.lf_space1.text())
            self.settings["lf_max"] = float(self.lf_space2.text())
            self.settings["hf_min"] = float(self.hf_space1.text())
            self.settings["hf_max"] = float(self.hf_space2.text())
            self.settings["spectrum_points"] = int(self.spectrum_estimation_space.text())
            self.settings["ma_order"] = int(self.welch_width_space.text())
            self.settings["lomb_scargle"] = self.checkbox_fft.isChecked()
            self.settings["ar_order"] = int(self.ar_order_space.text())
            self.settings["nonlinear_detrending"] = self.checkbox_nonlinear.isChecked()
            self.settings["embedding_dimension"] = int(self.embedding_dimension_space1.text())
            self.settings["tolerance"] = float(self.tolerance_space1.text())
            self.settings["n1_min"] = int(self.n1_space1.text())
            self.settings["n1_max"] = int(self.n1_space2.text())
            self.settings["n2_min"] = int(self.n2_space1.text())
            self.settings["n2_max"] = int(self.n2_space2.text())
            self.settings["embedding_dimension_recurrence"] = int(self.embedding_dimension_space1.text())

            # Write the updated dictionary back to the JSON file
         
            with open(resource_path(Path('settings.json')), 'w') as file:
                json.dump(self.settings, file, indent=4)  # Use indent to format the JSON file for readability
                self.close()

        except Exception as e:
            import traceback
            # Display an error message box
            QMessageBox.critical(None, "Could not save preferences", str(e), QMessageBox.Ok)
            error_traceback = traceback.format_exc()
            print(error_traceback)
        
