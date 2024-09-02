"""
Copyright (c) 2020 Stichting imec Nederland (PALMS@imec.nl)
https://www.imec-int.com/en/imec-the-netherlands
@license GPL-3.0+ <http://spdx.org/licenses/GPL-3.0+>
See COPYING, README.
"""
import pathlib
from qtpy.QtWidgets import QMessageBox
from PyQt5.QtCore import qInfo
from gui.tracking import Wave
from logic.databases.DatabaseHandler import Database
from utils.detect_peaks import detect_peaks
from utils.utils_general import get_project_root, butter_highpass_filter, butter_lowpass_filter, resource_path
import numpy as np

from utils.utils_gui import Dialog


class EXAMPLE_RESPIRATION(Database):
    def __init__(self):
        super().__init__()
        self.filetype = 'mat'
        self.DATAPATH = resource_path(pathlib.Path('docs', 'examples'))  # NB: top-level folder with the data
        self.file_template = r'**/*RESPIRATION*Subject_*' + r'.' + self.filetype or '**/*.' + self.filetype  # NB: source file filter, also in subfolders
        self.output_folder: pathlib.Path = self.DATAPATH  # NB: where to save file; it is overwritten in self.save() once file location is knowns
        self.existing_annotations_folder: pathlib.Path = self.output_folder  # NB: where to look for existing annotations
        self.main_track_label = 'resp'   # NB: signal to which all annotations will apply, should be one of the labels assigned in self.get_data()
        self.tracks_to_plot_initially = [self.main_track_label]  # NB: signals to be visible from the start of the app
        # NB: see !README_AnnotationConfig.xlsx: in this case we want to annotate 4 fiducial: peak, valley, upstroke and downstroke
        self.annotation_config_file = resource_path(pathlib.Path('config', 'AnnotationConfig', 'AnnotationConfig_EXAMPLE_RESPIRATION.csv'))
        # NB: see !README_EpochConfig.xlsx
        self.start_indexes = np.array([], dtype="int32")
        self.end_indexes = np.array([], dtype="int32")
        self.epoch_config_file = resource_path(pathlib.Path('config', 'EpochConfig', 'EpochConfig_default_start_with_good.csv'))
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
        # NB: 2.1 Load data from a mat-file
        #f = self._get_matfile_object(self.fullpath)

        #ecg_data = np.concatenate(np.array(f['/data/ekg/v']))
        #Fs_ecg = frequency
        #ppg_data = np.concatenate(np.array(f['/data/ppg/v']))
        #Fs_ppg = frequency
        resp_data = ecg_data
        resp_total = ecg_data
        Fs_resp = frequency
        # NB: 2.2 Convert\preprocess data, create new representation
        for start, end in zip(start_indexes,end_indexes):
            resp_data = butter_lowpass_filter(resp_data, 3, Fs_resp, order=2)  # NB: created and filtered data

            resp_total[start:end] = resp_data

        # NB 3. Create tracks and save them to the DB
        # signals start at time=0
        #ecg = Wave(ecg_data, Fs_ecg, label='ecg', filename=self.fullpath.parts[-1][:-1])
        #ppg = Wave(ppg_data, Fs_ppg, label='ppg', filename=self.fullpath.parts[-1][:-1])
        resp = Wave(resp_total, Fs_resp, label='resp', filename=self.fullpath.parts[-1][:-1])

        #for s in [ecg, ppg, resp]:
        #for s in [resp]:
        #    tracks[s.label] = s
        tracks[resp.label] = resp

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
            ecg = self.tracks[self.main_track_label].value
            #fs = self.tracks[self.main_track_label].fs
            fs = frequency
            
            try:

                total_peak_indices = np.array([], dtype="int32")
                total_valley_indices = np.array([], dtype="int32")
                total_upstroke_indices = np.array([], dtype="int32")
                total_downstroke_indices = np.array([], dtype="int32")
                for start, end in zip(self.start_indexes, self.end_indexes):
                    # NB: 1. Find\fetch preliminary annotation data
                    amp = self.tracks[self.main_track_label].value[start:end]
                    mpd = self.tracks[self.main_track_label].fs * 2
                    idx_peak = detect_peaks(amp, mph=np.median(amp), mpd=mpd, valley=False, show=False, kpsh=False)
                    idx_valley = detect_peaks(amp, mph=np.median(amp), mpd=mpd, valley=True, show=False, kpsh=False)
                    idx_upstroke = detect_peaks(np.diff(amp), mph=np.median(np.diff(amp)), mpd=mpd, valley=False, show=False, kpsh=False)
                    idx_downstroke = detect_peaks(np.diff(amp), mph=np.median(np.diff(amp)), mpd=mpd, valley=True, show=False, kpsh=False)

                    total_peak_indices = np.append(total_peak_indices, idx_peak)
                    total_valley_indices = np.append(total_valley_indices, idx_valley)
                    total_upstroke_indices = np.append(total_upstroke_indices, idx_upstroke)
                    total_downstroke_indices = np.append(total_downstroke_indices, idx_downstroke)

                    # NB: 2. Use inherited functions to assign annotations to the main signal
                    #  all annotation labels should be also in the provided AnnotationConfig file
                    #  User can use _set_annotation_from_time or _set_annotation_from_idx
                from gui import PALMS
                PALMS.get().original_annotations = total_peak_indices
                self._set_annotation_from_idx('rpeak', total_peak_indices)
                self._set_annotation_from_idx('valley', total_valley_indices)
                self._set_annotation_from_idx('upstroke', total_upstroke_indices)
                self._set_annotation_from_idx('downstroke', total_downstroke_indices)
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

                amp = self.tracks[self.main_track_label].value[start:end]
                mpd = self.tracks[self.main_track_label].fs * 2
                idx_peak = detect_peaks(amp, mph=np.median(amp), mpd=mpd, valley=False, show=False, kpsh=False)
                idx_valley = detect_peaks(amp, mph=np.median(amp), mpd=mpd, valley=True, show=False, kpsh=False)
                idx_upstroke = detect_peaks(np.diff(amp), mph=np.median(np.diff(amp)), mpd=mpd, valley=False, show=False, kpsh=False)
                idx_downstroke = detect_peaks(np.diff(amp), mph=np.median(np.diff(amp)), mpd=mpd, valley=True, show=False, kpsh=False)

                total_peak_indices = np.append(total_peak_indices, idx_peak)
                total_valley_indices = np.append(total_valley_indices, idx_valley)
                total_upstroke_indices = np.append(total_upstroke_indices, idx_upstroke)
                total_downstroke_indices = np.append(total_downstroke_indices, idx_downstroke)

                # NB: 2. Use inherited functions to assign annotations to the main signal
                #  all annotation labels should be also in the provided AnnotationConfig file
                #  User can use _set_annotation_from_time or _set_annotation_from_idx
            from gui import PALMS
            PALMS.get().original_annotations = total_peak_indices
            self._set_annotation_from_idx('rpeak', total_peak_indices)
            self._set_annotation_from_idx('valley', total_valley_indices)
            self._set_annotation_from_idx('upstroke', total_upstroke_indices)
            self._set_annotation_from_idx('downstroke', total_downstroke_indices)
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
        try:
            super().save(filename=self.fullpath.stem)
        except Exception as e:
            Dialog().warningMessage('Save crashed with: \n' + str(e), **kwargs)

    def load(self, filename):
        super().load(filename)
