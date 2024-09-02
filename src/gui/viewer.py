"""
Copyright (c) 2005-2017 TimeView Developers
MIT license (see in gui\LICENSE.txt)
"""
from functools import partial
import json
import time
import logging
import re
import sys
import weakref
import pathlib
from collections import defaultdict
from pathlib import Path
from timeit import default_timer as timer
from typing import Tuple, List, Optional, DefaultDict, Dict
from config import config, tooltips
from gui.dialogs.SelectFileDialog import SelectFileDialog
from utils.QTimerWithPause import QTimerWithPause
import numpy as np
import pyqtgraph as pg
from config.config import ICON_PATH, ALL_DATABASES, DATABASE_MODULE_NAME
from qtpy import QtWidgets, QtGui, QtCore
from qtpy.QtCore import Slot, Signal
from gui.dialogs.AnnotationConfigDialog import AnnotationConfigDialog
from gui.dialogs.help_popup import help_popup
from gui.dialogs.FilterConfigDialog import FilterConfigDialog
from gui import tracking
from logic.databases.DatabaseHandler import Database
from PyQt5.QtCore import qInfo, qDebug
from .display_panel import DisplayPanel, Frame
from .button_panel import ButtonPanel, ButtonFrame
from .left_options_panel import LeftOptionsFrame, LeftOptionsPanel
from .results_panel import ResultsFrame, ResultsPanel
from .outliers_panel import OutliersFrame, OutliersPanel
from .model import Model, View, Panel
from .view_table import ViewTable
from utils.utils_general import get_project_root, resource_path
from utils.utils_gui import Dialog
from logic.operation_mode.operation_mode import Modes, Mode
from logic.operation_mode.partitioning import SinglePartition, Partitions
from logic.operation_mode.noise_partitioning import NoisePartition, NoisePartitions
from logic.operation_mode.rr_noise_partitioning import RRNoisePartition, RRNoisePartitions
from logic.operation_mode.epoch_mode import EpochWindow, EpochModeConfig
from gui.plot_area import PlotArea
from PyQt5.QtWidgets import QApplication, QScrollBar
import datetime as dtime

from PyQt5.QtGui import QFont, QColor, QBrush, QIcon
from PyQt5.QtCore import Qt

from logic.operation_mode.annotation import Annotation, AnnotationConfig
from data_import.main_import import MyMainImport

logger = logging.getLogger()
if __debug__:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARN)




class Group(QtCore.QObject):
    relay = Signal(name='relay')

    def __init__(self) -> None:
        super().__init__()
        self.views: List[View] = []

    def viewsExcludingSource(self, view_to_exclude):
        return [view for view in set(self.views) if view is not view_to_exclude]

    def join(self, view):
        self.views.append(view)
        self.relay.connect(view.renderer.reload)


class ScrollArea(QtWidgets.QScrollArea):
    dragEnterSignal = Signal(name='dragEnterSignal')
    dragLeaveSignal = Signal(name='dragLeaveSignal')
    dropSignal = Signal(name='dropSignal')

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setParent(parent)
        self.dropSignal.connect(self.parent().moveToEnd)
        self.setWidgetResizable(True)
        self.setAcceptDrops(True)
        self.setContentsMargins(0, 0, 0, 0)

    def dropEvent(self, event: QtGui.QDropEvent):
        self.dropSignal.emit()
        event.accept()

    def dragLeaveEvent(self, event: QtGui.QDragLeaveEvent):
        self.dragLeaveSignal.emit()
        event.accept()

    def sizeHint(self):
        return QtCore.QSize(1000, 810)

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.type() == QtCore.QEvent.KeyPress:
            event.ignore()


class ScrollAreaWidgetContents(QtWidgets.QWidget):

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setParent(parent)
        self.viewer = parent.parent()
        self.setContentsMargins(0, 0, 0, 0)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.setAlignment(QtCore.Qt.AlignTop)
        self.layout.setSpacing(2)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        self.dragStartPos = QtCore.QPoint(0, 0)

    def swapWidgets(self, positions: Tuple[int, int]):
        assert len(positions) == 2
        if positions[0] == positions[1]:
            return
        frame_one = self.layout.takeAt(min(positions)).widget()
        frame_two = self.layout.takeAt(max(positions) - 1).widget()
        self.layout.insertWidget(min(positions), frame_two)
        self.layout.insertWidget(max(positions), frame_one)


class Viewer(QtWidgets.QMainWindow):
    queryAxesWidths = Signal(name='queryAxisWidths')
    queryColWidths = Signal(name='queryColWidths')
    setAxesWidth = Signal(float, name='setAxesWidth')
    queryColWidths = Signal(name='queryColWidths')
    setSplitter = Signal(list, name='setSplitter')
    moveSplitterPosition = Signal(name='moveSplitterPosition')
    setColWidths = Signal(list, name='setColWidths')
    refresh = Signal(name='refresh')
    cursorReadoutStatus = Signal(bool, name='cursor_readout_status')
    autoscaleYstatus = Signal(bool, name='autoscaleY_status')
    rewriteH5Status = Signal(bool, name='rewriteH5_status')
    setOperationMode = Signal(Modes, name='setOperationMode')

    _instance = None
    REBOOT_APP = False

    def __init__(self, application):
        super().__init__()
        self.application = application
        # self.annotationManager = ManagerWindow('Annotation Manager',self)
        self.annotationConfig = AnnotationConfigDialog(self.application)
        self.processorConfig = FilterConfigDialog(self.application)
        self.help_popup = help_popup(self.application)
        # self.partitionConfig = PartiotionConfigDialog(self.application) #TODO??
        if ICON_PATH.exists():
            #pix_map_icon = QtGui.QPixmap(str(ICON_PATH), format="JPEG")
            #self.setWindowIcon(QtGui.QIcon(pix_map_icon))
            #  this fixes a warning on OSX, but doesn't work at all on windows
            self.setWindowIcon(QtGui.QIcon(str(ICON_PATH)))
        else:
            logging.warning(f'cannot find icon at {ICON_PATH}')
        #self.resize(QtWidgets.QDesktopWidget().availableGeometry(self).size() * 0.5)  # change this for video capture
        #self.resize(*PALMS.config['viewer_window_size'])
        
        self.model: Model = Model()
        self.track_menu = None
        self.groups: DefaultDict[int, Group] = defaultdict(Group)
        self.setWindowTitle('EZCARDIO')

        # Create the main widget and set it as the central widget
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)

        # Create the top-left component
        self.top_left_frame = LeftOptionsFrame(main_window=self)
        self.top_left_w = LeftOptionsPanel(frame=self.top_left_frame)

        self.top_left_frame.layout.addWidget(self.top_left_w)
        self.top_left_frame.left_options_panel = self.top_left_w

        # Create the top-right component. Check if I can set fixed size (not scroll), otherwise change to just widget or frame
        self.scrollArea = ScrollArea(self)
        self.scrollAreaWidgetContents = ScrollAreaWidgetContents(self.scrollArea)
        #self.setCentralWidget(self.scrollArea)
        self.scrollArea.setWidget(self.scrollAreaWidgetContents)

        # Create the bottom component (results)
        self.results_frame = ResultsFrame(main_window=self)
        self.results_w = ResultsPanel(frame=self.results_frame)

        self.results_frame.layout.addWidget(self.results_w)
        self.results_frame.results_panel = self.results_w

        # Add the functions to the results
        from gui import PALMS
        self.results_w.home_domain_button.pressed.connect(lambda: self.results_w.set_home_results(rr_intervals=PALMS.get().rr_intervals))
        self.results_w.time_domain_button.pressed.connect(lambda: self.results_w.set_time_results(rr_intervals=PALMS.get().rr_intervals))
        self.results_w.frequency_domain_button.pressed.connect(lambda: self.results_w.set_frequency_results(rr_intervals=PALMS.get().rr_intervals))
        self.results_w.non_linear_button.pressed.connect(lambda: self.results_w.set_non_linear_results(rr_intervals=PALMS.get().rr_intervals))
        self.results_w.time_varying_button.pressed.connect(lambda: self.results_w.set_varying_results(rr_intervals=PALMS.get().rr_intervals))
        self.results_w.sports_button.pressed.connect(lambda: self.results_w.set_sports_results(rr_intervals=PALMS.get().rr_intervals))

        # Create the main layout and set the component widgets
        main_layout = QtWidgets.QGridLayout(main_widget)
        main_layout.addWidget(self.top_left_frame, 0, 0)
        main_layout.addWidget(self.scrollArea, 0, 1)
        main_layout.addWidget(self.results_frame, 1, 0, 1, 2)

        # Set the initial sizes of the components
        screen_rect = QApplication.instance().desktop().availableGeometry()
        width = screen_rect.width()*0.95
        height = screen_rect.height()*0.95
        self.original_width = width * 0.25
        self.original_height = height * 0.6
        self.top_left_frame.setFixedSize(width * 0.3, height * 0.6)
        self.scrollArea.setFixedSize(width * 0.7, height * 0.6)
        self.results_frame.setFixedSize(width, height * 0.35)

        # Initialize the resize state
        self.resized_left = False
        self.resized_down = False

        # Finished general GUI
        

        self.synchronized = True
        self.cursor_readout = False
        self.autoscale_y = PALMS.config['autoscale_y']
        self.rewriteH5 = PALMS.config['save_overwrite']

        self.frames: List[Frame] = []
        self.selected_frame: Optional[Frame] = None
        self.moving_frame: Optional[Frame] = None
        self.from_index: Optional[int] = None
        self.to_index: Optional[int] = None

        self.axis_width = 10
        # for storing
        self.column_width_hint: List[int] = []
        self.all_column_widths: List[Dict[ViewTable, int]] = []

        self.reference_plot: Optional[pg.ViewBox] = None
        self.min_plot_width = self.width()

        self.createMenus()

        self.initial_point = None

        self.RRregion = None
        

        self.statusBar()
        self.status('Ready')
        self.guiAddPanel()
        #self.evalTrackMenu()

        self.timer = QTimerWithPause(interval=PALMS.config['autoplay_timer_interval'])
        self.timer.timeout.connect(self.shiftRight)
        Viewer._instance = weakref.ref(self)()

    @staticmethod
    def get():
        return Viewer._instance if Viewer._instance is not None else None
    
    def createMenus(self):
        menu = self.menuBar()
        # to work around OSX bug that requires switching focus away from this
        # application, and the coming back to it, to make menu accessible this
        # is not necessary when started from the TimeView.app application icon
        if __debug__:  # I am beginning to think that I always want this
            menu.setNativeMenuBar(False)

        # File menu
        self.file_menu = menu.addMenu('&File')
        self.file_menu.setToolTipsVisible(True)

        self.file_menu.open_new_action = QtWidgets.QAction('&Open new', self, enabled=True)
        self.file_menu.open_new_action.setToolTip(tooltips.open_new)
        self.file_menu.open_new_action.triggered.connect(self.top_left_w.open_new_file)
        self.file_menu.addAction(self.file_menu.open_new_action)

        self.file_menu.save_action = QtWidgets.QAction('&Save', self, enabled=True)
        self.file_menu.save_action.setToolTip(tooltips.save)
        self.file_menu.save_action.triggered.connect(self.top_left_w.save_default)
        self.file_menu.addAction(self.file_menu.save_action)

        self.file_menu.save_as_action = QtWidgets.QAction('&Save as', self, enabled=True)
        self.file_menu.save_as_action.setToolTip(tooltips.save)
        self.file_menu.save_as_action.triggered.connect(self.top_left_w.save_file)
        self.file_menu.addAction(self.file_menu.save_as_action)

        # Results menu
        self.results_menu = menu.addMenu('&Export results')
        self.results_menu.setToolTipsVisible(True)

        self.results_menu.export_results = QtWidgets.QAction('&Export to new file', self, enabled=True)
        self.results_menu.export_results.setToolTip(tooltips.export_results)
        self.results_menu.export_results.triggered.connect(self.top_left_w.mainExportResults)
        self.results_menu.addAction(self.results_menu.export_results)

        self.results_menu.append_results = QtWidgets.QAction('&Append to existing file', self, enabled=True)
        self.results_menu.append_results.setToolTip(tooltips.append_results)
        self.results_menu.append_results.triggered.connect(self.top_left_w.append_results)
        self.results_menu.addAction(self.results_menu.append_results)

        # settings menu
        self.settings_menu = menu.addMenu('&Settings')
        self.settings_menu.open_settings_action = QtWidgets.QAction('Open settings', self, enabled=True)
        self.settings_menu.open_settings_action.triggered.connect(self.top_left_w.open_settings)
        self.settings_menu.addAction(self.settings_menu.open_settings_action)

        # help menu
        self.help_menu = menu.addMenu('&Help')
        self.help_menu.open_doc_action = QtWidgets.QAction('User manual', self, enabled=True)
        self.help_menu.open_doc_action.setToolTip(tooltips.open_doc)
        self.help_menu.open_doc_action.triggered.connect(self.top_left_w.open_doc)
        self.help_menu.addAction(self.help_menu.open_doc_action)

        self.help_menu.shortcut_action = QtWidgets.QAction('Shortcuts', self, enabled=True)
        self.help_menu.shortcut_action.setToolTip(tooltips.see_shortcuts)
        self.help_menu.shortcut_action.triggered.connect(self.open_shortcuts)
        self.help_menu.addAction(self.help_menu.shortcut_action)

        # ecg menu
        self.help_menu = menu.addMenu('&ECG options')
        self.help_menu.invert_signal_action = QtWidgets.QAction('Invert signal', self, enabled=True)
        self.help_menu.invert_signal_action.setToolTip(tooltips.invert_signal)
        self.help_menu.invert_signal_action.triggered.connect(self.invert_signal)
        self.help_menu.addAction(self.help_menu.invert_signal_action)

        self.help_menu.redetect_peaks_action = QtWidgets.QAction('Re-detect peaks', self, enabled=True)
        self.help_menu.redetect_peaks_action.setToolTip(tooltips.redetect_peaks)
        self.help_menu.redetect_peaks_action.triggered.connect(self.redetect_peaks)
        self.help_menu.addAction(self.help_menu.redetect_peaks_action)


    def invert_signal(self):
        
        db = Database.get()
        db.invert_signal()
        

        # redetect outliers
        use_threshold = (self.top_left_w.beat_threshold_level.currentIndex() != 0)
        use_algorithm = (self.top_left_w.algorithm_active == True)
        if use_threshold and use_algorithm:
            self.top_left_w.outlier_decision_central(False, True)
        elif use_threshold:
            self.top_left_w.outlier_decision_central(True, False)
        elif use_algorithm:
            self.top_left_w.outlier_decision_central(False, True)

        # reset graphs
        self.updateECGView()
        self.resetRRView()
        PALMS.get().updateRR()

    def redetect_peaks(self):
        db = Database.get()
        db.redetect_peaks()

        # redetect outliers
        use_threshold = (self.top_left_w.beat_threshold_level.currentIndex() != 0)
        use_algorithm = (self.top_left_w.algorithm_active == True)
        if use_threshold and use_algorithm:
            self.top_left_w.outlier_decision_central(False, True)
        elif use_threshold:
            self.top_left_w.outlier_decision_central(True, False)
        elif use_algorithm:
            self.top_left_w.outlier_decision_central(False, True)

        # reset graphs
        self.resetRRView()
        PALMS.get().updateRR()

    def open_shortcuts(self):
        from config import shortcuts
        settings_window = shortcuts.ShortcutsWindow()
        
        settings_window.show()

    @Slot(float, float)
    def plot_point(self, x, y):
        line = pg.InfiniteLine(pos=x, angle=90, movable=False)
        # self.temporary_items.append(line)
        self.addItem(line)

    @Slot(name='guiAddPanel')
    def guiAddPanel(self, pos: Optional[int] = None):
        """
        when adding a panel through the gui, this method determines
        where the panel should go, and handles the associated frame selection
        """
        if pos is None:
            if not self.frames:
                pos = 2 # 2 to skip 0 (outliers) and 1 (buttons)
            elif self.selected_frame:
                pos = self.frames.index(self.selected_frame) + 1
            else:
                pos = len(self.frames)
        if (pos==2):
            self.createNewOutliersPanel()
            self.createNewButtonPanel()
        self.createNewPanel(pos=pos)
        self.applySync()
        self.selectFrame(self.frames[pos])

    def toggle_resize_left(self):

        screen_rect = QApplication.instance().desktop().availableGeometry()
        width = screen_rect.width()*0.95
        height = screen_rect.height()*0.95
        

        if not self.resized_left:
            self.top_left_frame.setFixedSize(0, 0)
            if self.resized_down:
                self.scrollArea.setFixedSize(width, height)
                self.results_frame.setFixedSize(0,0)
            else:
                self.scrollArea.setFixedSize(width, height*0.6)
                self.results_frame.setFixedSize(width, height*0.35)
            
        else:
            if self.resized_down:
                self.top_left_frame.setFixedSize(width * 0.3, height)
                self.scrollArea.setFixedSize(width*0.7, height)
                self.results_frame.setFixedSize(0,0)
            else:
                self.top_left_frame.setFixedSize(width * 0.3, height*0.6)
                self.scrollArea.setFixedSize(width*0.7, height*0.6)
                self.results_frame.setFixedSize(width, height*0.35)

        self.resized_left = not self.resized_left

    def toggle_resize_down(self):

        screen_rect = QApplication.instance().desktop().availableGeometry()
        width = screen_rect.width()*0.95
        height = screen_rect.height()*0.95

        if not self.resized_down:
            if self.resized_left:
                self.top_left_frame.setFixedSize(0, 0)
                self.scrollArea.setFixedSize(width, height)
                self.results_frame.setFixedSize(0, 0)
            else:
                self.top_left_frame.setFixedSize(width*0.3, height)
                self.scrollArea.setFixedSize(width*0.7, height)
                self.results_frame.setFixedSize(0, 0)
        else:
            if self.resized_left:
                self.top_left_frame.setFixedSize(0, 0)
                self.scrollArea.setFixedSize(width, height*0.6)
                self.results_frame.setFixedSize(width, height*0.35)
            else:
                self.top_left_frame.setFixedSize(width*0.3, height*0.6)
                self.scrollArea.setFixedSize(width*0.7, height*0.6)
                self.results_frame.setFixedSize(width, height*0.35)

        self.resized_down = not self.resized_down
    

    def toggleAll_action(self):
        # TODO: it is here because when menus are created, there is no panel and selectedPanel yet
        # otherwise, can set callback directly to ...plot_area.hideAllViewsExceptMain()
        if self.selectedDisplayPanel is not None:
            self.selectedDisplayPanel.plot_area.toggleAllViewsExceptMain()

    def open_doc(self):
        try:
            from PyQt5.QtCore import QUrl
            ql = QtWidgets.QLabel('Help')
            path = resource_path(pathlib.Path('docs', 'user_manual.pdf'))
            url = bytearray(QUrl.fromLocalFile(path.as_posix()).toEncoded()).decode()
            text = "<a href={}>Reference Link> </a>".format(url)
            ql.setText(text)
            ql.setVisible(False)
            ql.setOpenExternalLinks(True)
            ql.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
            ql.linkActivated.emit('str')
            ql.move(0, 0)
            ql.show()
            mouseevent = QtGui.QMouseEvent(QtCore.QEvent.MouseButtonRelease, QtCore.QPoint(0, 0), QtCore.Qt.LeftButton,
                                           QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
            ql.mousePressEvent(mouseevent)
            ql.hide()
            del ql
        except Exception as e:
            Dialog().warningMessage('Something went wrong while opening the document.\n'
                                    'You can continue your work.\n'
                                    'The error was: '+ str(e))

    def restart_app(self):
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Restart...",
                                                "Do you want to save or overwrite and restart ?",
                                                QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Abort)
        if result == QtWidgets.QMessageBox.Save or result==QtWidgets.QMessageBox.Discard:
            db = Database.get()

            if result == QtWidgets.QMessageBox.Save:
                db.save()
                qInfo('{} saved'.format(db.fullpath.stem))

            PALMS.NEXT_FILE = None
            # PALMS.PREV_FILE = PALMS.CURRENT_FILE  # after reboot there is no previous file
            from logic.operation_mode.annotation import AnnotationConfig
            AnnotationConfig.get().clear()
            Partitions.delete_all()
            self.REBOOT_APP = True
            QtGui.QGuiApplication.exit(PALMS.EXIT_CODE_REBOOT)

    def restart_and_load(self, next_or_prev):
        db = Database.get()
        PALMS.NEXT_FILE = db.get_next_database_file()
        PALMS.PREV_FILE = db.get_prev_database_file()

        db.save()
        qInfo('{} saved'.format(db.fullpath.stem))
        #TODO: add QmessageBox about Save/Discard here and a tickbox option "Dont ask again"

        if next_or_prev in ['N', 'n', 'next', 'NEXT', 'Next']:
            if PALMS.NEXT_FILE is None:
                qInfo('Thi is the last file in the database.\n Try File->Restart or File->Load Prev')
                return
        elif next_or_prev in ['P', 'p', 'prev', 'PREV', 'Prev']:
            if PALMS.PREV_FILE is None:
                qInfo('Thi is the first file in the database.\n Try File->Restart or File->Load Next')
                return

        # don't clear data before certain that restart will happen
        from logic.operation_mode.annotation import AnnotationConfig
        AnnotationConfig.get().clear()
        Partitions.delete_all()
        self.REBOOT_APP = True
        if next_or_prev in ['N', 'n', 'next', 'NEXT', 'Next']:
            QtGui.QGuiApplication.exit(PALMS.EXIT_CODE_LOAD_NEXT)
        elif next_or_prev in ['P', 'p', 'prev', 'PREV', 'Prev']:
            QtGui.QGuiApplication.exit(PALMS.EXIT_CODE_LOAD_PREV)

    def raise_sticky_fiducial_popup(self):
        pos = self.selectedDisplayPanel.plot_area.event_cursor_global_position
        if pos is not None:
            sticky_fiducial = self.annotation_menu.sticky_fiducial_menu.exec_(pos)
        else:
            sticky_fiducial = self.annotation_menu.sticky_fiducial_menu.exec_()

    def toggle_sticky_fiducial_checkboxes(self):
        sender = self.sender()
        for ch in self.annotation_menu.sticky_fiducial_menu.actions():
            if ch.isChecked() and ch != sender:
                ch.setChecked(False)

    def toggle_mode(self, mode: Modes):  # annotation and partition modes can not be both ON, but can be both OFF
        self.selectedDisplayPanel.plot_area.redraw_fiducials()
        for item in self.annotation_menu.sticky_fiducial_menu.actions():
            item.setChecked(False)
        EpochModeConfig.get().redraw_epochs()
        
        if mode == Modes.annotation:
            self.annotation_menu.annotationMode_action.setChecked(True)
            self.annotation_menu.partitionMode_action.setChecked(False)
            self.annotation_menu.epochMode_action.setChecked(False)
            self.annotation_menu.browseMode_action.setChecked(False)
            Partitions.unhide_all_partitions()
            # Partitions.hide_all_partitions()
            self.annotation_menu.annotationConfig_action.setEnabled(True)
            self.annotation_menu.sticky_fiducial_menu.setEnabled(True)
            self.annotation_menu.partitionConfig_action.setEnabled(False)
            EpochWindow.hide()
        elif mode == Modes.partition:
            self.annotation_menu.annotationMode_action.setChecked(False)
            self.annotation_menu.partitionMode_action.setChecked(True)
            self.annotation_menu.epochMode_action.setChecked(False)
            self.annotation_menu.browseMode_action.setChecked(False)
            Partitions.unhide_all_partitions()
            self.annotation_menu.annotationConfig_action.setEnabled(False)
            self.annotation_menu.sticky_fiducial_menu.setEnabled(False)
            self.annotation_menu.partitionConfig_action.setEnabled(True)
            EpochWindow.hide()
        elif mode == Modes.noise_partition:
            self.annotation_menu.annotationMode_action.setChecked(False)
            self.annotation_menu.partitionMode_action.setChecked(True)
            self.annotation_menu.epochMode_action.setChecked(False)
            self.annotation_menu.browseMode_action.setChecked(False)
            NoisePartitions.unhide_all_partitions()
            self.annotation_menu.annotationConfig_action.setEnabled(False)
            self.annotation_menu.sticky_fiducial_menu.setEnabled(False)
            self.annotation_menu.partitionConfig_action.setEnabled(True)
            EpochWindow.hide()
        elif mode == Modes.browse:
            self.annotation_menu.annotationMode_action.setChecked(False)
            self.annotation_menu.partitionMode_action.setChecked(False)
            self.annotation_menu.epochMode_action.setChecked(False)
            self.annotation_menu.browseMode_action.setChecked(True)
            Partitions.unhide_all_partitions()
            self.annotation_menu.annotationConfig_action.setEnabled(False)
            self.annotation_menu.sticky_fiducial_menu.setEnabled(False)
            self.annotation_menu.partitionConfig_action.setEnabled(False)
            EpochWindow.hide()
        elif mode == Modes.epoch:
            self.annotation_menu.annotationMode_action.setChecked(False)
            self.annotation_menu.partitionMode_action.setChecked(False)
            self.annotation_menu.epochMode_action.setChecked(True)
            self.annotation_menu.browseMode_action.setChecked(False)
            Partitions.hide_all_partitions()
            self.annotation_menu.annotationConfig_action.setEnabled(False)
            self.annotation_menu.sticky_fiducial_menu.setEnabled(False)
            self.annotation_menu.partitionConfig_action.setEnabled(False)
            x_min, x_max = PlotArea.get_main_view().renderer.vb.viewRange()[0]
            EpochWindow.move_current_window_to_x(x_min)
            PlotArea.get_main_view().renderer.plot_area.setFocus()
            # TODO: reset plot to window + overlap

    def load_from_hdf5(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load hdf5 with annotations", get_project_root().as_posix(), " (*.h5);",
                                                      options=QtWidgets.QFileDialog.Options())
        if fn:
            Database.get().load(fn)
        else:
            qInfo('Load canceled')

    def toggleAutoscaleY(self):
        self.autoscale_y = not self.autoscale_y
        self.autoscaleYstatus.emit(self.autoscale_y)

    def toggleRewriteH5(self):
        self.rewriteH5 = not self.rewriteH5
        self.rewriteH5Status.emit(self.rewriteH5)

    def toggleCursorReadout(self):
        self.cursor_readout = not self.cursor_readout
        self.cursorReadoutStatus.emit(self.cursor_readout)

    def getOutliersDisplayPanel(self) -> OutliersPanel:
        selected_index = 0
        return self.frames[selected_index].outliersPanel # 2 to skip 0 (outliers) and 1 (buttons)
    
    def getButtonsDisplayPanel(self) -> ButtonPanel:
        selected_index = 1
        return self.frames[selected_index].buttonPanel # 2 to skip 0 (outliers) and 1 (buttons)

    def getSelectedDisplayPanel(self) -> DisplayPanel:
        selected_index = self.model.panels.index(self.model.selected_panel)
        return self.frames[selected_index+2].displayPanel # 2 to skip 0 (outliers) and 1 (buttons)
    
    def getRRDisplayPanel(self) -> DisplayPanel:
        if PALMS.get().RR_ONLY:
            selected_index = 1
            return self.frames[-1].displayPanel
        else:
            selected_index = 1
            return self.frames[-1].displayPanel # 2 to skip 0 (outliers) and 1 (buttons)

    outliersDisplayPanel = property(getOutliersDisplayPanel)

    buttonsDisplayPanel = property(getButtonsDisplayPanel)

    selectedDisplayPanel = property(getSelectedDisplayPanel)

    RRDisplayPanel = property(getRRDisplayPanel)

    def getSelectedTrack(self) -> tracking.Track:
        panel = self.selectedPanel
        track = panel.selected_track()
        return track

    selectedTrack = property(getSelectedTrack)

    def getSelectedView(self) -> View:
        return self.selectedPanel.selected_view

    selectedView = property(getSelectedView)

    def viewRange(self, display_panel=None) -> Tuple[float, float]:
        if display_panel is None:
            display_panel = self.selectedDisplayPanel
            if display_panel is None:
                return 0., 1.
        view = display_panel.panel.selected_view
        if view is None:
            vb = display_panel.plot_area.main_vb
        else:
            vb = view.renderer.vb
        return vb.viewRange()[0]

    # TODO: when shifting by menu / keys, implement a *target* system,
    # where we are smoothly and exponentially scrolling to the desired target
    @Slot(name='pageRight')
    def pageRight(self):
        span = np.diff(self.viewRange())[0]
        self.translateBy(span)

    def translateBy(self, delta_x):
        # using multiple panels can cause unexpected behaviour, to avoid, we always switch to the panel with the main track
        for frame in self.frames[2:]:
            if frame.displayPanel.plot_area.is_main_view_in_current_panel():
                break
        self.selectFrame(frame)

        view = self.selectedView
        if view is None:
            return
        x_min, x_max = view.renderer.vb.viewRange()[0]
        if x_min < 0 and delta_x < 0:
            return
        self.applySync()
        view.renderer.vb.translateBy(x=delta_x)
        self.selectedDisplayPanel.plot_area.alignViews()
        if self.synchronized:
            reference_view_range = self.reference_plot.viewRange()[0]
            for frame in self.frames[2:]:
                frame_view_range = frame.displayPanel.plot_area.main_vb.viewRange()[0]  # assert reference_view_range == frame_view_range

    def scaleBy(self, mag_x):
        view = self.selectedView
        if view is None:
            return
        self.applySync()
        center = view.renderer.vb.targetRect().center()
        padding = view.renderer.vb.suggestPadding(pg.ViewBox.XAxis)
        proposed_ranges = [dim * mag_x for dim in view.renderer.vb.viewRange()[0]]
        if proposed_ranges[0] < -padding:
            shift_right = abs(proposed_ranges[0]) - padding
            center.setX(center.x() + shift_right)
        view.renderer.vb.scaleBy(x=mag_x, center=center)
        self.selectedDisplayPanel.plot_area.alignViews()
        # if self.synchronized:
        #     reference_view_range = self.reference_plot.viewRange()[0]
        #     try:
        #         assert all([reference_view_range == frame.displayPanel.plot_area.main_vb.viewRange()[0] for frame in self.frames])
        #     except Exception as e:
        #         if len(self.frames) > 1:
        #             Dialog().warningMessage('Exception occured\n'
        #                                     'Using more than one frame may have caused this!\n'
        #                                     'The error was: '+ str(e))
        #         else:
        #             Dialog().warningMessage('Exception occured\n' + str(e))
        

    def getSelectedPanel(self) -> Panel:
        return self.model.selected_panel

    def setSelectedPanel(self, panel: Panel):
        self.model.set_selected_panel(panel)

    selectedPanel = property(getSelectedPanel, setSelectedPanel)

    @Slot(name='pageLeft')
    def pageLeft(self):
        span = np.diff(self.viewRange())[0]
        self.translateBy(-span)

    @Slot(name='shiftRight')
    def shiftRight(self):
        if Mode.is_epoch_mode() and not EpochWindow.get().is_out_of_scope():
            EpochWindow.move_right()
        else:
            if self.selectedView is None:
                return
            x_min, x_max = self.viewRange()
            span = np.diff(self.viewRange())[0]
            if x_max > self.selectedView.panel.get_max_duration():
                return
            shift = span / 10
            self.translateBy(shift)

    @Slot(name='play_pause')
    def play_pause(self):
        if self.timer.isActive():
            self.timer.pause()
        else:
            self.timer.resume()

    @Slot(name='shiftLeft')
    def shiftLeft(self):
        if Mode.is_epoch_mode() and not EpochWindow.get().is_out_of_scope():
            EpochWindow.move_left()
        else:
            if self.selectedView is None:
                return
            vb = self.selectedPanel.selected_view.renderer.vb
            x_min, x_max = vb.viewRange()[0]
            padding = vb.suggestPadding(pg.ViewBox.XAxis)
            span = x_max - x_min
            shift = span / 10
            if x_min < 0:
                return
            elif x_min - shift < -padding:
                shift = max(x_min, padding)
            self.translateBy(-shift)

    @Slot(name='goToBeginning')
    def goToBeginning(self):
        x_min, x_max = self.viewRange()
        padding = self.selectedPanel.selected_view.renderer.vb.suggestPadding(1)
        self.translateBy(-x_min - padding)

    @Slot(name='goToEnd')
    def goToEnd(self):
        x_min, x_max = self.viewRange()
        view = self.selectedView
        if view is None:
            return
        track = view.track
        end_time = view.track.duration / view.track.fs
        self.translateBy(end_time - x_max)

    @Slot(name='zoomFit')
    def zoomFit(self):
        view = self.selectedView
        if view is None:
            return
        track = view.track
        max_t = track.duration / track.fs
        span = np.diff(view.renderer.vb.viewRange()[0])[0]
        self.scaleBy(max_t / span)
        self.goToBeginning()

    @Slot(name='zoomToMatch')
    def zoomToMatch(self):
        """
        where each pixel represents exactly one sample at the
        highest-available sampling-frequency
        :return:
        """
        view = self.selectedPanel.selected_view
        if view is None:
            return
        vb = view.renderer.vb
        pixels = vb.screenGeometry().width()
        mag_span = pixels / self.selectedTrack.fs
        span = np.diff(self.viewRange())[0]
        mag = mag_span / span
        self.scaleBy(mag)

    @Slot(name='zoomIn')
    def zoomIn(self):
        """
        In AnnotationMode and PartitionMode: Up and Down execute regular zoom operation
        In EpochMode: Up and Down make label change to next\prev, zoom can be done only by MouseWheel
        :return:
        """
        if Mode.is_epoch_mode() and not EpochWindow.get().is_out_of_scope():
            EpochModeConfig.get().current_window_upgrade_value()
        else:
            view = self.selectedPanel.selected_view
            if view is None:
                return
            vb = view.renderer.vb
            x_range = np.diff(vb.viewRange()[0])[0]
            minXRange = vb.getState()['limits']['xRange'][0]
            zoom = 0.9

            if x_range <= minXRange:
                return
            elif x_range * zoom < minXRange:
                zoom = minXRange / x_range
            self.scaleBy(zoom)
        self.RRDisplayPanel.plot_area.alignViews()

    @Slot(name='zoomOut')
    def zoomOut(self):
        if Mode.is_epoch_mode() and not EpochWindow.get().is_out_of_scope():
            EpochModeConfig.get().current_window_downgrade_value()
        else:
            view = self.selectedPanel.selected_view
            if view is None:
                return
            vb = view.renderer.vb
            x_range = np.diff(vb.viewRange()[0])
            maxXRange = vb.getState()['limits']['xLimits'][1] - vb.getState()['limits']['xLimits'][0]
            zoom = 1.1

            if x_range >= maxXRange:
                return
            elif x_range * zoom > maxXRange:
                zoom = maxXRange / x_range
            self.scaleBy(zoom)
        self.RRDisplayPanel.plot_area.alignViews()

    @Slot(name='increaseSize')
    def increaseSize(self):
        self.selected_frame.increaseSize()

    @Slot(name='decreaseSize')
    def decreaseSize(self):
        self.selected_frame.decreaseSize()

    def status(self, msg: str, timeout: int = 5000):
        self.statusBar().showMessage(msg, timeout)

    def joinGroup(self, view):
        group = self.groups[id(view.track)]
        group.join(view)

    def changeSync(self):
        self.synchronized = not self.synchronized
        self.reference_plot = self.selectedDisplayPanel.plot_area.main_vb
        self.applySync()

    def applySync(self):
        if self.synchronized:
            self.synchronize()
        else:
            self.desynchronize()
        self.selectedDisplayPanel.plot_area.redraw_fiducials()

    def synchronize(self):
        self.reference_plot = self.selectedDisplayPanel.plot_area.main_vb
        assert isinstance(self.reference_plot, pg.ViewBox)
        x_min, x_max = self.reference_plot.viewRange()[0]
        for frame in self.frames[2:]: # 2 to skip 0 (outliers) and 1 (buttons)
            if frame.displayPanel.plot_area.main_vb is self.reference_plot:
                continue
            frame.displayPanel.plot_area.main_vb.setXLink(self.reference_plot)
            if frame.displayPanel.panel.selected_view:
                frame.displayPanel.panel.selected_view.renderer.vb.setXRange(x_min, x_max, padding=0)

    def desynchronize(self):
        self.reference_plot = None
        for frame in self.frames[2:]:
            frame.displayPanel.plot_area.main_vb.setXLink(frame.displayPanel.plot_area.main_vb)

    def toggleXAxis(self):
        PALMS.config['show_xaxis_label'] = not PALMS.config['show_xaxis_label']
        for frame in self.frames[2:]:
            frame.displayPanel.plot_area.axis_bottom.showLabel(PALMS.config['show_xaxis_label'])

    def createNewPanel(self, pos=None):
        from gui import PALMS
        frame = Frame(main_window=self)
        w = DisplayPanel(frame=frame)
        w.plot_area.setAxesWidths(self.axis_width)
        try:
            self.queryAxesWidths.connect(w.plot_area.updateWidestAxis)
            self.setAxesWidth.connect(w.plot_area.setAxesWidths)
            self.moveSplitterPosition.connect(w.setSplitterPosition)
        except TypeError:
            pass

        #self.setSplitter.connect(w.table_splitter.setSizes_)
        #self.setColWidths.connect(w.view_table.setColumnWidths)
        #self.queryColWidths.connect(w.view_table.calcColumnWidths)
        
        #w.table_splitter.setSizes([1, w.view_table.viewportSizeHint().width()])
        frame.layout.addWidget(w)
        frame.displayPanel = w
        if pos is not None:
            insert_index = pos
        elif self.selected_frame:
            insert_index = self.frames.index(self.selected_frame) + 1
        else:
            insert_index = None
        panel = self.model.new_panel(pos=insert_index)
        w.loadPanel(panel)
        self.addFrame(frame, insert_index+1)
        
        # range slider
        if (pos == 2 and PALMS.get().RR_ONLY == False): # 2 to skip 0 (outliers) and 1 (buttons)
            self.range_slider_ECG = QScrollBar()
            self.range_slider_ECG.setOrientation(Qt.Horizontal)
            self.range_slider_ECG.setFixedHeight(20)
            #self.range_slider_ECG.setMinimum(0)
            #self.range_slider_ECG.setMaximum(100)s
            # These values (0,1) represent the total size of the scroll bar. The current value and step is always decimal
            
            #frame.displayPanel.plot_area.main_plot.setXRange(*self.range_slider_ECG.sliderPosition())
            
        
            frame.layout.addWidget(self.range_slider_ECG)

            #self.range_slider_ECG.setSliderPosition([0,1])

        else:
            self.range_slider_RR = QScrollBar()
            self.range_slider_RR.setOrientation(Qt.Horizontal)
            self.range_slider_RR.setFixedHeight(20)
            #self.second_range_slider_RR = QScrollBar()
            #self.second_range_slider_RR.setOrientation(Qt.Horizontal)
            #self.second_range_slider_RR.setFixedHeight(20)
            #self.range_slider_RR.setMinimum(0)
            #self.range_slider_RR.setMaximum(100)
            #frame.displayPanel.plot_area.main_plot.setXRange(*self.range_slider_RR.sliderPosition())

            # Add connection signals 
            if PALMS.get().RR_ONLY is False:
                self.range_slider_ECG.valueChanged.connect(self.on_range_slider_ECG_changed)

                self.frames[2].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.connect(self.on_zoom_ECG_changed)

                self.range_slider_RR.valueChanged.connect(self.on_range_slider_RR_changed)

                self.range_slider_RR.sliderPressed.connect(self.slider_pressed)
            
                self.frames[3].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.connect(self.on_zoom_RR_changed)
        
                frame.layout.addWidget(self.range_slider_RR)
            else:
                self.frames[2].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.connect(self.on_zoom_RR_changed)

                self.range_slider_RR.valueChanged.connect(self.on_range_slider_RR_changed)

                frame.layout.addWidget(self.range_slider_RR)
            
        self.applySync()

    def slider_pressed(self):
        print("slider pressed")

    def synchronize_graphs(self):
        # Make RR same interval as ECG
        slider_value = self.frames[2].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][0]
        self.range_slider_RR.setValue(slider_value)
        self.frames[3].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.range_slider_ECG.value(), (self.range_slider_ECG.value()+self.range_slider_ECG.pageStep()))
        

        # variable to true
        self.synchronized = True
        self.applySync()
        
        self.RRDisplayPanel.plot_area.main_vb.removeItem(self.RRregion)
        self.RRregion = None

    def desynchronize_graphs(self):
        # variable to false
        self.synchronized = False
        self.applySync()

        self.minStart = self.frames[3].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][0]
        self.maxEnd = self.frames[3].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][1]


    def on_range_slider_ECG_changed(self):
        try:
            self.frames[2].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.disconnect(self.on_zoom_ECG_changed)
        except TypeError:
            pass
        try:
            self.frames[3].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.disconnect(self.on_zoom_RR_changed)
        except TypeError:
            pass
        try:
            self.range_slider_RR.valueChanged.disconnect(self.on_range_slider_RR_changed)
        except TypeError:
            pass
        self.frames[2].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.range_slider_ECG.value(), (self.range_slider_ECG.value()+self.range_slider_ECG.pageStep()))
        
        if (self.synchronized == True):
            self.range_slider_RR.setValue(self.range_slider_ECG.value())
        # If the ECG goes earlier than the current RR position, also expand RR
        #if (self.synchronized == False):
        #    if (self.minStart > self.frames[1].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][0]):
        #        self.frames[2].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.range_slider_ECG.sliderPosition()[0], self.frames[2].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][1])
            # Also if it goes later
            #if (self.maxEnd < self.frames[1].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][1]):
            #    self.frames[2].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.frames[2].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][0], self.range_slider_ECG.sliderPosition()[1])
        try:
            self.frames[2].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.connect(self.on_zoom_ECG_changed)
        except TypeError:
            pass
        try:
            self.frames[3].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.connect(self.on_zoom_RR_changed)
        except TypeError:
            pass
        try:
            self.range_slider_RR.valueChanged.connect(self.on_range_slider_RR_changed)
        except TypeError:
            pass
        self.updateHighlighted()


    def on_range_slider_RR_changed(self):
        try:
            if PALMS.get().RR_ONLY is False:
                self.frames[2].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.disconnect(self.on_zoom_ECG_changed)
        except TypeError:
            pass
        try:
            if PALMS.get().RR_ONLY is False:
                self.frames[3].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.disconnect(self.on_zoom_RR_changed)
            else:
                self.frames[2].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.disconnect(self.on_zoom_RR_changed)
        except TypeError:
            pass
        try:
            if PALMS.get().RR_ONLY is False:
                self.range_slider_ECG.valueChanged.disconnect(self.on_range_slider_ECG_changed)
        except TypeError:
            pass
        
        if PALMS.get().RR_ONLY is False:
            self.frames[3].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.range_slider_RR.value(), (self.range_slider_RR.value()+self.range_slider_RR.pageStep()))
            if (self.synchronized == True):
                self.range_slider_ECG.setValue(self.range_slider_RR.value())
        else:
            self.frames[2].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.range_slider_RR.value(), (self.range_slider_RR.value()+self.range_slider_RR.pageStep()))
        
        try:
            if PALMS.get().RR_ONLY is False:
                self.frames[2].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.connect(self.on_zoom_ECG_changed)
        except TypeError:
            pass
        try:
            if PALMS.get().RR_ONLY is False:
                self.frames[3].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.connect(self.on_zoom_RR_changed)
            else:
                self.frames[2].displayPanel.plot_area.main_plot.getViewBox().sigRangeChanged.connect(self.on_zoom_RR_changed)
        except TypeError:
            pass
        try:
            if PALMS.get().RR_ONLY is False:
                self.range_slider_ECG.valueChanged.connect(self.on_range_slider_ECG_changed)
        except TypeError:
            pass
        self.updateHighlighted()
        

    def on_zoom_ECG_changed(self):
        try:
            self.range_slider_ECG.valueChanged.disconnect(self.on_range_slider_ECG_changed)
        except TypeError:
            pass
        try:
            self.range_slider_RR.valueChanged.disconnect(self.on_range_slider_RR_changed)
        except TypeError:
            pass

        try:
            current_xmin, current_xmax = self.frames[2].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0]
            page_step = (current_xmax-current_xmin)
            if self.initial_point is not None:
                self.range_slider_ECG.setMaximum(int(self.initial_point[1])-page_step)
                self.range_slider_ECG.setValue(current_xmin)
                self.range_slider_ECG.setPageStep(page_step)
        except TypeError:
            print("error in slider")
            

        # If the ECG goes earlier than the current RR position, also expand RR
        #if (self.synchronized == False):
        #    if (self.minStart > self.frames[1].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][0]):
        #        self.frames[2].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.range_slider_ECG.sliderPosition()[0], self.frames[2].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][1])
            # Also if it goes later
        #    if (self.maxEnd < self.frames[1].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][1]):
        #        self.frames[2].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.frames[2].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][0], self.range_slider_ECG.sliderPosition()[0])
        try:
            self.range_slider_ECG.valueChanged.connect(self.on_range_slider_ECG_changed)
        except TypeError:
            pass
        try:
            self.range_slider_RR.valueChanged.connect(self.on_range_slider_RR_changed)
        except TypeError:
            pass
        self.updateHighlighted()
        

    def on_zoom_RR_changed(self):
        try:
            if PALMS.get().RR_ONLY is False:
                self.range_slider_ECG.valueChanged.disconnect(self.on_range_slider_ECG_changed)
        except TypeError:
            pass
        try:
            self.range_slider_RR.valueChanged.disconnect(self.on_range_slider_RR_changed)
        except TypeError:
            pass

        try: 
            if PALMS.get().RR_ONLY is False:
                current_xmin, current_xmax = self.frames[3].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0]
            else:
                current_xmin, current_xmax = self.frames[2].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0]
            page_step = (current_xmax-current_xmin)
            if self.initial_point is not None:
                self.range_slider_RR.setMaximum(self.initial_point[1]-page_step)
                self.range_slider_RR.setValue(current_xmin)
                self.range_slider_RR.setPageStep(page_step)
        except TypeError:
            print("error in slider")
            

        # If the RR goes higher than minStart, update RR start to it
        #if (self.synchronized == False):
        #    if (self.minStart < self.frames[2].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][0]):
        #        self.frames[1].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.range_slider_RR.sliderPosition()[0], self.frames[1].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][1])
            # Also for later
        #    if (self.maxEnd > self.frames[2].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][1]):
        #        self.frames[1].displayPanel.plot_area.main_plot.getViewBox().setXRange(self.frames[1].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][0], self.range_slider_RR.sliderPosition()[1])
        try:
            if PALMS.get().RR_ONLY is False:
                self.range_slider_ECG.valueChanged.connect(self.on_range_slider_ECG_changed)
        except TypeError:
            pass
        try:
            self.range_slider_RR.valueChanged.connect(self.on_range_slider_RR_changed)
        except TypeError:
            pass
        self.updateHighlighted()

        
    def updateHighlighted(self):
        
        if (self.synchronized == False and PALMS.get().RR_ONLY is False):

            # Get RR graph dimensions and compare to ECG to see if needed a highlighted interval
            x_min, x_max = self.selectedDisplayPanel.plot_area.main_vb.viewRange()[0]
            x_min_rr, x_max_rr = self.RRDisplayPanel.plot_area.main_vb.viewRange()[0]
            
            if (x_min_rr < x_min and x_max_rr > x_max):
                
                if (self.RRregion == None):
                    self.RRregion = pg.LinearRegionItem()
                    color = QColor(192, 192, 192) # grey
                    brush = QBrush(color)
                    self.RRregion.setBrush(brush)
                    self.RRDisplayPanel.plot_area.main_vb.addItem(self.RRregion)
                
                if (x_min < (self.initial_point[0] + self.initial_point[1]/100) and x_min > (self.initial_point[0] - self.initial_point[1]/100) and x_max < (self.initial_point[1] + self.initial_point[1]/100) and x_max > (self.initial_point[1] - self.initial_point[1]/100)):
                    self.RRregion.setRegion([x_min_rr, x_max_rr])
                    
                elif (x_min < (self.initial_point[0] + self.initial_point[1]/100) and x_min > (self.initial_point[0] - self.initial_point[1]/100)):
                    self.RRregion.setRegion([x_min_rr, x_max])
                    
                elif (x_max < (self.initial_point[1] + self.initial_point[1]/100) and x_max > (self.initial_point[1] - self.initial_point[1]/100)):
                    self.RRregion.setRegion([x_min, x_max_rr])
                    
                else:
                    self.RRregion.setRegion([x_min, x_max])
                
            elif (x_min_rr > x_min and self.RRregion is not None):
                self.RRregion.setRegion([x_min_rr, x_max])
            elif (x_max_rr < x_max and self.RRregion is not None):
                self.RRregion.setRegion([x_min, x_max_rr])

            # Update limits
            self.minStart = self.frames[3].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][0]
            self.maxEnd = self.frames[3].displayPanel.plot_area.main_plot.getViewBox().viewRange()[0][1]

    def createNewButtonPanel(self):
        
        frame = ButtonFrame(main_window=self)
        w = ButtonPanel(frame=frame)

        frame.layout.addWidget(w)
        frame.buttonPanel = w

        self.addFrame(frame, 1)

    def createNewOutliersPanel(self):
        
        frame = OutliersFrame(main_window=self)
        w = OutliersPanel(frame=frame)

        frame.layout.addWidget(w)
        frame.outliersPanel = w

        self.addFrame(frame, 0)


    def delItem(self):
        if self.selected_frame is None:
            logging.debug('no frame is selected for debug')
            return
        remove_index = self.frames.index(self.selected_frame)+1
        #self.model.panels.pop()
        #self.frames.pop()
        
        self.model.remove_panel(1)
        self.removeFrame(self.frames[3])
        #if not self.frames:
        #    self.selected_frame = None
        #    self.reference_plot = None
        #    self.guiAddPanel()
        #    self.selectFrame(self.frames[-1])
        #elif remove_index == len(self.frames):
        #    self.selectFrame(self.frames[-1])
        #else:
        #    self.selectFrame(self.frames[remove_index])
        self.applySync()

        


    @Slot(int, name='viewMoved')
    def viewMoved(self, panel_index):
        view_to_add = self.model.panels[panel_index].views[-1]
        self.frames[panel_index].displayPanel.view_table.addView(view_to_add, setColor=False)

    def addFrame(self, frame: Frame, index=None):
        if not index:
            index = len(self.frames)
        self.frames.insert(index, frame)
        #self.scrollAreaWidgetContents.layout.insertWidget(index, frame)
        if (index == 0 or index == 1):
            self.scrollAreaWidgetContents.layout.addWidget(frame, 1)
        else: 
            self.scrollAreaWidgetContents.layout.addWidget(frame, 4)
        self.updateFrames()

    def removeFrame(self, frame_to_remove: Frame):
        if frame_to_remove.displayPanel.plot_area.main_vb is self.reference_plot:
            self.reference_plot = None
        self.frames.remove(frame_to_remove)
        self.scrollAreaWidgetContents.layout.removeWidget(frame_to_remove)
        frame_to_remove.deleteLater()
        self.updateFrames()

    def updateFrames(self):
        self.scrollArea.updateGeometry()
        for panel, frame in zip(self.model.panels[0:], self.frames[2:]):
            #frame.displayPanel.handle.updateLabel()
            assert frame.displayPanel.panel == panel

    def swapFrames(self, positions: Tuple[int, int]):
        self.scrollAreaWidgetContents.swapWidgets(positions)
        self.frames[positions[0]], self.frames[positions[1]] = self.frames[positions[1]], self.frames[positions[0]]
        self.model.panels[positions[0]], self.model.panels[positions[1]] = self.model.panels[positions[1]], self.model.panels[positions[0]]
        self.updateFrames()

    @Slot(list, name='determineColumnWidths')
    def determineColumnWidths(self, widths: List[int]):
        if not self.all_column_widths:
            self.all_column_widths = [{self.sender(): width} for width in widths]
        else:
            for index, width in enumerate(widths):
                self.all_column_widths[index][self.sender()] = width

        self.column_width_hint = [max(column.values()) for column in self.all_column_widths]
        self.setColWidths.emit(self.column_width_hint)
        self.moveSplitterPosition.emit()

    @Slot(name='moveUp')
    def moveUp(self):
        index = self.frames.index(self.selected_frame)
        if index == 0:
            return
        self.swapFrames((index, index - 1))

    @Slot(name='moveDown')
    def moveDown(self):
        index = self.frames.index(self.selected_frame)
        if index == len(self.frames) - 1:
            return
        self.swapFrames((index, index + 1))

    @Slot(name='selectNext')
    def selectNext(self):
        index = self.frames.index(self.selected_frame)
        if index == len(self.frames) - 1:
            return
        else:
            self.selectFrame(self.frames[index + 1])

    @Slot(name='selectPrevious')
    def selectPrevious(self):
        index = self.frames.index(self.selected_frame)
        if index == 0:
            return
        else:
            self.selectFrame(self.frames[index - 1])

    @Slot(QtWidgets.QFrame, name='selectFrame')
    def selectFrame(self, frame_to_select: Frame):
        assert isinstance(frame_to_select, Frame)
        assert frame_to_select in self.frames
        if self.selected_frame is not None:
            self.selected_frame.resetStyle()
        self.selected_frame = frame_to_select
        self.selected_frame.setFocus(QtCore.Qt.ShortcutFocusReason)
        self.selected_frame.setStyleSheet("""
        Frame {
            border: 3px solid red;
        }
        """)
        index = self.frames.index(self.selected_frame)
        self.model.set_selected_panel(self.model.panels[index-2]) # 2 to skip 0 (outliers) and 1 (buttons)
        if self.synchronized and self.reference_plot is None:
            self.reference_plot = self.selectedDisplayPanel.plot_area.main_vb
        #self.evalTrackMenu()
        selected_frame_index = self.frames.index(frame_to_select)
        selected_panel_index = self.model.panels.index(self.selectedPanel)
        assert selected_frame_index == selected_panel_index+2 # 2 to skip 0 (outliers) and 1 (buttons)

    @Slot(QtWidgets.QFrame, name='frameToMove')
    def frameToMove(self, frame_to_move: Frame):
        self.from_index = self.frames.index(frame_to_move)

    @Slot(QtWidgets.QFrame, name='whereToInsert')
    def whereToInsert(self, insert_here: Frame):
        #self.to_index = self.frames.index(insert_here)
        #if self.to_index == self.from_index:
        #    self.from_index = self.to_index = None
        #    return
        #self.moveFrame()
        pass

    def moveFrame(self):
        if self.to_index is None or self.from_index is None:
            logging.debug('To and/or From index not set properly')
            return
        frame = self.frames[self.from_index]
        self.scrollAreaWidgetContents.layout.removeWidget(frame)
        self.frames.insert(self.to_index, self.frames.pop(self.from_index))
        self.model.move_panel(self.to_index, self.from_index)
        self.scrollAreaWidgetContents.layout.insertWidget(self.to_index, frame)
        self.selectFrame(self.frames[self.to_index])
        self.updateFrames()
        # Resetting moving parameters
        self.from_index = self.to_index = None

    @Slot(name='moveToEnd')
    def moveToEnd(self):
        self.frameToMove(self.selected_frame)
        self.to_index = len(self.frames) - 1
        self.moveFrame()

    @Slot(name='checkAxesWidths')
    def checkAxesWidths(self):
        widths = [axis.preferredWidth() for frame in self.frames[2:] for axis in frame.displayPanel.plot_area.axes.values()]
        if not widths:
            return
        axis_width = max(widths)
        if axis_width != self.axis_width:
            self.axis_width = axis_width
            self.setAxesWidth.emit(self.axis_width)

    @Slot(name='invertView')
    def invertViewView(self):
        #NB: not implemented
        """ invert the track, the view, annotations' Y-data, limits, etc."""
        if self.selectedView is None:
            return
        try:
            return
            self.selectedView.track.invert()
        except Exception as e:
            Dialog().warningMessage('Inverting signal failed\n' + str(e))


    @Slot(name='guiDelView')
    def guiDelView(self):
        """identifies the selected view and removes it"""
        if self.selectedView is None:
            return
        #if self.selectedView.track.label is Database.get().main_track_label:
        #    Dialog().warningMessage('It is not possible to delete the main ({}) track'.format(Database.get().main_track_label))
        #    return
        view_to_remove = self.RRDisplayPanel.panel.views[-1]
        self.RRDisplayPanel.removeViewFromChildren(view_to_remove)
        self.RRDisplayPanel.delViewFromModel(view_to_remove)
        #self.evalTrackMenu()
        AnnotationConfigDialog.get().reset_pinned_to_options_to_existing_views()

    @Slot(name='updateECGView')
    def updateECGView(self):
        if self.selectedView is None:
            return
        try:
            view_to_remove = self.selectedDisplayPanel.panel.views[-1]
        except:
            return
        if view_to_remove is None:
            return
        self.selectedDisplayPanel.removeViewFromChildren(view_to_remove)
        self.selectedDisplayPanel.delViewFromModel(view_to_remove)

        # add new ecg
        db = Database.get()
        PALMS.get().add_view_from_track(db.tracks[db.main_track_label], 0)

        AnnotationConfigDialog.get().reset_pinned_to_options_to_existing_views()

    @Slot(name='resetRRView')
    def resetRRView(self):
        if self.selectedView is None:
            return
        try:
            view_to_remove = self.RRDisplayPanel.panel.views[-1]
        except:
            return
        if view_to_remove is None:
            return
        
        self.RRDisplayPanel.removeViewFromChildren(view_to_remove)
        self.RRDisplayPanel.delViewFromModel(view_to_remove)
        try:
            view_to_remove = self.RRDisplayPanel.panel.views[-1]
        except:
            return
        if view_to_remove is None:
            return
        
        self.RRDisplayPanel.removeViewFromChildren(view_to_remove)
        self.RRDisplayPanel.delViewFromModel(view_to_remove)
        self.fiducials, self.rr_intervals = Annotation.get().create_RRinterval_track()
        # fiducials is the interpolated signal to plot, rr_intervals is all 0s except for the rr values
        PALMS.get().add_view_from_track(self.fiducials, 1) # add RR graph


    def setTrackMenuStatus(self, enabled):
        ignore_actions = ["New Partition", "Open"]  # TODO: hate this...
        for action in self.track_menu.actions():
            if any([ignore_str in action.text() for ignore_str in ignore_actions]):
                continue
            else:
                action.setEnabled(enabled)

    def evalTrackMenu(self):
        self.setTrackMenuStatus(bool(self.selectedPanel.views))

    def closeEvent(self, event):
        if not self.REBOOT_APP:  # the app is restarting, thus a dialog already appeared
            from PyQt5.QtWidgets import QFileDialog

            result = QtWidgets.QMessageBox.question(self,
                                                "Close program",
                                                "Do you want to save the current file before closing ?",
                                                QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Abort)
            
        else:
            result = QtWidgets.QMessageBox.Discard

        event.ignore()

        if result == QtWidgets.QMessageBox.Save:
            self.top_left_w.save_default()
            self.annotationConfig.close()
            self.help_popup.close()
            self.processorConfig.close()
            event.accept()

        elif result == QtWidgets.QMessageBox.Discard:
            self.annotationConfig.close()
            self.help_popup.close()
            self.processorConfig.close()
            event.accept()


class PALMS(object):  # Application - here's still the best place for it methinks
    EXIT_CODE_REBOOT = -123
    EXIT_CODE_LOAD_NEXT = 1
    EXIT_CODE_LOAD_PREV = -1
    PREV_FILE = None
    continue_value = False
    # Things that will be set when importing data
    CURRENT_FILE = None
    ECG_DATA = None
    original_annotations = np.array([])
    RR_ONLY = False
    FREQUENCY = None
    TIME_DATA = None
    #BEAT_DETECTION = 0
    START_INDEXES = np.array([], dtype="int32")
    END_INDEXES = np.array([], dtype="int32")
    START_MISSING_INDEXES = np.array([], dtype="int32")
    END_MISSING_INDEXES = np.array([], dtype="int32")
    START_ECG_INDEXES = np.array([], dtype="int32")
    END_ECG_INDEXES = np.array([], dtype="int32")
    FIRST_DATETIME = None
    LAST_DATETIME = None
    ORIGINAL_DATETIME = None
    algorithm_outliers = {}
    algorithm_outliers["interpolate"] = np.array([], dtype="int32")
    algorithm_outliers["add"] = np.array([], dtype="int32")
    algorithm_outliers["delete"] = np.array([], dtype="int32")
    threshold_outliers = np.array([], dtype="int32")
    INTERPOLATIONS = np.array([])
    fiducials = None
    rr_intervals = None
    original_rr = None
    original_fiducials = None
    DATA_TYPE = None # 0 for ECG, 1 for RR, 2 for respiratory, 3 for ppg
    #
    SAVE_FILE = None
    NEXT_FILE = None
    _instance = None
    config = config.default_config
    shortcuts = None
    # load file variables:
    is_load = False
    noise_level = 0
    beat_correction_level = 0
    current_outlier = 0
    annotations = np.array([], dtype="int32")
    is_threshold_outlier = False
    is_algorithm_outlier = False
    algorithm_correction = False
    samples_dictionary = {}

    def __init__(self, file_to_load: Path = None, **kwargs):
        start = timer()
        
        PALMS._instance = weakref.ref(self)()
        # sys.argv[0] = 'PALMS'  # to override Application menu on OSX
        QtCore.qInstallMessageHandler(self._log_handler)
        QtWidgets.QApplication.setDesktopSettingsAware(False)
        self.qtapp = qtapp = QtWidgets.QApplication(sys.argv)
        qtapp.setStyle("fusion")
        qtapp.setApplicationName("EZcardio")
        qtapp.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
        
        if hasattr(QtWidgets.QStyleFactory, 'AA_UseHighDpiPixmaps'):
            qtapp.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)

        try:
            with open(config.CONFIG_PATH) as file:
                PALMS.config.update(json.load(file))
            with open(config.SHORTCUTS_PATH) as file:
                PALMS.shortcuts = json.load(file)
        except IOError:
            logging.debug('cannot find saved configuration, using default configuration')

        db_name = self.config.get('prev_database', None)
        

        if (file_to_load is not None) and (db_name is not None) and (db_name in ALL_DATABASES):
            try:
                db = getattr(sys.modules[DATABASE_MODULE_NAME], db_name).__call__()
                self.initialize_new_file(file_to_load)
            except Exception as e:
                Dialog().warningMessage(
                    'Loading requested file {} failed with \n {} \nPlease select a file manually'.format(file_to_load, str(e)))
                self.request_user_input_database_and_file()

        else:
            self.request_user_input_database_and_file()

    
            

    def request_user_input_database_and_file(self):

        try: 
            #app = QApplication(sys.argv)
            mainWindow = MyMainImport(self)
            #mainWindow.show()
            if QApplication.instance():
                mainWindow.exec_()

            if self.continue_value == False:
                sys.exit(1)

            self.after_input()
        except:
            sys.exit(1)

    def after_input(self):

        if self.ECG_DATA == np.array([]):
            sys.exit(1)

        self.DATA_TYPE = max(0, self.DATA_TYPE-1) # 0 for ECG and RR, 1 for RESP, 2 for PPG
        db_name = ALL_DATABASES[self.DATA_TYPE]
        db = getattr(sys.modules[DATABASE_MODULE_NAME], db_name).__call__()
        
        # PALMS.CURRENT_FILE = pathlib.Path(db, self.CURRENT_FILE)
        PALMS.CURRENT_FILE = pathlib.Path(self.CURRENT_FILE)
        # Initialise other import preferencesgetSelectedDisplayPanel
        if (self.RR_ONLY == False):
            self.initialize_new_file(Path(self.CURRENT_FILE), self.ECG_DATA, self.FREQUENCY, self.TIME_DATA, self.START_INDEXES, self.END_INDEXES)
        
            mode = Modes.browse.value

            if mode not in Mode.all_modes():
               mode = Modes.browse.value
            Mode.switch_mode(Modes[mode]) # Modes has no influence on gui
        
            self.viewer.getSelectedDisplayPanel().plot_area.sigScaleChanged.emit(self.viewer.getSelectedDisplayPanel().plot_area) 
            # No idea what previous line does, but not plotting signal

            # Update range of graphs and bars with length of signal
            x_min, x_max = self.viewer.getSelectedView().track.get_time()[[0,-1]] 
            # self.viewer.getSelectedView().renderer.vb.setXRange(x_min, (x_min*0.99+x_max*0.01),padding=0) # This updates peaks # 
            self.viewer.getSelectedDisplayPanel().plot_area.main_vb.setXRange(x_min, (x_min*0.99+x_max*0.01),padding=0)
            self.viewer.getRRDisplayPanel().plot_area.main_vb.setXRange(x_min, (x_min*0.99+x_max*0.01),padding=0)
        else:
            self.initialize_new_rr_file(Path(self.CURRENT_FILE), self.ECG_DATA, self.FREQUENCY, self.TIME_DATA, self.START_INDEXES, self.END_INDEXES)
        
            mode = Modes.browse.value

            if mode not in Mode.all_modes():
               mode = Modes.browse.value
            Mode.switch_mode(Modes[mode]) # Modes has no influence on gui

            # Update range of graphs and bars with length of signal
            x_min, x_max = self.viewer.getSelectedView().track.get_time()[[0,-1]] 
            # self.viewer.getSelectedView().renderer.vb.setXRange(x_min, (x_min*0.99+x_max*0.01),padding=0) # This updates peaks # 
            self.viewer.getSelectedDisplayPanel().plot_area.main_vb.setXRange(x_min, (x_min*0.99+x_max*0.01),padding=0)
            self.viewer.getRRDisplayPanel().plot_area.main_vb.setXRange(x_min, (x_min*0.99+x_max*0.01),padding=0)

        self.updateRR(True, True)

        if self.is_load:
            # add as missing beats the outliers that are not interpolations

            # write noise and outliers previous things
            # text left outliers
            # beat dropdown
            self.viewer.top_left_w.beat_threshold_level.setCurrentIndex(int(self.beat_correction_level))
            self.viewer.top_left_w.beat_threshold_text_label.setText(f"{len(self.threshold_outliers)} outliers detected ({round(100 * len(self.threshold_outliers) / len(self.annotations), 2)} % of beats)")
            

            # text left noise
            noise_start_points = RRNoisePartitions.all_startpoints_by_two_names("", "ecg")
            noise_end_points = RRNoisePartitions.all_endpoints_by_two_names("", "ecg")

            signal_length = PALMS.get().from_sample_to_time(len(PALMS.get().ECG_DATA)-1)
            noise_length = 0
            noise_count = 0
            for noise_start, noise_end in zip(noise_start_points, noise_end_points):
                noise_length += (noise_end - noise_start)
                noise_count += 1

            ratio_noise = round(100*noise_length/signal_length, 2)
            self.viewer.top_left_w.noise_text_label.setText(f"{noise_count} intervals detected ({ratio_noise} % of signal)")
            # noise dropdown
            self.viewer.top_left_w.noise_level.setCurrentIndex(int(self.noise_level))

            # algorithm button
            # if self.algorithm_correction:
            #    self.viewer.top_left_w.algorithm_active = False # not using, otherwise first time it will not detect
            if self.algorithm_correction:
                self.viewer.top_left_w.beat_algorithm_button.setStyleSheet("background-color: red; color: white;")
                self.viewer.top_left_w.beat_algorithm_button.setText("Cancel")
                algorithm_outliers_length = len(self.algorithm_outliers.get("add", np.array([], dtype="int32"))) + len(self.algorithm_outliers.get("delete", np.array([], dtype="int32"))) + len(self.algorithm_outliers.get("interpolate", np.array([], dtype="int32")))
                self.viewer.top_left_w.beat_algorithm_text_label.setText(f"{algorithm_outliers_length} outliers detected ({round(100 * algorithm_outliers_length / len(self.annotations), 2)} % of beats)")
            
            # selector values
            self.viewer.getOutliersDisplayPanel().threshold_outliers = self.threshold_outliers
            for key, value in self.algorithm_outliers.items():
                if len(value!=0):
                    self.viewer.getOutliersDisplayPanel().algorithm_outliers = np.concatenate((self.viewer.getOutliersDisplayPanel().algorithm_outliers, value), axis=None)

            if (self.is_algorithm_outlier):
                self.viewer.getOutliersDisplayPanel().initializeAlgorithmOutliers()
                self.viewer.getOutliersDisplayPanel().switchSelectorOption()
            elif (self.is_threshold_outlier):
                self.viewer.getOutliersDisplayPanel().initializeThresholdOutliers()
                self.viewer.getOutliersDisplayPanel().switchSelectorOption()
            else:
                self.viewer.getOutliersDisplayPanel().initializeNoise()
                self.viewer.getOutliersDisplayPanel().switchSelectorOption()

            # update noise and outlier labels
            self.viewer.getOutliersDisplayPanel().currentSelector = self.current_outlier-1
            self.viewer.getOutliersDisplayPanel().update_label(self.current_outlier-1, 1)
        
        
        exit_code, file_to_load = self.start()
        self._exit(exit_code)

        while exit_code in [PALMS.EXIT_CODE_REBOOT, PALMS.EXIT_CODE_LOAD_NEXT, PALMS.EXIT_CODE_LOAD_PREV]:
            app = PALMS(None)
            exit_code, file_to_load = app.start()
            self._exit(exit_code)
        sys.exit(exit_code)

    def initialize_new_file(self, filepath: Path, ecg_data, frequency, time_data, start_indexes, end_indexes):

        from logic.operation_mode.annotation import AnnotationConfig
        
        db = Database.get()
        
        if (self.is_load == False):
            try:
                db.get_data(filepath.as_posix(), ecg_data, frequency, time_data, start_indexes, end_indexes)
            except Exception as e:
                Dialog().warningMessage(
                'There was an error on {} with \n'.format(filepath.name) +
                str(e) +
                '\nMake sure you set all the correct options before trying to import the file')
                self.ECG_DATA = []
                self.delete_all()
                self.request_user_input_database_and_file()
            try:
                db.set_annotation_config()
                db.set_epochMode_config()
                db.set_annotation_data(frequency)
                annotations = [fiducial.annotation.idx for fiducial in AnnotationConfig.get().fiducials]
                annotations = np.array(annotations[0])
                if len(annotations) == 0:
                    Dialog().warningMessage(
                    'There was an error detecting the beats'+
                    '\nMake sure the selected data type is the correct one')
                    self.ECG_DATA = []
                    self.delete_all()
                    self.request_user_input_database_and_file()
            except: 
                Dialog().warningMessage(
                'There was an error detecting the beats'+
                '\nMake sure the selected data type is the correct one')
                self.ECG_DATA = []
                self.delete_all()
                self.request_user_input_database_and_file()

        else:
            try:
                db.load_data(filepath.as_posix(), ecg_data, frequency, time_data, start_indexes, end_indexes)
            except Exception as e:
                Dialog().warningMessage(
                'There was an error on {} with \n'.format(filepath.name) +
                str(e) +
                '\nMake sure you set all the correct options before trying to import the file')
                self.ECG_DATA = []
                self.delete_all()
                self.request_user_input_database_and_file()
            try:
                db.set_annotation_config()
                db.set_epochMode_config()
                self.original_annotations = self.annotations
                db.load_annotation_data(self.annotations)
            except:
                Dialog().warningMessage(
                'There was an error detecting the beats'+
                '\nMake sure the selected data type is the correct one')
                self.ECG_DATA = []
                self.delete_all()
                self.request_user_input_database_and_file()

        
        self.viewer = Viewer(self)
        # Loop where ECG appears:
        for i, s in enumerate(db.tracks_to_plot_initially): # This plots the option on the right column, but not the right column
            self.add_view_from_track(db.tracks[s], 0) # Also plots the right column signal options
        try:
            file_idx = Database.get().get_all_files_in_database().index(filepath) + 1
            n_files = len(Database.get().get_all_files_in_database())
            progress_str = str(file_idx) + '/' + str(n_files)
        except:
            progress_str = ''
        self.viewer.setWindowTitle(filepath.as_posix() + ' ' + progress_str)
        

        
        self.viewer.get().annotationConfig.aConf_to_table(AnnotationConfig.get()) # no effect on gui

        self.viewer.initial_point = self.viewer.selectedDisplayPanel.plot_area.main_vb.viewRange()[0]

        page_step = self.viewer.initial_point[0]*0.99 + self.viewer.initial_point[1]*0.01
        self.viewer.range_slider_ECG.setMinimum(self.viewer.initial_point[0])
        self.viewer.range_slider_ECG.setMaximum(self.viewer.initial_point[1]-page_step)
        self.viewer.range_slider_ECG.setPageStep(page_step)
        self.viewer.range_slider_ECG.setValue(self.viewer.initial_point[0])

        
        self.fiducials, self.rr_intervals = Annotation.get().create_RRinterval_track()
        # fiducials is the interpolated signal to plot, rr_intervals is all 0s except for the rr values
        self.add_view_from_track(self.fiducials, 1) # add RR graph

        self.viewer.selectedDisplayPanel.plot_area.redraw_fiducials() # no effect on gui (update r-peaks annotation)

        self.viewer.range_slider_RR.setMinimum(self.viewer.initial_point[0])
        self.viewer.range_slider_RR.setMaximum(self.viewer.initial_point[1]-page_step)
        self.viewer.range_slider_RR.setPageStep(page_step)
        self.viewer.range_slider_RR.setValue(self.viewer.initial_point[0])


    def initialize_new_rr_file(self, filepath: Path, ecg_data, frequency, time_data, start_indexes, end_indexes):

        if (self.is_load == False):

            original_ecg = ecg_data

            start_indexes = self.START_MISSING_INDEXES
            end_indexes = self.END_MISSING_INDEXES

            rr_ts = np.arange(0, self.END_MISSING_INDEXES[-1] / frequency, 1 / frequency)
            total_rr = np.zeros_like(rr_ts).astype(float)
            time_data = np.zeros_like(rr_ts)

            for start, end in zip(start_indexes, end_indexes):
                annotations = np.cumsum(ecg_data)+end-start
                annotations -= annotations[0]
                annotations *= frequency
                current_annotations = annotations[(annotations >= start) & (annotations <= end)]
                current_ecg = original_ecg[(annotations >= start) & (annotations <= end)]
                # ecg_data is original rr interpolated considering its times
                interpolated_rr = np.interp(list(range(start, end)), current_annotations, current_ecg)
                total_rr[start:end] = interpolated_rr[:(end-start)]
                # time data

            # time_desired
            time_desired = rr_ts
            time_data = annotations
            
            import copy
            self.rr_intervals = copy.deepcopy(time_data)
            self.ECG_DATA = copy.deepcopy(total_rr)

        else:
            import copy
            total_rr = copy.deepcopy(self.ECG_DATA)
            time_desired = copy.deepcopy(self.TIME_DATA)
            self.rr_intervals = copy.deepcopy(self.annotations)

        db = Database.get()

        try:
            db.get_rr_data(filepath.as_posix(), total_rr, frequency, time_desired, start_indexes, end_indexes)
        except Exception as e:
            import traceback
            Dialog().warningMessage(
                'There was an error on {} with \n'.format(filepath.name) +
                str(e) +
                '\nMake sure you set all the correct options before trying to import the file')
            error_traceback = traceback.format_exc()
            print(error_traceback)
            self.ECG_DATA = []
            self.delete_all()
            self.request_user_input_database_and_file()
        try:
            db.set_annotation_config()
            db.set_epochMode_config()
            self.original_annotations = copy.deepcopy(self.rr_intervals)
            db.set_rr_annotation_data(np.array(self.rr_intervals))
            annotations = [fiducial.annotation.idx for fiducial in AnnotationConfig.get().fiducials]
            annotations = np.array(annotations[0])
            if len(annotations) == 0:
                Dialog().warningMessage(
                'There was an error detecting the beats'+
                '\nMake sure the selected data type is the correct one')
                self.ECG_DATA = []
                self.delete_all()
                self.request_user_input_database_and_file()
        except:
            Dialog().warningMessage(
            'There was an error detecting the beats'+
            '\nMake sure the selected data type is the correct one')
            self.ECG_DATA = []
            self.delete_all()
            self.request_user_input_database_and_file()

        
        self.viewer = Viewer(self)
        
        # save samples where peaks are on Annotation (based on ECG_data, which is ibis, and frequency)
        self.fiducials, self.rr_intervals = Annotation.get().create_RRinterval_track()
        self.add_view_from_track(self.fiducials, 0) # add RR graph
        self.viewer.initial_point = self.viewer.selectedDisplayPanel.plot_area.main_vb.viewRange()[0]

        page_step = self.viewer.initial_point[0]*0.99 + self.viewer.initial_point[1]*0.01

        self.viewer.range_slider_RR.setMinimum(self.viewer.initial_point[0])
        self.viewer.range_slider_RR.setMaximum(self.viewer.initial_point[1]-page_step)
        self.viewer.range_slider_RR.setPageStep(page_step)
        self.viewer.range_slider_RR.setValue(self.viewer.initial_point[0])
    

    def updateRR(self, correct=False, manual=False):

        if self.RR_ONLY is False:
            import copy
            if self.is_load:
                new_fiducials, self.rr_intervals = Annotation.get().create_RRinterval_track(correct)
            else:
                self.original_rr, self.rr_intervals = Annotation.get().create_RRinterval_track(correct)
                self.original_fiducials = copy.deepcopy(self.rr_intervals)
                new_fiducials = copy.deepcopy(self.original_rr)


            self.viewer.guiDelView()

            
            self.fiducials = copy.deepcopy(self.original_rr)
            self.add_view_from_track(self.original_rr, 1)
            first_view = self.viewer.getRRDisplayPanel().panel.views[0]
            first_view.set_color((100, 100, 100, 100))
            self.viewer.getRRDisplayPanel().plot_area.changeColor(first_view)
            self.fiducials.set_value(new_fiducials.get_value())
            self.fiducials.set_viewvalue(new_fiducials.get_viewvalue())
            self.add_view_from_track(self.fiducials, 1)

            self.viewer.RRDisplayPanel.plot_area.updateViews()
        
            self.viewer.selectedDisplayPanel.plot_area.redraw_fiducials()

        
            self.viewer.results_w.update_current_result()

            self.viewer.RRregion = None
            self.viewer.updateHighlighted()

        else:
            import copy
            if self.is_load:
                new_fiducials, self.rr_intervals = Annotation.get().create_RRinterval_track(correct)
            else:
                self.original_rr, self.rr_intervals = Annotation.get().create_RRinterval_track(correct)
                self.original_fiducials = copy.deepcopy(self.rr_intervals)
                new_fiducials = copy.deepcopy(self.rr_intervals)

            self.viewer.guiDelView()

            
            self.fiducials = copy.deepcopy(self.original_rr)
            self.add_view_from_track(self.original_rr, 0)
            x_min, x_max = self.viewer.getSelectedView().track.get_time()[[0,-1]] 
            self.viewer.getRRDisplayPanel().plot_area.main_vb.setXRange(x_min, (x_min*0.99+x_max*0.01),padding=0)
            first_view = self.viewer.getRRDisplayPanel().panel.views[0]
            first_view.set_color((100, 100, 100, 100))
            self.viewer.getRRDisplayPanel().plot_area.changeColor(first_view)
            self.fiducials.set_value(new_fiducials.get_value())
            self.fiducials.set_viewvalue(new_fiducials.get_viewvalue())
            self.add_view_from_track(self.fiducials, 0)
            
            self.viewer.RRDisplayPanel.plot_area.updateViews()

            self.viewer.selectedDisplayPanel.plot_area.redraw_fiducials()

            self.viewer.results_w.update_current_result()


    def singleUpdateRR(self, annotation_change, change_type, updateGraph=False):
        # annotation_change: index of the annotation to change
        # change_type: 0 to add, 1 to delete, 2 to interpolate

        if self.RR_ONLY is False:
            self.fiducials, self.rr_intervals = Annotation.get().update_RRinterval_track(annotation_change, change_type)

            if updateGraph:

                first_view = self.viewer.getRRDisplayPanel().panel.views[0]
                first_view.set_color((100, 100, 100, 100))
                self.viewer.getRRDisplayPanel().plot_area.changeColor(first_view)
                #
                import copy
                new_fiducials = copy.deepcopy(self.original_rr)
                new_fiducials.set_value(self.fiducials.get_value())
                new_fiducials.set_viewvalue(self.fiducials.get_viewvalue())
                self.viewer.guiDelView()
                self.add_view_from_track(new_fiducials, 1)
                
                self.viewer.RRDisplayPanel.plot_area.alignViews()
        
                self.viewer.selectedDisplayPanel.plot_area.redraw_fiducials()

        
                self.viewer.results_w.update_current_result()

                self.viewer.RRregion = None
                self.viewer.updateHighlighted()

        else:
            self.fiducials, self.rr_intervals = Annotation.get().update_RRinterval_track(annotation_change, change_type)

            if updateGraph:

                self.viewer.guiDelView()

                first_view = self.viewer.getRRDisplayPanel().panel.views[0]
                first_view.set_color((100, 100, 100, 100))
                self.viewer.getRRDisplayPanel().plot_area.changeColor(first_view)

                import copy
                new_fiducials = copy.deepcopy(self.original_rr)
                new_fiducials.set_value(self.fiducials.get_value())
                new_fiducials.set_viewvalue(self.fiducials.get_viewvalue())
                
                self.add_view_from_track(new_fiducials, 0)
                
                self.viewer.RRDisplayPanel.plot_area.alignViews()
        
                self.viewer.RRDisplayPanel.plot_area.redraw_fiducials()

                self.viewer.results_w.update_current_result()


    def createNewRRGraph(self):
        # annotation_change: index of the annotation to change
        # change_type: 0 to add, 1 to delete, 2 to interpolate

        if self.RR_ONLY is False:
            #self.viewer.guiDelView()

            #self.add_view_from_track(self.fiducials, 1)

            first_view = self.viewer.getRRDisplayPanel().panel.views[0]
            first_view.set_color((100, 100, 100, 100))
            self.viewer.getRRDisplayPanel().plot_area.changeColor(first_view)
            # update second view
            import copy
            new_fiducials = copy.deepcopy(self.original_rr)
            new_fiducials.set_value(self.fiducials.get_value())
            new_fiducials.set_viewvalue(self.fiducials.get_viewvalue())
            self.viewer.guiDelView()
            self.add_view_from_track(new_fiducials, 1)

            self.viewer.RRDisplayPanel.plot_area.alignViews()
        
            self.viewer.RRDisplayPanel.plot_area.redraw_fiducials()

        
            self.viewer.results_w.update_current_result()

            self.viewer.RRregion = None
            self.viewer.updateHighlighted()

        else:

            self.viewer.guiDelView()

            first_view = self.viewer.getRRDisplayPanel().panel.views[0]
            first_view.set_color((100, 100, 100, 100))
            self.viewer.getRRDisplayPanel().plot_area.changeColor(first_view)
            # update second view
            import copy
            new_fiducials = copy.deepcopy(self.original_rr)
            new_fiducials.set_value(self.fiducials.get_value())
            new_fiducials.set_viewvalue(self.fiducials.get_viewvalue())
            
            self.add_view_from_track(new_fiducials, 0)

            self.viewer.RRDisplayPanel.plot_area.alignViews()
        
            self.viewer.selectedDisplayPanel.plot_area.redraw_fiducials()

            self.viewer.results_w.update_current_result()


    def from_sample_to_time(self, sample_index):
        from logic.databases.DatabaseHandler import Database
        real_time = Database.get().tracks[Database.get().main_track_label].time
        return real_time[sample_index]
    
    def from_time_to_sample(self, time):
        from logic.databases.DatabaseHandler import Database
        real_time = Database.get().tracks[Database.get().main_track_label].time
        real_time = np.array(real_time)
        sample_index = np.where(real_time == time)[0]
        sample_index = sample_index[0]
        return sample_index
    
    def from_time_to_closest_sample(self, value):
        from logic.databases.DatabaseHandler import Database
        real_time = Database.get().tracks[Database.get().main_track_label].time
        real_time = np.asarray(real_time)
        idx = (np.abs(real_time - value)).argmin()
        return idx
    

    

    @staticmethod
    def update_config():
        #PALMS.config.update({'viewer_window_size': [PALMS.get().viewer.width(), PALMS.get().viewer.height()]})
        PALMS.config.update({'prev_database': Database.get().name})
        #PALMS.config.update({'autoscale_y': PALMS.get().viewer.settings_menu.autoscale_y_action.isChecked()})
        #PALMS.config.update({'save_tracks': PALMS.get().viewer.settings_menu.save_tracks_action.isChecked()})
        #PALMS.config.update({'save_overwrite': PALMS.get().viewer.settings_menu.save_overwrite_action.isChecked()})
        PALMS.config.update({'default_mode': Mode.current_mode_name()})

    @staticmethod
    def get():
        return PALMS._instance

    @staticmethod
    def _log_handler(msg_type, msg_log_context, msg_string):
        if msg_type == 1:
            if re.match("QGridLayoutEngine::addItem: Cell \\(\\d+, \\d+\\) already taken", msg_string):
                return
            logger.warning(msg_string)
        elif msg_type == 2:
            logger.critical(msg_string)
        elif msg_type == 3:
            logger.error(msg_string)
        elif msg_type == 4:
            logger.info(msg_string)
        elif msg_type == 0:
            logger.debug(msg_string)
        else:
            logger.warning(f'received unknown message type from qt system with contents {msg_string}')
        try:
            Viewer.get().status(msg_string)
        except:
            pass

    def start(self):
        # Set the window to maximize by default
        self.viewer.showMaximized()

        self.viewer.show() #here it plots the signal
        #self.viewer.selectedDisplayPanel.plot_area.toggleAllViewsExceptMain() #here it unticks ecg to show just ecg_filt
        self.viewer.zoomIn()
        self.viewer.zoomOut()

        self.viewer.toggle_resize_down()
        self.viewer.toggle_resize_down()

        

        # Create missing signal intervals
        for new_end, new_start in zip(self.END_MISSING_INDEXES[:-1], self.START_MISSING_INDEXES[1:]): 

            new_start = PALMS.get().from_sample_to_time(new_start)
            new_end = PALMS.get().from_sample_to_time(new_end)

            mode = Modes.noise_partition.value
            Mode.switch_mode(Modes[mode]) # Modes has no influence on gui

            if self.RR_ONLY is False:
                p = NoisePartition("miss", start=new_end, end=new_start, click=False) # The partition goes from end to start, as it is the missing part
                self.viewer.selectedDisplayPanel.plot_area.main_vb.addItem(p)
                p.setMovable(False)

            p_rr = RRNoisePartition("miss", start=new_end, end=new_start, click=False) # The partition goes from end to start, as it is the missing part
            self.viewer.RRDisplayPanel.plot_area.main_vb.addItem(p_rr)
            p_rr.label.setVisible(False)
            self.viewer.RRDisplayPanel.plot_area.main_vb.addItem(p_rr.label)

            p_rr.setMovable(False)
            
            mode = Modes.browse.value
            Mode.switch_mode(Modes[mode]) # Modes has no influence on gui
            # Not adding indexes, they were added in import
            # Not updating RR, already updated


        # Create ecg noise intervals
        noise_length = 0
        noise_count = 0
        
        for new_end, new_start in zip(self.END_ECG_INDEXES, self.START_ECG_INDEXES): 

            new_start_time = PALMS.get().from_sample_to_time(new_start)
            new_end_time = PALMS.get().from_sample_to_time(new_end)

            mode = Modes.noise_partition.value
            Mode.switch_mode(Modes[mode]) # Modes has no influence on gui

            if self.RR_ONLY is False:
                p = NoisePartition("ecg", start=new_end_time, end=new_start_time, click=False) # The partition goes from end to start, as it is the missing part
                self.viewer.selectedDisplayPanel.plot_area.main_vb.addItem(p)
                p.setMovable(True)

            p_rr = RRNoisePartition("ecg", start=new_end_time, end=new_start_time, click=False) # The partition goes from end to start, as it is the missing part
            self.viewer.RRDisplayPanel.plot_area.main_vb.addItem(p_rr)
            p_rr.label.setVisible(False)
            self.viewer.RRDisplayPanel.plot_area.main_vb.addItem(p_rr.label)

            p_rr.setMovable(True)
            
            mode = Modes.browse.value
            Mode.switch_mode(Modes[mode]) # Modes has no influence on gui

            noise_length += (new_start - new_end)
            noise_count += 1
        
        # initialize noise label and selector
        signal_length = len(PALMS.get().ECG_DATA)
        
        ratio_noise = round(100*noise_length/signal_length, 2)
        self.viewer.top_left_w.noise_text_label.setText(f"{noise_count} intervals detected ({ratio_noise} % of signal)")
        

        self.viewer.getOutliersDisplayPanel().selector_option.setCurrentIndex(0)
        self.viewer.getOutliersDisplayPanel().switchSelectorOption()
        
        if self.is_load:
            # add samples
            for sample_name, sample_data in self.samples_dictionary.items():
                for i, values in sample_data.items():
                    sample_start = values['start']
                    sample_end = values['end']
                    p = SinglePartition(sample_name, start=self.from_sample_to_time(sample_start), end=self.from_sample_to_time(sample_end)) 
                    self.viewer.getRRDisplayPanel().plot_area.main_vb.addItem(p)

                self.viewer.top_left_w.load_sample(sample_name)

            # add noise
            if (len(self.START_INDEXES) > 1):
                noise_starts = np.delete(self.END_INDEXES, -1)
                noise_ends = np.delete(self.START_INDEXES, 0)
                for noise_start, noise_end in zip(noise_starts, noise_ends):
                    p = NoisePartition("", start=noise_start/self.FREQUENCY, end=noise_end/self.FREQUENCY) 
                    self.viewer.getSelectedDisplayPanel().plot_area.main_vb.addItem(p)
                    p_rr = RRNoisePartition("", start=noise_start/self.FREQUENCY, end=noise_end/self.FREQUENCY) 
                    self.viewer.getRRDisplayPanel().plot_area.main_vb.addItem(p_rr)

        else: # if not load, detect default noise and outliers
            
            self.viewer.top_left_w.detectNoise()
            
            if self.viewer.top_left_w.algorithm_active and self.viewer.top_left_w.beat_threshold_level != 0: # do both
                self.viewer.top_left_w.outlier_decision_central(False)

            elif self.viewer.top_left_w.beat_threshold_level != 0:
                self.viewer.top_left_w.outlier_decision_central(True)
            

        self.viewer.RRDisplayPanel.plot_area.alignViews()
        
        
        exit_code = self.qtapp.exec_()
        
        file_to_load = None
        if exit_code == PALMS.EXIT_CODE_LOAD_NEXT:
            file_to_load = PALMS.NEXT_FILE
        elif exit_code == PALMS.EXIT_CODE_LOAD_PREV:
            file_to_load = PALMS.PREV_FILE

        self.update_config()
        with open(config.CONFIG_PATH, 'w') as file:
            json.dump(PALMS.config, file, indent=4)

        return (exit_code, file_to_load)

    def _exit(self, status):
        self.update_config()
        with open(config.CONFIG_PATH, 'w') as file:
            json.dump(PALMS.config, file, indent=4)
        self.qtapp.closeAllWindows()
        del self.viewer
        del self.qtapp

    def delete_all(self):
        self.continue_value = False
        self.CURRENT_FILE = None
        self.ECG_DATA = None
        self.RR_ONLY = False
        self.FREQUENCY = None
        self.TIME_DATA = None
        self.START_INDEXES = np.array([], dtype="int32")
        self.END_INDEXES = np.array([], dtype="int32")
        self.START_MISSING_INDEXES = np.array([], dtype="int32")
        self.END_MISSING_INDEXES = np.array([], dtype="int32")
        self.START_ECG_INDEXES = np.array([], dtype="int32")
        self.END_ECG_INDEXES = np.array([], dtype="int32")
        self.FIRST_DATETIME = None
        self.LAST_DATETIME = None
        self.ORIGINAL_DATETIME = None
        self.fiducials = np.array([], dtype="int32")
        self.rr_intervals = np.array([])
        self.original_rr = np.array([])
        self.original_fiducials = np.array([])
        #
        self.NEXT_FILE = None
        self.SAVE_FILE = None
        self._instance = None
        self.config = config.default_config
        self.shortcuts = None
        # load file variables:
        self.is_load = False
        self.noise_level = 0
        self.beat_correction_level = 0
        self.current_outlier = 0
        self.annotations = np.array([], dtype="int32")
        self.threshold_outliers = np.array([], dtype="int32")
        self.algorithm_outliers = {}
        self.algorithm_outliers["add"] = np.array([], dtype="int32")
        self.algorithm_outliers["delete"] = np.array([], dtype="int32")
        self.algorithm_outliers["interpolate"] = np.array([], dtype="int32")
        self.is_threshold_outlier = False
        self.is_algorithm_outlier = False
        self.algorithm_correction = False
        self.samples_dictionary = {}


    def add_view(self, track_obj: tracking.Track, panel_index: int = None, renderer_name: Optional[str] = None, *args, **kwargs):
        if isinstance(panel_index, int) and panel_index >= len(self.viewer.frames)-2: # 2 to skip 0 (outliers) and 1 (buttons)
            for pos in range(len(self.viewer.frames)-1, panel_index + 2): # 2 to skip 0 (outliers) and 1 (buttons)
                self.viewer.guiAddPanel()
                self.viewer.selectFrame(self.viewer.frames[pos])
        
        
        if (panel_index == 0 and self.RR_ONLY is False):
            self.viewer.selectedDisplayPanel.createViewWithTrack(track_obj, renderer_name, **kwargs)
        else:
            self.viewer.RRDisplayPanel.createViewWithTrack(track_obj, renderer_name, **kwargs)


    def add_view_from_track(self, track, panel_index: int = None):
        parent_view = self.viewer.selectedView
        
        self.add_view(track, panel_index=panel_index, y_min=track.minY, y_max=track.maxY, x_min=track.minX,
                      x_max=Database.get().get_longest_track_duration())
        if parent_view is not None:
            self.viewer.selectedDisplayPanel.selectView(parent_view)
            
