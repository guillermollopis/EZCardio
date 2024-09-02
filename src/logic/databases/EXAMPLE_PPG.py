"""
Copyright (c) 2020 Stichting imec Nederland (PALMS@imec.nl)
https://www.imec-int.com/en/imec-the-netherlands
@license GPL-3.0+ <http://spdx.org/licenses/GPL-3.0+>
See COPYING, README.
"""
import pathlib
from matplotlib import pyplot as plt
import pandas as pd
from qtpy.QtWidgets import QMessageBox
import numpy as np
from PyQt5.QtCore import qInfo
import scipy
from gui.tracking import Wave
from logic.databases.DatabaseHandler import Database
from utils.utils_general import get_project_root, butter_highpass_filter, butter_lowpass_filter, resource_path
from utils.utils_gui import Dialog
from utils.detect_peaks import detect_peaks


class EXAMPLE_PPG(Database):  # NB: !!!!!!!!!!!  class name should be equal to database name (this filename)
    def __init__(self):
        super().__init__()
        self.filetype = 'mat'  # NB: files to be used as source of the data
        self.DATAPATH = resource_path(pathlib.Path('docs', 'examples'))  # NB: top-level folder with the data
        self.file_template = r'**/*PPG*Subject_*' + r'.' + self.filetype or '**/*.' + self.filetype  # NB: source file filter, also in subfolders
        self.output_folder: pathlib.Path = self.DATAPATH  # NB: where to save files; it is overwritten in self.save() once file location is known
        self.existing_annotations_folder: pathlib.Path = self.output_folder  # NB: where to look for existing annotations
        self.main_track_label = 'ppg_filt'  # NB: signal to which all annotations will apply, should be one of the labels assigned in self.get_data()
        self.tracks_to_plot_initially = [self.main_track_label]  # NB: signals to be visible from the start of the app
        # NB: see !README_AnnotationConfig.xlsx: in this case we want to annotate 2 fiducial: peak and foot
        self.annotation_config_file = resource_path(pathlib.Path('config', 'AnnotationConfig', 'AnnotationConfig_EXAMPLE_PPG.csv'))
        # NB: see !README_EpochConfig.xlsx
        self.start_indexes = np.array([], dtype="int32")
        self.end_indexes = np.array([], dtype="int32")
        self.epoch_config_file = resource_path(pathlib.Path('config', 'EpochConfig', 'EpochConfig_default_start_with_None.csv'))
        self.RR_interval_as_HR = True  # NB: True: RR intervals in BPM, False: in seconds
        self.outputfile_prefix = ''  # NB: set here your initials, to distinguish multiple annotators' files
        assert 'csv' in self.annotation_config_file.suffix, 'Currently only .csv are supported as annotation configuration'

    def get_data(self, filename, ecg_data, frequency, time_data, start_indexes, end_indexes):
        # NB: here one needs to define the way data is fetched from the source
        #  In the end the annotated signal and all references have to be defined as Wave-instances

        # NB: 1. Run base class to initialize some variables:
        super().get_data(filename, ecg_data, frequency, time_data, start_indexes, end_indexes)

        self.start_indexes = start_indexes
        self.end_indexes = end_indexes

        # NB: 2. Fetch data from self.fullpath and create tracks: Dict[label:str,track:Wave]
        #  At this step signals from the source can be filtered (one also can have multiple versions of the same signal),
        #  resampled (for faster browsing when zoom-in/zoom-out), sync, etc.

        tracks = {}
        # NB: 2.1 Load data from a file
        #f = self._get_matfile_object(self.fullpath)
        # after referencing a mat file, one can get data from it as:
        # f['/data/ecg/signal'] if mat was saved as '-v7.3' (hdf5)
        # f['data'].ecg.signal if mat was saved as earlier version

        #ecg_data = np.concatenate(np.array(f['/data/ecg/signal']))  # NB: loaded data
        #Fs_ecg = int(np.array(f['/data/ecg/fs']))
        ppg_data = ecg_data
        Fs_ppg = frequency

        # NB: 2.2 Convert\preprocess data, create new representations
        ppg_filt_data = butter_lowpass_filter(ppg_data, 5, Fs_ppg, order=2)  # NB: created and filtered data

        #ecg_data = butter_highpass_filter(ecg_data, 0.05, Fs_ecg, order=2)  # NB: created and filtered data
        #ecg_data = butter_lowpass_filter(ecg_data, 30, Fs_ecg, order=2)

        # NB 3. Create tracks and save them to the DB
        # signals start at time=0
        #ecg = Wave(ecg_data, Fs_ecg, label='ecg', filename=self.fullpath.parts[-1][:-1])
        ppg = Wave(ppg_data, Fs_ppg, label='ppg', filename=self.fullpath.parts[-1][:-1])
        ppg_filt = Wave(ppg_filt_data, Fs_ppg, label='ppg_filt', filename=self.fullpath.parts[-1][:-1])

        #for s in [ecg, ppg, ppg_filt]:
        #for s in [ppg, ppg_filt]:
        #    tracks[s.label] = s
        tracks[ppg_filt.label] = ppg_filt

        self.tracks = tracks
        self.track_labels = list(tracks.keys())
        self.tracks_to_plot_initially = self.track_labels
        super().test_database_setup()  # NB: test to early catch some of the DB initialization errors
        return tracks

    def set_annotation_data(self, frequency):
        # NB: used to set initial guesses for annotations, otherwise, one has to start annotation from scratch
        #  one can use here simple findpeaks() type algos, or more signal-specific python algorithms
        #  also possible to run an algo beforehand (e.g. in Matlab), store the results and load them here

        # NB: OPTIONAL!!! Load existing annotation if an .h5 file with the same name found in self.existing_annotation_folder (be careful with self.outputfile_prefix)
        existing_annotation_file = pathlib.Path(self.existing_annotations_folder, self.fullpath.stem + '.h5')
        if self.annotation_exists(existing_annotation_file.stem):
            try:
                self.load(existing_annotation_file)
                qInfo('Loading annotations from {}'.format(existing_annotation_file))
            except Exception as e:
                Dialog().warningMessage('Loading annotations from {} failed\n'.format(existing_annotation_file) + str(e))
        else:
            loading_box = QMessageBox()
            loading_box.setWindowTitle("Loading")
            loading_box.setText("Detecting peaks...")
            loading_box.show()
            # # NB: 1. Find\fetch preliminary annotation data
            #fs = self.tracks[self.main_track_label].fs
            fs = frequency
            
            try:

                total_peaks = np.array([], dtype="int32")
                for start, end in zip(self.start_indexes, self.end_indexes):
                    # # NB: 1. Find\fetch preliminary annotation data
                    amp = self.tracks[self.main_track_label].value[start:end]
                    peak = self.detect_ppg_peaks(amp, fs)

                    total_peaks = np.append(total_peaks, peak)

                    # # NB: 2. Use inherited functions to assign annotations to the main signal
                    # #  all annotation labels should be also in the provided AnnotationConfig file
                    # #  User can use _set_annotation_from_time or _set_annotation_from_idx
                from gui import PALMS
                PALMS.get().original_annotations = total_peaks
                self._set_annotation_from_idx('rpeak', total_peaks)
                loading_box.close()
            except Exception as e:
                loading_box.close()
                Dialog().warningMessage('Failed to use beat detector\n'
                                        'Currently you do not have any initial annotations loaded, but\n'
                                        'You can fix the issue, or implement another way in set_annotation_data()')
                import traceback
                error_traceback = traceback.format_exc()
                print(error_traceback)

    def get_rr_data(self, filename, ecg_data, frequency, time_data, start_indexes, end_indexes):
        print("get rr")

    def set_rr_annotation_data(self, total_indices):
        self._set_annotation_from_idx('rpeak', total_indices)

    def load_annotation_data(self, total_indices):
        self._set_annotation_from_idx('rpeak', total_indices)

    def load_data(self, filename, ecg_data, frequency, time_data, start_indexes, end_indexes):
        print("load data")

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
                amp = self.tracks[self.main_track_label].value[start:end]
                new_values = self.detect_ppg_peaks(amp, fs)
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


    def detect_ppg_peaks(self, ppg_signal, fs):
        
        final_pulse_indices = self.ppg_findpeaks(ppg_signal, fs)["PPG_Peaks"]

        return final_pulse_indices

    def ppg_findpeaks(
        self, ppg_cleaned, sampling_rate=1000, method="elgendi", show=False, **kwargs
    ):
        method = method.lower()
        peaks = self._ppg_findpeaks_elgendi(ppg_cleaned, sampling_rate, show=show, **kwargs)

        # Prepare output.
        info = {"PPG_Peaks": peaks}

        return info
    
    def _ppg_findpeaks_elgendi(
        self,
        signal,
        sampling_rate=1000,
        peakwindow=0.111,
        beatwindow=0.667,
        beatoffset=0.02,
        mindelay=0.3,
        show=False,
    ):
        if show:
            _, (ax0, ax1) = plt.subplots(nrows=2, ncols=1, sharex=True)
            ax0.plot(signal, label="filtered")

        # Ignore the samples with negative amplitudes and square the samples with
        # values larger than zero.
        signal_abs = signal.copy()
        signal_abs[signal_abs < 0] = 0
        sqrd = signal_abs**2

        # Compute the thresholds for peak detection. Call with show=True in order
        # to visualize thresholds.
        ma_peak_kernel = int(np.rint(peakwindow * sampling_rate))
        ma_peak = self.signal_smooth(sqrd, kernel="boxcar", size=ma_peak_kernel)

        ma_beat_kernel = int(np.rint(beatwindow * sampling_rate))
        ma_beat = self.signal_smooth(sqrd, kernel="boxcar", size=ma_beat_kernel)

        thr1 = ma_beat + beatoffset * np.mean(sqrd)  # threshold 1

        if show:
            ax1.plot(sqrd, label="squared")
            ax1.plot(thr1, label="threshold")
            ax1.legend(loc="upper right")

        # Identify start and end of PPG waves.
        waves = ma_peak > thr1
        beg_waves = np.where(np.logical_and(np.logical_not(waves[0:-1]), waves[1:]))[0]
        end_waves = np.where(np.logical_and(waves[0:-1], np.logical_not(waves[1:])))[0]
        # Throw out wave-ends that precede first wave-start.
        end_waves = end_waves[end_waves > beg_waves[0]]

        # Identify systolic peaks within waves (ignore waves that are too short).
        num_waves = min(beg_waves.size, end_waves.size)
        min_len = int(
            np.rint(peakwindow * sampling_rate)
        )  # this is threshold 2 in the paper
        min_delay = int(np.rint(mindelay * sampling_rate))
        peaks = [0]

        for i in range(num_waves):
            beg = beg_waves[i]
            end = end_waves[i]
            len_wave = end - beg

            if len_wave < min_len:
                continue

            # Visualize wave span.
            if show:
                ax1.axvspan(beg, end, facecolor="m", alpha=0.5)

            # Find local maxima and their prominence within wave span.
            data = signal[beg:end]
            locmax, props = scipy.signal.find_peaks(data, prominence=(None, None))

            if locmax.size > 0:
                # Identify most prominent local maximum.
                peak = beg + locmax[np.argmax(props["prominences"])]
                # Enforce minimum delay between peaks.
                if peak - peaks[-1] > min_delay:
                    peaks.append(peak)

        peaks.pop(0)

        if show:
            ax0.scatter(peaks, signal_abs[peaks], c="r")
            ax0.legend(loc="upper right")
            ax0.set_title("PPG Peaks (Method by Elgendi et al., 2013)")

        peaks = np.asarray(peaks).astype(int)
        return peaks
    
    def signal_smooth(self, signal, method="convolution", kernel="boxzen", size=10, alpha=0.1):
        if isinstance(signal, pd.Series):
            signal = signal.values

        if isinstance(kernel, str) is False:
            raise TypeError("NeuroKit error: signal_smooth(): 'kernel' should be a string.")

   
        # hybrid method
        # 1st pass - boxcar kernel
        x = scipy.ndimage.uniform_filter1d(signal, size, mode="nearest")

        # 2nd pass - parzen kernel
        smoothed = self._signal_smoothing(x, kernel="parzen", size=size)

        return smoothed
    
    def _signal_smoothing(self, signal, kernel, size=5):

        # Get window.
        window = scipy.signal.get_window(kernel, size)
        w = window / window.sum()

        # Extend signal edges to avoid boundary effects.
        x = np.concatenate((signal[0] * np.ones(size), signal, signal[-1] * np.ones(size)))

        # Compute moving average.
        smoothed = np.convolve(w, x, mode="same")
        smoothed = smoothed[size:-size]
        return smoothed