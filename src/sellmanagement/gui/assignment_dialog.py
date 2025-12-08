from qtpy import QtWidgets, QtCore
from qtpy.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox, QPushButton
from typing import List


class AssignmentDialog(QDialog):
    """Dialog to assign MA settings for a list of tickers."""
    def __init__(self, tickers: List[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assign moving averages")
        self.setModal(True)
        self._tickers = tickers
        self._widgets = {}
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Assign MA for new tickers:"))
        # presets row
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(["SMA 20 1H", "SMA 50 1H", "EMA 20 1H", "SMA 50 D"])
        preset_row.addWidget(self._preset_combo)
        apply_preset = QPushButton("Apply to all")
        preset_row.addWidget(apply_preset)
        v.addLayout(preset_row)
        apply_preset.clicked.connect(self._apply_preset_to_all)
        for tk in tickers:
            row = QHBoxLayout()
            row.addWidget(QLabel(tk))
            fam = QComboBox()
            fam.addItems(["SMA", "EMA"])
            fam.setCurrentText("SMA")
            row.addWidget(fam)
            length = QSpinBox()
            length.setRange(1, 500)
            length.setValue(20)
            row.addWidget(length)
            tf = QComboBox()
            tf.addItems(["1H", "D"])
            tf.setCurrentText("1H")
            row.addWidget(tf)
            v.addLayout(row)
            self._widgets[tk] = (fam, length, tf)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok = QPushButton("Save")
        cancel = QPushButton("Cancel")
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        v.addLayout(btn_row)

        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)

    def assignments(self):
        """Return mapping ticker -> (type, length, timeframe)."""
        out = {}
        for tk, (fam, length, tf) in self._widgets.items():
            out[tk] = (fam.currentText(), int(length.value()), tf.currentText())
        return out

    def _apply_preset_to_all(self):
        text = self._preset_combo.currentText()
        try:
            parts = text.split()
            fam = parts[0]
            ln = int(parts[1])
            tf = parts[2]
            for tk, (fam_w, length_w, tf_w) in self._widgets.items():
                try:
                    fam_w.setCurrentText(fam)
                    length_w.setValue(ln)
                    tf_w.setCurrentText(tf)
                except Exception:
                    continue
        except Exception:
            return

    def show_non_blocking(self, accept_callback=None, reject_callback=None):
        """Show dialog non-modally and call callbacks on accept/reject."""
        if accept_callback:
            self.accepted.connect(lambda: accept_callback(self.assignments()))
        if reject_callback:
            self.rejected.connect(lambda: reject_callback())
        self.setModal(False)
        self.show()


