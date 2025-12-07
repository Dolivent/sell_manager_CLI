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

        # wire settings connect toggle to IBWorker
        self.settings_tab.connection_toggled.connect(self._on_settings_connect_toggled)
        self.ib_worker.connected.connect(self._on_ib_connected)
        # deliver positions updates to positions tab
        self.ib_worker.positions_updated.connect(self.positions_tab.on_positions_update)
        # wire signals updates to positions tab for live status updates
        try:
            self.signals_tab.signals_updated.connect(self.positions_tab.on_signals_updated)
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
        self._status_label.setStyleSheet("color: gray; font-size: 16px; padding-right:8px;")
        h.addWidget(self._status_label)
        h.addStretch()
        tabs.setCornerWidget(corner, Qt.TopRightCorner)

        self.setCentralWidget(tabs)

        # wire status label click to connect/disconnect
        self._status_label.clicked.connect(self._on_status_clicked)
        self._ib_connected = False
        # try to auto-connect on startup
        QtCore.QTimer.singleShot(100, self._attempt_autoconnect)

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


