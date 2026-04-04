"""Entry point to run the GUI."""
from qtpy import QtWidgets
from .main_window import MainWindow
import sys

from ..log_config import setup_logging


def main():
    setup_logging()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    # Ensure the app exec runs and returns when window closed
    return app.exec_()

if __name__ == "__main__":
    sys.exit(main())





