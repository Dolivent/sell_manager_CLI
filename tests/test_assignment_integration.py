import pytest

def test_assignment_dialog_non_blocking(monkeypatch):
    try:
        from qtpy import QtWidgets
    except Exception:
        pytest.skip("Qt not available")

    try:
        from src.sellmanagement.gui.assignment_dialog import AssignmentDialog
    except Exception:
        pytest.skip("AssignmentDialog import failed")

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dlg = AssignmentDialog(["NASDAQ:TSLA", "NYSE:PL"])

    accepted = {}

    def on_accept(assigns):
        accepted.update(assigns)

    dlg.show_non_blocking(accept_callback=on_accept, reject_callback=lambda: None)
    # simulate user interaction: set values then accept
    for tk, (fam_w, length_w, tf_w) in dlg._widgets.items():
        fam_w.setCurrentText("EMA")
        length_w.setValue(20)
        tf_w.setCurrentText("1H")

    dlg.accept()
    assert accepted, "Assignment accepted callback not invoked"
    assert "NASDAQ:TSLA" in accepted
    assert accepted["NASDAQ:TSLA"][0] == "EMA"









