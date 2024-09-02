"""
Copyright (c) 2020 Stichting imec Nederland (PALMS@imec.nl)
https://www.imec-int.com/en/imec-the-netherlands
@license GPL-3.0+ <http://spdx.org/licenses/GPL-3.0+>
See COPYING, README.
"""
import bisect
import weakref
from typing import List

import numpy as np
import pandas as pd
from PyQt5.QtCore import pyqtSlot, QObject, pyqtSignal, qInfo
from pyqtgraph import mkBrush, mkPen
from qtpy.QtCore import Signal

from logic.databases.DatabaseHandler import Database
from utils.detect_peaks import detect_peaks
from utils.utils_general import find_closest, dict_to_df_with_nans
from logic.operation_mode.noise_partitioning import NoisePartitions

class Annotation(QObject):
    signal_annotate = pyqtSignal(float)
    signal_delete_annotation = pyqtSignal(float)

    def __init__(self, fiducial_name, x_=np.array([]), y_=np.array([]), parent=None):
        super(QObject, self).__init__(parent)
        self.name = fiducial_name.lower()
        self.x = x_
        self.y = y_
        self.idx = np.array([])
        Annotation._instance = weakref.ref(self)()
        self.signal_annotate.connect(self.add)
        self.signal_delete_annotation.connect(self.delete)

    def find_annotation_between_two_ts(self, x1, x2):
        """
        finds annotation points within given x-limits. used to redraw only part of the annotations when zooming\moving a plot
        !!! MUST be computationally efficient otherwise will slow down browsing through the plot
        """
        x, y = np.array([]), np.array([])

        # import time
        # s = time.time()
        # for i in np.arange(10000):
        #     idx = np.arange(np.searchsorted(self.x, x1, 'right'), np.searchsorted(self.x, x2, 'left'))
        idx = np.arange(bisect.bisect_right(self.x, x1), bisect.bisect_left(self.x, x2))
        # This gets the indices of x (fiducials) that are under the [x1,x2] range. If upsampling, divide x by n before this line
        # en = time.time() - s

        if idx.size > 0:
            x = self.x[idx]
            y = self.y[idx]
        return np.array(x), np.array(y)
    
    @classmethod
    def get(cls):
        return Annotation._instance if Annotation._instance is not None else cls()

    @pyqtSlot(float)
    def delete(self, x):
        from gui.viewer import Viewer
        plot_area = Viewer.get().selectedDisplayPanel.plot_area

        fiducial_name = self.name
        fConf = AnnotationConfig.get()[fiducial_name]
        if fConf.annotation.x.size > 0:
            # closest_idx, _, _ = find_closest(fConf.annotation.x, np.array([x]))
            closest_idx = np.argmin(abs(x - fConf.annotation.x))
            deleted_x, deleted_y = fConf.annotation.x[closest_idx], fConf.annotation.y[closest_idx]

            fConf.annotation.x = np.delete(fConf.annotation.x, closest_idx)
            fConf.annotation.y = np.delete(fConf.annotation.y, closest_idx)
            fConf.annotation.idx = np.delete(fConf.annotation.idx, closest_idx)

            Viewer.get().selectedDisplayPanel.plot_area.redraw_fiducials()
            plot_area.signal_annotation_added.emit(deleted_x, deleted_y, 'deleted')

            # Update track
            from gui.viewer import PALMS
            PALMS.get().singleUpdateRR(PALMS.get().from_time_to_closest_sample(x), 1, True)
            qInfo('{n} deleted'.format(n=fiducial_name))
        else:
            qInfo('No {n} to be deleted'.format(n=fiducial_name))

        

    @pyqtSlot(float)
    def add(self, x):
        fiducial_name = self.name
        from gui.viewer import Viewer
        from gui import PALMS
        plot_area = Viewer.get().selectedDisplayPanel.plot_area
        track = plot_area.main_window.selectedTrack  # annotation can only be added to the main track, but there are checks on this before
        fs = track.fs

        amp = track.value
        ts = track.get_time()
        fConf = AnnotationConfig.get()[fiducial_name]
        insert_index = bisect.bisect_right(fConf.annotation.x, x)

        min_distance_samples = round(fs * fConf.min_distance)
        blocked_region = np.array([])
        if insert_index > 0:
            blocked_region = np.arange(fConf.annotation.idx[insert_index - 1],
                                       fConf.annotation.idx[insert_index - 1] + min_distance_samples)
        if len(fConf.annotation.idx) > insert_index:
            blocked_region = np.append(blocked_region, np.arange(fConf.annotation.idx[insert_index] - min_distance_samples,
                                                                 fConf.annotation.idx[insert_index] + 1))
        if insert_index > 0 and fConf.annotation.idx.size > insert_index:
            allowed_region = np.arange(fConf.annotation.idx[insert_index - 1] + min_distance_samples,
                                       fConf.annotation.idx[insert_index] - min_distance_samples)
        elif insert_index > 0 and fConf.annotation.idx.size == insert_index:
            allowed_region = np.arange(fConf.annotation.idx[insert_index - 1] + min_distance_samples,
                                       ts.shape[0])
        elif insert_index == 0 and fConf.annotation.idx.size > insert_index:
            allowed_region = np.arange(0, fConf.annotation.idx[insert_index] - min_distance_samples)
        elif insert_index == 0 and fConf.annotation.idx.size == insert_index:
            allowed_region = np.arange(0, ts.shape[0])

        pinned_to_track = plot_area.main_window.selectedPanel.get_view_from_track_label(fConf.pinned_to_track_label).track
        if fConf.is_pinned:
            # TODO: pin should take into account blocked region, as more important requirement
            #x = fConf.annotation.pin(x, pinned_to_track, fConf.pinned_to_location, fConf.pinned_window, allowed_region)
            pass

        if x is None:
            qInfo('{}: duplicate annotation; min_distance is set to {} s'.format(fiducial_name.upper(), fConf.min_distance))
            return
        ind, _, _ = find_closest(ts, np.array([x]))
        assert len(ind) == 1

        # min_distance_samples = round(fs * fConf.min_distance)
        # blocked_region = np.array([])
        # if insert_index > 0:
        #     blocked_region = np.arange(fConf.annotation.idx[insert_index - 1],
        #                                fConf.annotation.idx[insert_index - 1] + min_distance_samples)
        # if len(fConf.annotation.idx) > insert_index:
        #     blocked_region = np.append(blocked_region, np.arange(fConf.annotation.idx[insert_index] - min_distance_samples,
        #                                                          fConf.annotation.idx[insert_index] + 1))
        if not ind[0] in blocked_region:
            fConf.annotation.idx = np.insert(fConf.annotation.idx, insert_index, ind[0])
            fConf.annotation.x = np.insert(fConf.annotation.x, insert_index, ts[ind[0]])
            y = amp[ind[0]]
            fConf.annotation.y = np.insert(fConf.annotation.y, insert_index, y)
            plot_area.signal_annotation_added.emit(x, y, 'added')
            # Update track
            from gui.viewer import PALMS
            PALMS.get().singleUpdateRR(PALMS.get().from_time_to_closest_sample(x), 0, True)
            qInfo('{n}: x= {X} y= {Y}'.format(n=fiducial_name, X=str(np.round(x, 2)), Y=str(np.round(y, 2))))
        else:
            qInfo('{}: duplicate annotation; min_distance is set to {} s'.format(fiducial_name.upper(), fConf.min_distance))
            return
        

    def pin(self, x: float, track, pinned_to: str, pinned_window: float, allowed_region_idx: List[int]):
        DEBUG = False
        window = pinned_window  # sec

        if len(allowed_region_idx) < 3:
            return None

        amp = track.value
        ts = track.get_time()
        fs = track.get_fs()

        x_ind = np.argmin(abs(ts - x))
        left_x_ind, right_x_ind = int(max([x_ind - round(fs * window), 0])), int(min([x_ind + round(fs * window), amp.size]))
        left_x_ind, right_x_ind = int(max([allowed_region_idx[0], left_x_ind])), int(min(
            [allowed_region_idx[-1], right_x_ind]))  # both within window and allowed region
        sx, sy = ts[left_x_ind:right_x_ind], amp[left_x_ind:right_x_ind]
        # sy = scipy.signal.medfilt(sy, round_to_odd(fs * 0.02))  # TODO: parametrize smoothing

        if pinned_to.lower().__contains__('peak'):
            ind = detect_peaks(sy, show=DEBUG)
        elif pinned_to.lower().__contains__('valley'):
            ind = detect_peaks(sy, valley=True, show=DEBUG)
        else:
            raise ValueError

        if ind.size > 0:
            closest, _, _ = find_closest(ind + left_x_ind, np.array([x_ind]))
            highest = np.argmax(abs(sy[ind] - np.mean(sy)))
            ind_to_return = highest  # take highest of all peaks found
            return sx[ind[ind_to_return]]
        else:
            qInfo('{p} not found'.format(p=pinned_to))
            return x

    def create_RRinterval_track(self, correct=False):
        from gui import PALMS
        db = Database.get()
        
        track_fs = db.tracks[db.main_track_label].fs
        track_ts = db.tracks[db.main_track_label].ts

        fs = track_fs  # maximum zooming is defined by the lowest sampling freq of all tracks
        #if PALMS.get().RR_ONLY is False:
        #    rr_ts = np.arange(track_ts[0], round(track_ts[-1]), 1 / fs).astype(float)
        #else:
        rr_ts = np.arange(track_ts[0], PALMS.get().END_MISSING_INDEXES[-1] / PALMS.get().FREQUENCY, 1 / PALMS.get().FREQUENCY).astype(float)
        
        annotations = [fiducial.annotation.idx for fiducial in AnnotationConfig.get().fiducials]
        annotations = np.array(annotations[0]) # points in which there is peak
        
        total_rr = np.zeros_like(rr_ts) # interpolated values here
        local_rr = np.zeros_like(rr_ts) # just r intervals and 0s
        current_index = 0
        start_indexes = PALMS.get().START_MISSING_INDEXES
        end_indexes = PALMS.get().END_MISSING_INDEXES

        for start, end in zip(start_indexes, end_indexes):
            
            current_annotations = annotations[(annotations >= start) & (annotations <= end)]
            
            if (current_annotations != []):
                annotation_intervals = np.diff(current_annotations)
                
                interval_times = annotation_intervals / track_fs # r-r intervals

                if (correct):
                    # get interpolation points and get their value
                    annotation_indexes = np.array([], dtype="int32")
                    PALMS.get().INTERPOLATIONS = np.array(PALMS.get().INTERPOLATIONS)
                    interpolation_indeces = np.concatenate((PALMS.get().INTERPOLATIONS, PALMS.get().algorithm_outliers.get("interpolate", np.array([], dtype="int32")))) # time where there is interpolation
                    if (len(interpolation_indeces) != 0):
                        interpolation_indeces = np.array(interpolation_indeces) 
                        interpolation_samples = np.vectorize(PALMS.get().from_time_to_closest_sample)(interpolation_indeces)# sample in which there is interpolation
                        annotation_indexes = np.where(np.isin(current_annotations, interpolation_samples))[0]# index of annotation in which there is interpolation (interval_time is this-1)

                    for annotation_index in annotation_indexes: 

                        rr_index = int(annotation_index)-1

                        # get previous 5 rr_intervals
                        start_index = max(0, (rr_index - 5))
                        window_pre = interval_times[start_index:(rr_index-1)]

                        end_index = min(len(interval_times), (rr_index + 6))
                        window_post = interval_times[(rr_index+1):end_index]
                    
                        mean = np.mean(np.concatenate((window_pre, window_post)))

                        interval_times[rr_index] = mean
                
                local_rr[current_annotations[1:]] = interval_times
                
                if (start == 0 and len(db.start_indexes)!=1): # if start is the first in a list with more indexes
                    interpolated_rr = np.interp(list(range(start, end)), current_annotations[1:], interval_times)
                elif (current_index > 0 and current_index < len(db.start_indexes)-1): # in the middle
                    interpolated_rr = np.interp(list(range(start, end)), current_annotations[1:], interval_times)
                else:
                    interpolated_rr = np.interp(list(range(start, end)), current_annotations[1:], interval_times)
                
                total_rr[start:end] = interpolated_rr

                
            current_index = current_index + 1

        from gui.tracking import Wave
        rr_int_wave = Wave(total_rr, fs, offset=0, label='RR', unit='sec')
        rr_int_wave.type = 'RR'
        
        # for convenience when getting results, local_rr has 0 values when noise
        noise_start_points = NoisePartitions.all_startpoints()
        noise_end_points = NoisePartitions.all_endpoints()

        for start, end in zip(noise_start_points, noise_end_points):
            local_rr[PALMS.get().from_time_to_closest_sample(start): PALMS.get().from_time_to_closest_sample(end)] = 0

        return rr_int_wave, local_rr


    def update_RRinterval_track(self, annotation_change, change_type):
        # annotation_change: index of the sample where the change will be done
        # change_type: 0 to add, 1 to delete, 2 to interpolate

        from gui import PALMS
        import copy
        old_rr_intervals = copy.deepcopy(PALMS.get().fiducials.value)
        intervals = copy.deepcopy(PALMS.get().rr_intervals)

        annotations = [fiducial.annotation.idx for fiducial in AnnotationConfig.get().fiducials]
        annotations = copy.deepcopy(np.array(annotations[0])) # points in which there is peak

        try:
            previous_annotation = max(annotations[np.where(annotations < annotation_change)[0][-1]], 0)
        except:
            previous_annotation = 0

        try: 
            next_annotation = min(annotations[np.where(annotations > annotation_change)[0][0]], len(PALMS.get().ECG_DATA)-2)
        except:
            next_annotation = len(PALMS.get().ECG_DATA)-2
        # for add: get second next
        try:
            second_next_annotation = min(annotations[np.where(annotations > next_annotation)[0][0]], len(PALMS.get().ECG_DATA)-2)
        except:
            second_next_annotation = len(PALMS.get().ECG_DATA)-2

        if change_type == 1: # if delete the current disapears, so current annotation is really previous
            first_interval = (next_annotation-previous_annotation)/PALMS.get().FREQUENCY # from previous to added
            second_interval = (second_next_annotation-next_annotation)/PALMS.get().FREQUENCY # from added to next
            local_rr = np.interp(list(range(previous_annotation, second_next_annotation)), [previous_annotation, next_annotation, second_next_annotation], [old_rr_intervals[previous_annotation], first_interval, second_interval])

        elif change_type == 0: # add
            first_interval = (annotation_change-previous_annotation)/PALMS.get().FREQUENCY # from previous to added
            second_interval = (next_annotation-annotation_change)/PALMS.get().FREQUENCY # from added to next
            third_interval = (second_next_annotation-next_annotation)/PALMS.get().FREQUENCY
            local_rr = np.interp(list(range(previous_annotation, second_next_annotation)), [previous_annotation, annotation_change, next_annotation, second_next_annotation], [old_rr_intervals[previous_annotation], first_interval, second_interval, third_interval])
        
        elif change_type == 2: # add interpolation
            annotation_index = np.where(annotations == annotation_change)[0][0]
            min_index = max(0, annotation_index-5)
            max_index = min(len(PALMS.get().ECG_DATA), annotation_index+5)
            # to get mean rr: sum all and divide by how many and frequency
            interpolated_value = np.mean(np.diff(annotations[min_index:max_index])) / (PALMS.get().FREQUENCY)
            local_rr = np.interp(list(range(previous_annotation, next_annotation)), [previous_annotation, annotation_change, next_annotation], [old_rr_intervals[previous_annotation], interpolated_value, old_rr_intervals[next_annotation]])

        elif change_type == 3: # delete interpolation
            real_value = (annotation_change-previous_annotation) / PALMS.get().FREQUENCY
            local_rr = np.interp(list(range(previous_annotation, next_annotation)), [previous_annotation, annotation_change, next_annotation], [old_rr_intervals[previous_annotation], real_value, old_rr_intervals[next_annotation]])

        if change_type==0: # add
            old_rr_intervals[previous_annotation:second_next_annotation] = local_rr
            #if (previous_annotation != annotations[0]):
             #   intervals[previous_annotation] = old_rr_intervals[previous_annotation]
            intervals[annotation_change] = old_rr_intervals[annotation_change]
            intervals[next_annotation] = old_rr_intervals[next_annotation]

        elif change_type==1: # delete
            old_rr_intervals[previous_annotation:second_next_annotation] = local_rr
            #if (previous_annotation != annotations[0]):
             #   intervals[previous_annotation] = old_rr_intervals[previous_annotation]
            non_null_indices = np.where(intervals[previous_annotation+10:second_next_annotation] != 0)[0] + previous_annotation + 10
            intervals = np.delete(intervals, non_null_indices[0])  # Adjust second index due to the removal of the first
            intervals = np.delete(intervals, non_null_indices[1]-1) 
            intervals = np.insert(intervals, annotation_change, old_rr_intervals[annotation_change])
            #intervals[next_annotation] = old_rr_intervals[next_annotation]

        else:
            old_rr_intervals[previous_annotation:next_annotation] = local_rr
            #if (previous_annotation != annotations[0]):
             #   intervals[previous_annotation] = old_rr_intervals[previous_annotation]
            intervals[annotation_change] = old_rr_intervals[annotation_change]

        from gui.tracking import Wave
        rr_int_wave = Wave(old_rr_intervals, int(PALMS.get().FREQUENCY), offset=0, label='RR', unit='sec')
        rr_int_wave.type = 'RR'


        return rr_int_wave, intervals
    
    def updateFiducialsNoise(self):

        from gui import PALMS
        import copy

        rr_intervals = copy.deepcopy(PALMS.get().fiducials.value)

        annotations = [fiducial.annotation.idx for fiducial in AnnotationConfig.get().fiducials]
        annotations = np.array(annotations[0]) # points in which there is peak

        mask = np.ones(len(rr_intervals))
        mask[annotations] = 0

        fiducials = copy.deepcopy(rr_intervals)
        fiducials[mask==1] = 0

        # noise
        noise_start_points = NoisePartitions.all_startpoints()
        noise_end_points = NoisePartitions.all_endpoints()

        for start, end in zip(noise_start_points, noise_end_points):
            fiducials[PALMS.get().from_time_to_closest_sample(start): PALMS.get().from_time_to_closest_sample(end)] = 0


        # update fiducials
        PALMS.get().rr_intervals = copy.deepcopy(fiducials)


class SingleFiducialConfig:
    def __init__(self, data: dict):
        from gui import PALMS
        #assert all([k in data for k in PALMS.config['annotationConfig_columns']])
        name = data['name'].lower()
        key = data['key']
        is_pinned = data['is_pinned']
        pinned_to = data['pinned_to']
        pinned_window = data['pinned_window']
        min_distance = data['min_distance']
        symbol = data['symbol']
        symbol_size = data['symbol_size']
        symbol_colour = data['symbol_colour']

        self.name = name
        self.key, self.is_pinned, self.pinned_to, self.pinned_window, self.min_distance = key, is_pinned, pinned_to, pinned_window, min_distance
        self.symbol = symbol
        self.symbol_size = symbol_size
        self.symbol_colour = symbol_colour
        self.symbol_pen = mkPen(cosmetic=False, width=1, color=self.symbol_colour)
        self.symbol_brush = mkBrush(self.symbol_colour)
        self.pxMode = True
        self.annotation = Annotation(self.name)

        self.split_pinned_to()

    def split_pinned_to(self):
        try:
            from gui.viewer import PALMS
            if self.pinned_to in PALMS.config['pinned_to_options']:
                self.pinned_to = self.pinned_to + ' ' + Database.get().main_track_label

            pinned_to_split = self.pinned_to.split()
            # TODO: make it more generic and foolproof, now it is assumed that pinned_to consists of two words: peak\valley + track_label
            #assert_text = '{} pinned_to setting must consist of two words:\n' \
            #              '"peak" or "valley" + track_label from the database;\n' \
            #              'Current pinned_to value is {}\n' \
            #              'Check your AnnotationConfig file {} and run the tool again'.format(self.name, self.pinned_to,
            #                                                                                  Database.get().annotation_config_file.stem)
            #assert len(pinned_to_split) == 2, assert_text
            #assert pinned_to_split[0] in PALMS.config['pinned_to_options'], assert_text
            self.pinned_to_location = pinned_to_split[0]
            self.pinned_to_track_label = pinned_to_split[1]
        except Exception as e:
            from utils.utils_gui import Dialog
            Dialog().warningMessage('Error in split_pinned_to():\n' + str(e))
            raise ValueError

    def print(self):
        print(self.__str__())

    def set_annotation_from_time(self, ts, track):
        # TODO: make it properly via init of Annotation(...)
        ts = ts[~np.isnan(ts)]
        self.annotation.x = ts
        idx, _, _ = find_closest(track.time, ts)
        self.annotation.y = track.value[idx]
        self.annotation.idx = idx

    def set_annotation_from_idx(self, idx, track):
        # TODO: make it properly via init of Annotation(...)
        idx = idx[~np.isnan(idx)]
        self.annotation.idx = idx
        self.annotation.x = track.time[idx]
        self.annotation.y = track.value[idx]


class AnnotationConfig(QObject):
    signal_config_changed = Signal(list, name='config_changed')
    _instance = None

    def __init__(self, parent=None):
        super(QObject, self).__init__(parent)
        self.fiducials = []
        AnnotationConfig._instance = weakref.ref(self)()
        self.signal_config_changed.connect(self.reload_config)

    def clear(self):
        self.fiducials = []
        from gui.dialogs.AnnotationConfigDialog import AnnotationConfigDialog
        AnnotationConfigDialog.get().aConf_to_table(AnnotationConfig.get())

    def reset_fiducials_config(self, fiducials):
        for f in fiducials:
            if self.find_idx_by_name(f.name) is not None:
                idx = self.find_idx_by_name(f.name)
                # TODO: copy annotation
                tmp_annotation = self.fiducials[idx].annotation
                self.fiducials[idx] = f
                self.fiducials[idx].annotation = tmp_annotation
            else:
                self.fiducials.append(f)

    @classmethod
    def get(cls):
        return AnnotationConfig._instance if AnnotationConfig._instance is not None else cls()

    def find_idx_by_name(self, name: str):
        if not self.fiducials:
            return None
        else:
            idx = [i for i, f in enumerate(self.fiducials) if name == f.name]
            assert len(idx) in [0, 1]
            if len(idx) == 0:
                return None  # TODO: if not found case
            else:
                return idx[0]

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.fiducials[self.find_idx_by_name(item)]
        elif isinstance(item, int):
            return self.fiducials[item]

    def is_valid(self):
        if len(self.fiducials) > 0:
            return True
        return False

    @staticmethod
    def all_fiducials():
        return [f.name for f in AnnotationConfig.get().fiducials]

    @classmethod
    # TODO: generalize and combine with refreshing aConf from GUI
    def from_csv(cls, csv):
        from gui import PALMS
        settings_init = pd.read_csv(csv)
        db = Database.get()
        fiducials = []
        for _, row_data in settings_init.iterrows():
            #assert all([k in row_data for k in PALMS.config['annotationConfig_columns']])
            # NB: recover aConf.pinned_to changes from json
            #  it is not needed as one can rewrite annotation config from AnnotationConfigDialog Save button
            # see also AnnotationConfigDialog where applied data is saved
            # try:
            #     tmp_singleFiducialConfig = SingleFiducialConfig(row_data)
            #     pinned_to_prev_state = PALMS.config['pinned_to_last_state'][tmp_singleFiducialConfig.name]
            #     pinned_to_prev_state = pinned_to_prev_state.split()
            #     if pinned_to_prev_state[0] in PALMS.config['pinned_to_options'] and \
            #         pinned_to_prev_state[1] in db.tracks_to_plot_initially:
            #         row_data['pinned_to'] = " ".join(pinned_to_prev_state)
            #     qInfo('Annotation Config updated with config.json data')
            # except Exception as e:
            #     pass
            fiducials.append(SingleFiducialConfig(row_data))
        aConf = AnnotationConfig.get()
        aConf.reset_fiducials_config(fiducials)
        try:  # NB: nice to do it here, but Viewer object might still not be created
            from gui.viewer import Viewer
            Viewer.get().annotationConfig.aConf_to_table(aConf)
            Viewer.get().annotationConfig.reset_pinned_to_options_to_existing_views()
        except:
            import traceback
            print(traceback.format_exc())
            pass
        return aConf

    def to_csv(self, filename: str, save_idx: bool = False):
        # TODO: pop up window save as and multiple choice of file formats???
        d = {}
        for f in self.fiducials:
            if save_idx:
                d[f.name] = np.sort(f.annotation.idx)
            else:
                d[f.name] = np.sort(f.annotation.x)

        df = dict_to_df_with_nans(d)
        try:
            df.to_csv(filename + '.csv', index=False)
        except OSError as e:
            try:
                #xl = win32com.client.Dispatch("Excel.Application")
                #xl.Quit()  # quit excel, as if user hit the close button/clicked file->exit.
                # xl.ActiveWorkBook.Close()  # close the active workbook
                df.to_csv(filename + '.csv', index=False)
            except Exception as e:
                print(e)

    def size(self):
        return len(self)

    @pyqtSlot(list, name='reload_config')
    def reload_config(self, data):
        aConf = AnnotationConfig.get()
        for i, idx in enumerate(data):
            if i > 0:
                aConf.fiducials.append(
                    SingleFiducialConfig(data[i][0], data[i][1], data[i][2], data[i][3], data[i][4], data[i][5], symbol=data[i][6],
                                         symbol_size=data[i][7], symbol_colour=data[i][8]))
