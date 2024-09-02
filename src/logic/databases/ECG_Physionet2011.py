"""
Copyright (c) 2020 Stichting imec Nederland (PALMS@imec.nl)
https://www.imec-int.com/en/imec-the-netherlands
@license GPL-3.0+ <http://spdx.org/licenses/GPL-3.0+>
See COPYING, README.
"""
import os
import pathlib

from PyQt5.QtCore import qInfo
from qtpy.QtWidgets import QMessageBox

from gui.tracking import Wave
from logic.databases.DatabaseHandler import Database
from utils.utils_general import get_project_root, butter_highpass_filter, butter_lowpass_filter, resource_path
from utils.utils_gui import Dialog
import numpy as np
from __main__ import PanTompkinsQRSDetector
from utils import PanTompkinsImproved
#from utils import PanTompkinsImproved

from scipy.interpolate import interp1d


#NB: for this example to work one needs to put some of the PhysioNet/CinC Challenge 2011 .txt data files into docs\examples\example_Physionet2011
# https://archive.physionet.org/physiobank/database/challenge/2011/

class ECG_Physionet2011(Database):  # NB: !!!!!!!!!!!  class name should be equal to database name (this filename)
    def __init__(self):
        super().__init__()
        self.filetype = 'txt'  # NB: files to be used as source of the data
        self.DATAPATH = resource_path(pathlib.Path('docs' +os.sep+ 'examples' + os.sep+ 'example_Physionet2011'))  # NB: top-level folder with the data
        self.file_template = os.sep + r'.' + self.filetype or os.sep + self.filetype  # NB: source file filter, also in subfolders
        self.output_folder: pathlib.Path = self.DATAPATH  # NB: where to save files; it is overwritten in self.save() once file location is known
        self.existing_annotations_folder: pathlib.Path = self.output_folder  # NB: where to look for existing annotations
        self.main_track_label = 'ecg_filt'   # NB: signal to which all annotations will apply, should be one of the labels assigned in self.get_data()
        self.tracks_to_plot_initially = [self.main_track_label]  # NB: signals to be visible from the start of the app
        # NB: see !README_AnnotationConfig.xlsx: in this case we want to annotate 2 fiducial: peak and foot
        self.annotation_config_file = resource_path(pathlib.Path('config', 'AnnotationConfig', 'AnnotationConfig_ECG.csv'))
        self.epoch_config_file = resource_path(pathlib.Path('config', 'EpochConfig', 'EpochConfig_ECG_Physionet2011.csv'))
        self.RR_interval_as_HR = True  # NB: True: RR intervals in BPM, False: in seconds
        self.outputfile_prefix = ''  # NB: set here your initials, to distinguish multiple annotators' files
        self.start_indexes = np.array([], dtype="int32")
        self.end_indexes = np.array([], dtype="int32")
        assert 'csv' in self.annotation_config_file.suffix, 'Currently only .csv are supported as annotation configuration'

    def get_data(self, filename, ecg_data, frequency, time_data, start_indexes, end_indexes):
        # NB: here one needs to define the way data is fetched from the source
        #  In the end the annotated signal and all references have to be defined as Wave-instances

        # NB: 1. Run base class to initialize some variables:
        super().get_data(filename, ecg_data, frequency, time_data, start_indexes, end_indexes)
        # self.output_folder = self.fullpath.parent  # to save in the same location
        # self.output_folder = get_project_root()  # to save in project root/near the executable
        self.output_folder = self.fullpath.parent
        self.existing_annotations_folder = self.output_folder
        
        self.start_indexes = start_indexes
        self.end_indexes = end_indexes

        # NB: 2. Fetch data from self.fullpath and create tracks: Dict[label:str,track:Wave]
        #  At this step signals from the source can be filtered (one also can have multiple versions of the same signal),
        #  resampled (for faster browsing when zoom-in/zoom-out), sync, etc.

        tracks = {}
        # NB: 2.1 Load data from a file
        #txt_data = pd.read_csv(self.fullpath.as_posix(), header=None)
        #txt_data = pd.read_csv(self.fullpath.as_posix(), sep=";", engine="python")
        #ecg = txt_data.iloc[:, 3].values
        Fs_ecg = frequency # or time data

        #ecg_data = ecg
        # NB: 2.2 Convert\preprocess data, create new representations
        ecg_total, desired_time = self.interpolate_signal(ecg_data, round(frequency))

        self.ecg_raw = ecg_total

        for start, end in zip(start_indexes,end_indexes):

            ecg_data_filt = butter_highpass_filter(ecg_total[start:end], 1, int(Fs_ecg), order=5)  # NB: created and filtered data
            ecg_data_filt = butter_lowpass_filter(ecg_data_filt, 48, int(Fs_ecg), order=5)

            ecg_total[start:end] = ecg_data_filt

        
        #if _ecg_inverted(ecg_total[int(len(ecg_total)/4):int(len(ecg_total)/2+len(ecg_total)/10)], sampling_rate=Fs_ecg):
        #   ecg_total = -ecg_total
        
        # NB 3. Create tracks and save them to the DB
        # signals start at time=0
        #ecg = Wave(ecg_data, Fs_ecg, label='ecg', filename=self.fullpath.parts[-1][:-1])
        
        ecg_filt = Wave(ecg_total, round(Fs_ecg), desired_time, label='ecg_filt', filename=self.fullpath.parts[-1][:-1])
        
        #for s in [ecg_filt, ecg]:
        #    tracks[s.label] = s
        tracks[ecg_filt.label] = ecg_filt
        
        self.tracks = tracks
        self.track_labels = list(tracks.keys())
        self.tracks_to_plot_initially = self.track_labels
        
        super().test_database_setup()  # NB: test to early catch some of the DB initialization errors
        
        return tracks
    

    def get_rr_data(self, filename, ecg_data, frequency, time_data, start_indexes, end_indexes):
        # NB: here one needs to define the way data is fetched from the source
        #  In the end the annotated signal and all references have to be defined as Wave-instances

        # NB: 1. Run base class to initialize some variables:
        super().get_rr_data(filename, ecg_data, frequency, time_data, start_indexes, end_indexes)
        # self.output_folder = self.fullpath.parent  # to save in the same location
        # self.output_folder = get_project_root()  # to save in project root/near the executable
        self.output_folder = self.fullpath.parent
        self.existing_annotations_folder = self.output_folder
        
        self.start_indexes = start_indexes
        self.end_indexes = end_indexes

        # NB: 2. Fetch data from self.fullpath and create tracks: Dict[label:str,track:Wave]
        #  At this step signals from the source can be filtered (one also can have multiple versions of the same signal),
        #  resampled (for faster browsing when zoom-in/zoom-out), sync, etc.

        tracks = {}
        # NB: 2.1 Load data from a file
        #txt_data = pd.read_csv(self.fullpath.as_posix(), header=None)
        #txt_data = pd.read_csv(self.fullpath.as_posix(), sep=";", engine="python")
        #ecg = txt_data.iloc[:, 3].values
        Fs_ecg = frequency # or time data

        #ecg_data = ecg
        # NB: 2.2 Convert\preprocess data, create new representationss
        rr_total = ecg_data
        desired_time = time_data
        
        # NB 3. Create tracks and save them to the DB
        # signals start at time=0
        #ecg = Wave(ecg_data, Fs_ecg, label='ecg', filename=self.fullpath.parts[-1][:-1])ecg
        
        ecg_filt = Wave(rr_total, round(Fs_ecg), desired_time, label='RR', filename=self.fullpath.parts[-1][:-1])
        
        #for s in [ecg_filt, ecg]:
        #    tracks[s.label] = s
        tracks[ecg_filt.label] = ecg_filt
        
        self.main_track_label = 'RR'
        self.tracks = tracks
        self.track_labels = list(tracks.keys())
        self.tracks_to_plot_initially = self.track_labels
        
        super().test_database_setup()  # NB: test to early catch some of the DB initialization errors
        
        return tracks
    

    def load_data(self, filename, ecg_data, frequency, time_data, start_indexes, end_indexes):
        # NB: here one needs to define the way data is fetched from the source
        #  In the end the annotated signal and all references have to be defined as Wave-instances

        # NB: 1. Run base class to initialize some variables:
        super().load_data(filename, ecg_data, frequency, time_data, start_indexes, end_indexes)
        # self.output_folder = self.fullpath.parent  # to save in the same location
        # self.output_folder = get_project_root()  # to save in project root/near the executable
        self.output_folder = self.fullpath.parent
        self.existing_annotations_folder = self.output_folder
        
        self.start_indexes = start_indexes
        self.end_indexes = end_indexes

        # NB: 2. Fetch data from self.fullpath and create tracks: Dict[label:str,track:Wave]
        #  At this step signals from the source can be filtered (one also can have multiple versions of the same signal),
        #  resampled (for faster browsing when zoom-in/zoom-out), sync, etc.

        tracks = {}
        # NB: 2.1 Load data from a file
        #txt_data = pd.read_csv(self.fullpath.as_posix(), header=None)
        #txt_data = pd.read_csv(self.fullpath.as_posix(), sep=";", engine="python")
        #ecg = txt_data.iloc[:, 3].values
        Fs_ecg = frequency # or time data

        #ecg_data = ecg
        # NB: 2.2 Convert\preprocess data, create new representations
        from gui import PALMS
        desired_time = np.linspace(0, stop=(len(ecg_data) - 1) / Fs_ecg, num=len(ecg_data))
        ecg_total = ecg_data
        
        # NB 3. Create tracks and save them to the DB
        # signals start at time=0
        #ecg = Wave(ecg_data, Fs_ecg, label='ecg', filename=self.fullpath.parts[-1][:-1])
        
        ecg_filt = Wave(ecg_total, round(Fs_ecg), desired_time, label='ecg_filt', filename=self.fullpath.parts[-1][:-1])
        
        #for s in [ecg_filt, ecg]:
        #    tracks[s.label] = s
        tracks[ecg_filt.label] = ecg_filt
        
        self.tracks = tracks
        self.track_labels = list(tracks.keys())
        self.tracks_to_plot_initially = self.track_labels
        
        super().test_database_setup()  # NB: test to early catch some of the DB initialization errors
        
        return tracks
    

    def interpolate_signal(self, ecg_data, fs):
        # Determine the desired time points for interpolation
        desired_time = np.linspace(0, stop=(len(ecg_data) - 1) / fs, num=len(ecg_data))

        # Create an interpolation function
        interpolated_signal = interp1d(desired_time, ecg_data, kind="linear")

        # Interpolate the signal at the desired time points
        interpolated_values = interpolated_signal(desired_time)
        return interpolated_values, desired_time


    def set_annotation_data(self, frequency):
        print(frequency)
        # NB: used to set initial guesses for annotations, otherwise, one has to start annotation from scratch
        #  one can use here simple findpeaks() type algos, or more signal-specific python algorigthms
        #  also possible to run an algo beforehand (e.g. in Matlab), store the results and load them here

        # NB: OPTIONAL!!! Load existing annotation if an .h5 file with the same name found in self.existing_annotation_folder (be careful with self.outputfile_prefix)
        existing_annotation_file = pathlib.Path(self.existing_annotations_folder, self.fullpath.stem + '.h5')
        existing_annotation_file_with_prefix = pathlib.Path(self.existing_annotations_folder, self.outputfile_prefix + self.fullpath.stem + '.h5')

        existing_annotation_files = self.get_annotation_file(self.fullpath.stem)
        if existing_annotation_files is not None:
            latest_file_idx = np.argmax([os.path.getmtime(f) for f in existing_annotation_files])
            try:
                self.load(existing_annotation_files[latest_file_idx])
                qInfo('Loading annotations from {}'.format(existing_annotation_file_with_prefix))
            except Exception as e:
                Dialog().warningMessage('Loading annotations from {} failed\n'.format(existing_annotation_file_with_prefix) + str(e))
        else:
            loading_box = QMessageBox()
            loading_box.setWindowTitle("Loading")
            loading_box.setText("Detecting peaks...")
            loading_box.show()
            # # NB: 1. Find\fetch preliminary annotation data
            ecg = self.tracks[self.main_track_label].value
            #fs = self.tracks[self.main_track_label].fs
            fs = frequency
            
            try:

                total_indices = np.array([], dtype="int32")
                for start, end in zip(self.start_indexes, self.end_indexes):

                    # use any beat detection algorithm here, new_values is indexes of beats
                    #nyq = 0.5 * fs  # Nyquist Frequency
                    #low = 5 / nyq
                    #high = 18 / nyq
                    #from scipy import signal
                    #b, a = signal.butter(5, [low, high], btype='band')
                    #ecg_data_filt = signal.lfilter(b, a, self.ecg_raw[start:end])
                    ecg_data_filt = butter_highpass_filter(self.ecg_raw[start:end], 5, fs, order=5)  # NB: created and filtered data
                    ecg_data_filt = butter_lowpass_filter(ecg_data_filt, 18, fs, order=5)
                    qrs_detector = PanTompkinsQRSDetector(self.tracks[self.main_track_label].value, ecg_data_filt, fs, verbose=True, log_data=False, plot_data=False, show_plot=False)
                    new_values = np.array(start+qrs_detector.qrs_peaks_indices)
                    #from ecgdetectors import Detectors
                    #detectors = Detectors(fs)
                    #new_values = detectors.pan_tompkins_detector(self.ecg_raw[start:end])
                    #timestamp = np.arange(start, end)
                    #filtered_ecg_measurements, smooth_signal, integrated_signal = PanTompkinsImproved.Pan_Tompkins_QRS().solve(ecg[start:end], fs, timestamp)
                    #new_values = PanTompkinsImproved.detect_peaks(ecg[start:end], fs, filtered_ecg_measurements, integrated_signal)
                    
                    total_indices = np.append(total_indices, new_values)
                
                #total_indices = np.concatenate(total_indices)
                
                # # NB: 2. Use inherited functions to assign annotations to the main signal
                # #  all annotation labels should be also in the provided AnnotationConfig file
                # #  User can use _set_annotation_from_time or _set_annotation_from_idx
                from gui import PALMS
                import copy
                PALMS.get().original_annotations = total_indices
                self._set_annotation_from_idx('rpeak', total_indices)
                loading_box.close()
            except Exception as e:
                loading_box.close()
                Dialog().warningMessage('Failed to use beat detector\n'
                                        'Currently you do not have any initial annotations loaded, but\n'
                                        'You can fix the issue, or implement another way in set_annotation_data()')
                import traceback
                error_traceback = traceback.format_exc()
                print(error_traceback)


    def set_rr_annotation_data(self, total_indices):
        self._set_annotation_from_idx('rpeak', total_indices)

    def load_annotation_data(self, total_indices):
        self._set_annotation_from_idx('rpeak', total_indices)
        

    def redetect_peaks(self):

        loading_box = QMessageBox()
        loading_box.setWindowTitle("Loading")
        loading_box.setText("Detecting peaks...")
        loading_box.show()
        # # NB: 1. Find\fetch preliminary annotation data
        ecg = self.tracks[self.main_track_label].value
        #fs = self.tracks[self.main_track_label].fs

        from gui import PALMS
        fs = PALMS.get().FREQUENCY
        start_indexes = PALMS.get().START_INDEXES
        end_indexes = PALMS.get().END_INDEXES
            
        try:

            total_indices = np.array([], dtype="int32")
            for start, end in zip(start_indexes, end_indexes):

                # use any beat detection algorithm here, new_values is indexes of beats
                #nyq = 0.5 * fs  # Nyquist Frequency
                #low = 5 / nyq
                #high = 18 / nyq
                #from scipy import signal
                #b, a = signal.butter(5, [low, high], btype='band')
                #ecg_data_filt = signal.lfilter(b, a, self.ecg_raw[start:end])
                ecg_data_filt = butter_highpass_filter(self.ecg_raw[start:end], 5, fs, order=5)  # NB: created and filtered data
                ecg_data_filt = butter_lowpass_filter(ecg_data_filt, 18, fs, order=5)
                qrs_detector = PanTompkinsQRSDetector(self.tracks[self.main_track_label].value, ecg_data_filt, fs, verbose=True, log_data=False, plot_data=False, show_plot=False)
                new_values = np.array(start+qrs_detector.qrs_peaks_indices)
                #from ecgdetectors import Detectors
                #detectors = Detectors(fs)
                #new_values = detectors.pan_tompkins_detector(self.ecg_raw[start:end])
                #timestamp = np.arange(start, end)
                #filtered_ecg_measurements, smooth_signal, integrated_signal = PanTompkinsImproved.Pan_Tompkins_QRS().solve(ecg[start:end], fs, timestamp)
                #new_values = PanTompkinsImproved.detect_peaks(ecg[start:end], fs, filtered_ecg_measurements, integrated_signal)
                
                total_indices = np.append(total_indices, new_values)
                
            #total_indices = np.concatenate(total_indices)
                
            # # NB: 2. Use inherited functions to assign annotations to the main signal
            # #  all annotation labels should be also in the provided AnnotationConfig file
            # #  User can use _set_annotation_from_time or _set_annotation_from_idx
            from gui import PALMS
            PALMS.get().original_annotations = total_indices
            self._set_annotation_from_idx('rpeak', total_indices)
            loading_box.close()
        except Exception as e:
            loading_box.close()
            Dialog().warningMessage('Failed to use beat detector\n'
                                    'Currently you do not have any initial annotations loaded, but\n'
                                    'You can fix the issue, or implement another way in set_annotation_data()')
            import traceback
            error_traceback = traceback.format_exc()
            print(error_traceback)


    def invert_signal(self):
        from gui import PALMS
        self.ecg_raw = -self.ecg_raw
        PALMS.get().ECG_DATA = self.ecg_raw
        self.tracks[self.main_track_label].value = self.ecg_raw
        self.tracks[self.main_track_label].viewvalue = self.ecg_raw
        self.redetect_peaks()


    def save(self, **kwargs):
        # NB: save annotation data. By default annotations and partitions are saved as .h5 file.
        #  All tracks can be saved too (see Settings in the menu bar).
        #  One can also define custom save protocol here
        # self.output_folder = self.fullpath.parent  # to save in the same location
        # self.output_folder = get_project_root()  # to save in project root/near the executable
        try:
            self.output_folder = self.fullpath.parent
            super().save(filename=self.fullpath.stem, **kwargs)
        except Exception as e:
            Dialog().warningMessage('Save crashed with: \n' + str(e))

    def load(self, filename):
        # NB: load previously saved annotations and partitions.
        #  Inherited method loads data from .h5 files, but one can define custom protocol here
        super().load(filename)

def _ecg_inverted(ecg_signal, sampling_rate=1000, window_time=2.0):
    """Checks whether an ECG signal is inverted."""

    ecg_cleaned = ecg_clean(ecg_signal, sampling_rate=sampling_rate)

    ecg_cleaned_meanzero = ecg_signal - np.nanmean(ecg_cleaned)
    # take the median of the original value of the maximum of the squared signal
    # over a window where we would expect at least one heartbeat
    med_max_squared = np.nanmedian(
        _roll_orig_max_squared(ecg_cleaned_meanzero, window=int(window_time * sampling_rate))
    )
    # if median is negative, assume inverted
    return med_max_squared < 0


def _roll_orig_max_squared(x, window=2000):
    """With a rolling window, takes the original value corresponding to the maximum of the squared signal."""
    x_rolled = np.lib.stride_tricks.sliding_window_view(x, window, axis=0)
    # https://stackoverflow.com/questions/61703879/in-numpy-how-to-select-elements-based-on-the-maximum-of-their-absolute-values
    shape = np.array(x_rolled.shape)
    shape[-1] = -1
    return np.take_along_axis(x_rolled, np.square(x_rolled).argmax(-1).reshape(shape), axis=-1)

    
def ecg_clean(ecg_signal, sampling_rate=1000, method="neurokit", **kwargs):

    clean = _ecg_clean_nk(ecg_signal, sampling_rate, **kwargs)

    return clean

def _ecg_clean_nk(ecg_signal, sampling_rate=1000, **kwargs):
    # Remove slow drift and dc offset with highpass Butterworth.
    clean = signal_filter(
        signal=ecg_signal,
        sampling_rate=sampling_rate,
        lowcut=1,
        highcut=40,
        method="butterworth",
        order=5,
    )

    return clean

def signal_filter(
    signal,
    sampling_rate=1000,
    lowcut=None,
    highcut=None,
    method="butterworth",
    order=2,
    window_size="default",
    powerline=50,
    show=False,
):


    filtered = _signal_filter_butterworth(signal, sampling_rate, lowcut, highcut, order)



    return filtered

def _signal_filter_butterworth(signal, sampling_rate=1000, lowcut=None, highcut=None, order=5):
    import scipy
    """Filter a signal using IIR Butterworth SOS method."""
    freqs, filter_type = _signal_filter_sanitize(lowcut=lowcut, highcut=highcut, sampling_rate=sampling_rate)
    sos = scipy.signal.butter(order, freqs, btype=filter_type, output="sos", fs=sampling_rate)
    filtered = scipy.signal.sosfiltfilt(sos, signal)
    return filtered


def _signal_filter_sanitize(lowcut=None, highcut=None, sampling_rate=1000, normalize=False):

    # Sanity checks
    #freqs = sampling_rate
    #filter_type = "bandpass"
    
    # Replace 0 by none
    if lowcut is not None and lowcut == 0:
        lowcut = None
    if highcut is not None and highcut == 0:
        highcut = None

    # Format
    if lowcut is not None and highcut is not None:
        if lowcut > highcut:
            filter_type = "bandstop"
        else:
            filter_type = "bandpass"
        # pass frequencies in order of lowest to highest to the scipy filter
        freqs = list(np.sort([lowcut, highcut]))
    elif lowcut is not None:
        freqs = [lowcut]
        filter_type = "highpass"
    elif highcut is not None:
        freqs = [highcut]
        filter_type = "lowpass"

    # Normalize frequency to Nyquist Frequency (Fs/2).
    # However, no need to normalize if `fs` argument is provided to the scipy filter
    if normalize is True:
        freqs = np.array(freqs) / (sampling_rate / 2)

    return freqs, filter_type
