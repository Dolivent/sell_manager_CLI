"""Entry point to run the GUI."""
from qtpy import QtWidgets
from .main_window import MainWindow
import sys

def main():
    app = QtWidgets.QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()


