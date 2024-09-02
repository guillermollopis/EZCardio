
import bisect
from typing import List

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QObject, qInfo, qWarning
from PyQt5.QtGui import QFont, QColor, QBrush
from qtpy import QtWidgets

from utils.utils_general import dict_to_df_with_nans
from utils.utils_gui import Dialog


class RRNoisePartition(pg.LinearRegionItem):
    """
    represents non-overlapping regions defined by start/end borders and left/right bounds (limits)
    start\end can be dragged/moved in Partition mode, but cannot reach its limits
    """

    def __init__(self, name: str, *, start: float = None, end: float = None, click: bool = False):
        """
        constructor when start/end are given explicitly. when created from mouse click (single point) see self.from_click
        """
        
        from gui import PALMS
        
        from logic.databases.DatabaseHandler import Database
        
        track = Database.get().tracks[Database.get().main_track_label]
        #if (click):
        left_bound, right_bound = RRNoisePartitions.calculate_boundaries(start, end)
        left_bound = left_bound if left_bound is not None else track.minX
        right_bound = right_bound if right_bound is not None else track.maxX
         
        start = max([max([start, track.minX]), left_bound])
        end = min([min([end, track.maxX]), right_bound])
        
        #else:
        #left_bound = start
        #right_bound = end
        

        super().__init__((start, end))
        self.setBounds([left_bound, right_bound])
        self.track = track
        self.start = start
        self.end = end
        self.mid = self.start + (self.end - self.start) / 2
        self.name = name
        self.label = pg.TextItem(name)
        
        # Color
        # Set the brush color to red
        color = QColor(0, 0, 0) # black
        brush = QBrush(color)
        self.setBrush(brush)

        self.label.setFont(QFont("", PALMS.config['partition_labels_font_size'], QFont.Bold))
        # self.label.setColor(QColor('k'))
        self.label.setAnchor((0.5, 1))
        self.label.setPos(self.mid, self.track.get_yrange_between(self.start, self.end)[0])
        
        RRNoisePartitions.add(self)
        
        RRNoisePartitions.update_all_bounds(self)
        

        # # update config with new partition name
        # from gui.viewer import PALMS
        # PALMS.config['default_partition_labels'] = list(
        #     unique_everseen(PALMS.config['default_partition_labels'] + Partitions.unique_labels()))


        self.sigRegionChangeFinished.connect(self.region_moved)
        
        qInfo('Region {} [{:0.2f}; {:0.2f}] created'.format(self.name, self.start, self.end))
        

    @classmethod
    def from_click(cls, name: str, *, click_x: float, click: bool = False):
        """construct SinglePartition from single point: calculate its start/end considering other partitions"""
        from logic.databases.DatabaseHandler import Database
        from gui import PALMS
        
        track = Database.get().tracks[Database.get().main_track_label]
        
        initial_span = (track.maxX - track.minX) * 0.01
        initial_span = PALMS.config['initial_partition_span_sec']  # NB: set initial span of just created partition
        left_bound, right_bound = RRNoisePartitions.calculate_boundaries(click_x, click_x)
        left_bound = left_bound if left_bound is not None else track.minX
        right_bound = right_bound if right_bound is not None else track.maxX
        

        start = max([max([click_x - initial_span / 2, track.minX]), left_bound])
        end = min([min([click_x + initial_span / 2, track.maxX]), right_bound])
        return cls(name, start=start, end=end)
    
    @classmethod
    def from_start_end(cls, name: str, *, start: int, end: int, click: bool = True):
        """construct SinglePartition from single point: calculate its start/end considering other partitions"""
        from logic.databases.DatabaseHandler import Database
        from gui import PALMS
        track = Database.get().tracks[Database.get().main_track_label]
        initial_span = (track.maxX - track.minX) * 0.01
        initial_span = PALMS.config['initial_partition_span_sec']  # NB: set initial span of just created partition
        # It is in sample index, convert to seconds
        start = start * PALMS.get().FREQUENCY
        end = end * PALMS.get().FREQUENCY
        
        left_bound, right_bound = RRNoisePartitions.calculate_boundaries(start, end)
        left_bound = left_bound if left_bound is not None else track.minX
        right_bound = right_bound if right_bound is not None else track.maxX
        
        return cls(name, start=start, end=end)
    

    def region_moved(self):

        # Update PALMS indexes
        from gui import PALMS
        
        if PALMS.get().RR_ONLY:

            previous_end = PALMS.get().from_time_to_closest_sample(self.end)
            previous_start = PALMS.get().from_time_to_closest_sample(self.start)

            index_in_start = np.where(PALMS.get().START_INDEXES==previous_end)
            index_in_end = np.where(PALMS.get().END_INDEXES==previous_start)
    
            self.start, self.end = self.getRegion()

            start_sample = PALMS.get().from_time_to_closest_sample(self.start)
            end_sample = PALMS.get().from_time_to_closest_sample(self.end)

            if (start_sample != previous_start): # update start
                PALMS.get().END_INDEXES[index_in_end] = start_sample
            if (end_sample != previous_end):
                PALMS.get().START_INDEXES[index_in_start] = end_sample

            # Update visual 
            self.mid = self.start + (self.end - self.start) / 2
            self.label.setPos(self.mid, self.track.get_yrange_between(self.start, self.end)[0])


        RRNoisePartitions.remove_zero_partitions()
            
        RRNoisePartitions.update_all_bounds()

        qInfo('RR Region {} moved'.format(self.name))



    def region_deleted(self):
        
        if self is not None:
            from gui import PALMS

            if PALMS.get().RR_ONLY:
                previous_end = PALMS.get().from_time_to_closest_sample(self.end)
                previous_start = PALMS.get().from_time_to_closest_sample(self.start)
                index_in_start = np.where(PALMS.get().START_INDEXES==previous_end)
                index_in_end = np.where(PALMS.get().END_INDEXES==previous_start)
                PALMS.get().END_INDEXES = np.delete(PALMS.get().END_INDEXES, index_in_end)
                PALMS.get().START_INDEXES = np.delete(PALMS.get().START_INDEXES, index_in_start)
            
            self.label.getViewBox().removeItem(self.label)
            self.getViewBox().removeItem(self)
            RRNoisePartitions.delete(self)
            RRNoisePartitions.update_all_bounds()
            qInfo('Region {} [{:0.2f}; {:0.2f}] deleted'.format(self.name, self.start, self.end))
            # Update rr interval as new intra-signals



class RRNoisePartitions(QObject):
    """
    static class to operate on all existing SinglePartition instances
    """
    partitions: List[RRNoisePartition] = []  # keep sorted list of all SinglePartition instances

    def __new__(*args):  # instead of creating, return list of SinglePartition
        return RRNoisePartitions.partitions

    @staticmethod
    def remove_zero_partitions():  # if start==end --> SinglePartition is flat
        for p in RRNoisePartitions():
            x1, x2 = p.getRegion()
            if x1 == x2:
                p.region_deleted()

    @staticmethod
    def update_all_bounds(avoid_this_p: RRNoisePartition = None):
        """
        As SinglePartitions cannot overlap, after creating\moving\deleting it is necessary to update
        the limits to which every SinglePartition can be moved\dragged
        """
        for p in RRNoisePartitions():
            if not p == avoid_this_p:
                left_bound, right_bound = RRNoisePartitions.calculate_boundaries(p.start, p.end)
                left_bound = left_bound if left_bound is not None else p.track.minX
                right_bound = right_bound if right_bound is not None else p.track.maxX
                p.setBounds([left_bound, right_bound])

    @staticmethod
    def calculate_boundaries(this_left: float, this_right: float):
        """
        check nearest left and nearest right SinglePartition borders and set limits for this SinglePartition
        """
        nearest_left = bisect.bisect_right(RRNoisePartitions.all_endpoints(), this_left) - 1
        nearest_right = bisect.bisect_left(RRNoisePartitions.all_startpoints(), this_right)
        try:
            left_boundary = RRNoisePartitions()[nearest_left].end if nearest_left >= 0 else None
        except:
            left_boundary = None

        try:
            right_boundary = RRNoisePartitions()[nearest_right].start if nearest_right >= 0 else None
        except:
            right_boundary = None

        return left_boundary, right_boundary

    @staticmethod
    def unhide_all_partitions():
        from gui.viewer import Viewer
        for i in RRNoisePartitions():
            Viewer.get().selectedView.renderer.vb.addItem(i)
            Viewer.get().selectedView.renderer.vb.addItem(i.label)

    @staticmethod
    def hide_all_partitions():
        from gui.viewer import Viewer
        for i in RRNoisePartitions():
            Viewer.get().selectedView.renderer.vb.removeItem(i)
            Viewer.get().selectedView.renderer.vb.removeItem(i.label)

    @staticmethod
    def all_startpoints():
        return np.array([p.start for p in RRNoisePartitions.partitions])
    
    @staticmethod
    def all_startpoints_by_name(filter_name):
        filtered_objects = list(filter(lambda obj: obj.name == filter_name, RRNoisePartitions.partitions))
        return np.array([p.start for p in filtered_objects])

    @staticmethod
    def all_endpoints():
        return np.array([p.end for p in RRNoisePartitions.partitions])
    
    @staticmethod
    def all_endpoints_by_name(filter_name):
        filtered_objects = list(filter(lambda obj: obj.name == filter_name, RRNoisePartitions.partitions))
        return np.array([p.end for p in filtered_objects])
    
    @staticmethod
    def all_startpoints_by_two_names(filter_name1, filter_name2):
        filtered_objects = list(filter(lambda obj: obj.name == filter_name1 or obj.name == filter_name2, RRNoisePartitions.partitions))
        return np.array([p.start for p in filtered_objects])
    
    @staticmethod
    def find_partitions_by_two_names(filter_name1, filter_name2):
        filtered_objects = list(filter(lambda obj: obj.name == filter_name1 or obj.name == filter_name2, RRNoisePartitions.partitions))
        return np.array(filtered_objects)
    
    @staticmethod
    def all_endpoints_by_two_names(filter_name1, filter_name2):
        filtered_objects = list(filter(lambda obj: obj.name == filter_name1 or obj.name == filter_name2, RRNoisePartitions.partitions))
        return np.array([p.end for p in filtered_objects])

    @staticmethod
    def add(p: RRNoisePartition):
        idx = bisect.bisect_left(RRNoisePartitions.all_midpoints(), p.mid)
        RRNoisePartitions.partitions.insert(idx, p)

    @staticmethod
    def add_all(labels: List[str], start: np.ndarray, end: np.ndarray):
        """
        batch adding partitions, e.g. from loaded annotations file

        """
        try:
            RRNoisePartitions.delete_all()
            assert len(labels) == start.size & start.size == end.size, 'Every loaded partition should have label, start and end'
            for l, s, e in zip(labels, start, end):
                RRNoisePartition(l, start=s, end=e)
        except Exception as e:
            Dialog().warningMessage('Partitions cannot be loaded\n' + str(e))

    @staticmethod
    def delete(p: RRNoisePartition):
        RRNoisePartitions.partitions.remove(p)

    @staticmethod
    def delete_all():
        RRNoisePartitions.hide_all_partitions()
        RRNoisePartitions.partitions = []

    @staticmethod
    def find_partition_by_point(click_x: float):  # get partition under mouse click or None
        idx = np.where((click_x >= RRNoisePartitions.all_startpoints()) & (click_x <= RRNoisePartitions.all_endpoints()))[0]
        if len(idx) == 1:
            return RRNoisePartitions()[idx[0]]
        elif len(idx) == 0:
            return None
        else:
            qWarning('More than one partition found! Return the first')  # should not happen, as partitions don't overlap
            return RRNoisePartitions()[idx[0]]
        

    @staticmethod
    def find_partition_by_start(previous_start):  # get partition under mouse click or None
        from gui.viewer import PALMS
        
        filtered_objects = list(filter(lambda obj: PALMS.get().from_time_to_closest_sample(obj.start) == previous_start, RRNoisePartitions.partitions))

        if (filtered_objects == []):
            filtered_objects = list(filter(lambda obj: PALMS.get().from_time_to_closest_sample(obj.start)+1 == previous_start, RRNoisePartitions.partitions))

        if (filtered_objects == []):
            filtered_objects = list(filter(lambda obj: PALMS.get().from_time_to_closest_sample(obj.start)-1 == previous_start, RRNoisePartitions.partitions))

        return filtered_objects
        
    @staticmethod
    def find_partitions_by_name(filter_name):
        filtered_objects = list(filter(lambda obj: obj.name == filter_name, RRNoisePartitions.partitions))
        return np.array(filtered_objects)

    # TODO: ensure non overlapping partitions!!!
    # TODO: partitions outside signal
    @staticmethod
    def all_startpoints():
        return np.array([p.start for p in RRNoisePartitions.partitions])

    @staticmethod
    def all_endpoints():
        return np.array([p.end for p in RRNoisePartitions.partitions])

    @staticmethod
    def all_midpoints():
        return np.array([p.mid for p in RRNoisePartitions.partitions])

    @staticmethod
    def all_labels():
        return [p.name for p in RRNoisePartitions.partitions]

    #@staticmethod
    #def unique_labels():
    #    return list(unique_everseen(RRNoisePartitions.all_labels()))

    @staticmethod
    def to_csv(filename: str):
        d = {'label': RRNoisePartitions.all_labels(), 'start': RRNoisePartitions.all_startpoints(), 'end': RRNoisePartitions.all_endpoints()}
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
                Dialog().warningMessage('Save crashed with:\n' + str(e))

    @staticmethod
    def clear_annotations_in_this_partition(p: RRNoisePartition):
        """
        batch removing annotations which fall within a partition.
        good to have if it is needed to clean large artifact region from spurious fiducials
        """
        try:
            from logic.operation_mode.annotation import AnnotationConfig
            from gui.viewer import Viewer
            aConf = AnnotationConfig.get()
            for f in aConf.fiducials:
                ann = f.annotation
                remove_idx = np.arange(bisect.bisect_right(ann.x, p.start), bisect.bisect_left(ann.x, p.end))
                nn = max(remove_idx.shape)
                result = QtWidgets.QMessageBox.question(Viewer.get(), "Confirm Delete Annotations...",
                                                        "Are you sure you want to delete {nn} {name} annotations ?".format(nn=nn, name=ann.name),
                                                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                if result == QtWidgets.QMessageBox.Yes:
                    ann.x = np.delete(ann.x, remove_idx)
                    ann.y = np.delete(ann.y, remove_idx)
                    ann.idx = np.delete(ann.idx, remove_idx)
                    Viewer.get().selectedDisplayPanel.plot_area.redraw_fiducials()
            RRNoisePartitions.update_all_bounds()

        except Exception as e:
            Dialog().warningMessage('Deleting annotations failed with\n' + str(e))
