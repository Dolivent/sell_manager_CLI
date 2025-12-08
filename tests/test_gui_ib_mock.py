import pytest

def _make_app():
    try:
        from qtpy import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        return app
    except Exception:
        return None


def test_ib_connected_indicator(monkeypatch):
    app = _make_app()
    if app is None:
        pytest.skip("Qt not available in test environment")

    try:
        from src.sellmanagement.gui.main_window import MainWindow
    except Exception:
        pytest.skip("GUI import failed in test environment")

    mw = MainWindow()

    # simulate worker connected signal
    mw._on_ib_connected(True)
    style = mw._status_label.styleSheet()
    assert "color: green" in style

    mw._on_ib_connected(False)
    style2 = mw._status_label.styleSheet()
    assert "color: red" in style2


