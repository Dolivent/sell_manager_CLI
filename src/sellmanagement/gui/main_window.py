from qtpy import QtWidgets, QtCore
from .widgets import PositionsWidget, SignalsWidget, SettingsWidget
from .ib_worker import IBWorker
from qtpy import QtWidgets, QtCore
import json
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QWidget, QHBoxLayout
import logging

logger = logging.getLogger(__name__)


class ClickableLabel(QLabel):
    clicked = QtCore.Signal()

    def mousePressEvent(self, event):
        try:
            self.clicked.emit()
        except Exception:
            pass
        super().mousePressEvent(event)



class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("sell_manager - GUI")
        self.resize(1100, 700)

        tabs = QtWidgets.QTabWidget()
        # single shared IB worker
        self.ib_worker = IBWorker()

        self.positions_tab = PositionsWidget()
        self.signals_tab = SignalsWidget()
        self.settings_tab = SettingsWidget()
        # if any assignments missing on startup, notify UI immediately
        try:
            from ..assign import get_assignments_list
            cur = get_assignments_list()
            missing = []
            for r in cur:
                if not (r.get('type') and r.get('length')):
                    missing.append(r.get('ticker'))
            if missing:
                # emit into same flow as pipeline need_assign so dialog opens
                QtCore.QTimer.singleShot(200, lambda: self._on_pipeline_need_assign(missing))
        except Exception:
            pass

        # wire settings connect toggle to IBWorker
        self.settings_tab.connection_toggled.connect(self._on_settings_connect_toggled)
        # wire pre/post-market toggle to signals tab
        try:
            self.settings_tab.show_premarket_toggled.connect(self.signals_tab.set_show_premarket)
        except Exception:
            pass
        self.ib_worker.connected.connect(self._on_ib_connected)
        # deliver positions updates to positions tab
        self.ib_worker.positions_updated.connect(self.positions_tab.on_positions_update)
        # pipeline runner (auto-start when IB connected)
        from .pipeline import PipelineRunner
        self._pipeline = PipelineRunner(self.ib_worker)
        self._pipeline.snapshot_done.connect(lambda tup: self.positions_tab.update_minute_snapshot_info())
        # start pipeline automatically on IB connect (always)
        self.ib_worker.connected.connect(lambda ok: self._pipeline.start() if ok else self._pipeline.stop())
        # handle need_assign signal: show modal and write assignments
        self._pipeline.need_assign.connect(self._on_pipeline_need_assign)
        self._pipeline.need_assign.connect(lambda m: self._append_log(f"Need assign: {m}"))
        # wire signals updates to positions tab for live status updates
        try:
            self.signals_tab.signals_updated.connect(self.positions_tab.on_signals_updated)
        except Exception:
            pass
        # pipeline signals -> append to console
        try:
            self._pipeline.started.connect(lambda: self._append_log("Pipeline started"))
            self._pipeline.stopped.connect(lambda: self._append_log("Pipeline stopped"))
            self._pipeline.snapshot_done.connect(lambda tup: self._append_log(f"Snapshot {tup[0]} ({len(tup[1])} rows)"))
            self.ib_worker.connected.connect(lambda ok: self._append_log(f"IB connected: {ok}"))
        except Exception:
            pass

        tabs.addTab(self.positions_tab, "Positions")
        tabs.addTab(self.signals_tab, "Signals")
        tabs.addTab(self.settings_tab, "Settings")

        # Create a corner widget with Live toggle and status light
        corner = QWidget()
        h = QHBoxLayout(corner)
        h.setContentsMargins(0, 0, 0, 0)
        # use the settings_tab's live_checkbox widget (it exists but is not added to settings layout)
        h.addWidget(self.settings_tab.live_checkbox)
        self._status_label = ClickableLabel("●")
        # style the traffic light: slightly larger, circular, neutral color by default
        self._status_label.setFixedSize(20, 20)
        self._status_label.setStyleSheet("color: gray; font-size: 16px; padding-right:8px; border-radius:10px;")
        # tooltip styling and faster appearance
        try:
            QtWidgets.QToolTip.setFont(self.font())
            QtWidgets.QToolTip.setStyleSheet("QToolTip { color: white; background: #333333; border: 1px solid white; }")
        except Exception:
            pass
        self._status_label.setToolTip("Click to connect / disconnect IB Gateway")
        try:
            self._status_label.setToolTipDuration(500)
        except Exception:
            pass
        h.addWidget(self._status_label)
        h.addStretch()
        tabs.setCornerWidget(corner, Qt.TopRightCorner)

        self.setCentralWidget(tabs)

        # wire status label click to connect/disconnect
        self._status_label.clicked.connect(self._on_status_clicked)
        self._ib_connected = False
        # try to auto-connect on startup
        QtCore.QTimer.singleShot(100, self._attempt_autoconnect)
        # track whether an assignment dialog is active to avoid duplicates
        self._assign_dialog_active = False
        self._assign_dialog = None

    def _on_settings_connect_toggled(self, checked: bool):
        if checked:
            host = self.settings_tab.host.text()
            port = int(self.settings_tab.port.value())
            client_id = int(self.settings_tab.client_id.value())
            self.ib_worker.connect(host=host, port=port, client_id=client_id)
        else:
            self.ib_worker.disconnect()

    def _on_ib_connected(self, ok: bool):
        self._ib_connected = bool(ok)
        if ok:
            self._status_label.setStyleSheet("color: green; font-size: 16px; padding-right:8px;")
            # start poll timer on main thread
            try:
                if not self.ib_worker._poll_timer.isActive():
                    self.ib_worker._poll_timer.start()
            except Exception:
                logger.exception("Failed to start poll timer on connect")
        else:
            self._status_label.setStyleSheet("color: red; font-size: 16px; padding-right:8px;")
            try:
                if self.ib_worker._poll_timer.isActive():
                    self.ib_worker._poll_timer.stop()
            except Exception:
                logger.exception("Failed to stop poll timer on disconnect")

    def _on_status_clicked(self):
        # If currently connected, disconnect; otherwise attempt connect using settings values
        if self._ib_connected:
            try:
                self.ib_worker.disconnect()
            except Exception:
                logger.exception("Failed to disconnect IBWorker")
        else:
            host = self.settings_tab.host.text()
            port = int(self.settings_tab.port.value())
            client_id = int(self.settings_tab.client_id.value())
            try:
                self.ib_worker.connect(host=host, port=port, client_id=client_id)
            except Exception:
                logger.exception("Failed to connect on status click")

    def _attempt_autoconnect(self):
        # Try connecting on startup, do not require Live checkbox
        host = self.settings_tab.host.text()
        port = int(self.settings_tab.port.value())
        client_id = int(self.settings_tab.client_id.value())
        try:
            self.ib_worker.connect(host=host, port=port, client_id=client_id)
        except Exception:
            logger.exception("Auto-connect failed")
    def closeEvent(self, event):
        # Attempt a clean shutdown: stop timers and disconnect IB cleanly.
        try:
            try:
                if self.ib_worker._poll_timer.isActive():
                    self.ib_worker._poll_timer.stop()
            except Exception:
                pass
            try:
                # perform shutdown which submits disconnect to IB thread and joins it
                self.ib_worker.shutdown(timeout=3.0)
            except Exception:
                logger.exception("Error while shutting down IB worker")
        finally:
            super().closeEvent(event)

    def _on_pipeline_need_assign(self, missing_list):
        # Show non-blocking assignment dialog and persist results; pipeline will be resumed via confirm_assignments callback
        try:
            from .assignment_dialog import AssignmentDialog
            from ..assign import set_assignment

            def _on_accept(assigns_map):
                try:
                    for tk, (fam, ln, tf) in assigns_map.items():
                        try:
                            set_assignment(tk, fam, ln, timeframe=tf)
                        except Exception:
                            pass
                finally:
                    try:
                        self._pipeline.confirm_assignments()
                    except Exception:
                        pass

            def _on_reject():
                # user cancelled; still resume pipeline
                try:
                    self._pipeline.confirm_assignments()
                except Exception:
                    pass

            # avoid opening multiple dialogs
            if getattr(self, "_assign_dialog_active", False):
                try:
                    if self._assign_dialog:
                        self._assign_dialog.raise_()
                        self._assign_dialog.activateWindow()
                except Exception:
                    pass
                return

            dlg = AssignmentDialog(missing_list, parent=self)
            self._assign_dialog_active = True
            self._assign_dialog = dlg

            def _wrapped_accept(assigns_map):
                try:
                    _on_accept(assigns_map)
                finally:
                    try:
                        self._assign_dialog_active = False
                        self._assign_dialog = None
                    except Exception:
                        pass

            def _wrapped_reject():
                try:
                    _on_reject()
                finally:
                    try:
                        self._assign_dialog_active = False
                        self._assign_dialog = None
                    except Exception:
                        pass

            dlg.show_non_blocking(accept_callback=_wrapped_accept, reject_callback=_wrapped_reject)
        except Exception:
            try:
                self._pipeline.confirm_assignments()
            except Exception:
                pass

    def _append_log(self, text: str):
        try:
            now = QtCore.QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
            msg = f"[{now}] {text}"
            try:
                self.settings_tab.console.appendPlainText(msg)
            except Exception:
                pass
        except Exception:
            pass


