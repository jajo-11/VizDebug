from PySide6 import QtWidgets

from .main_window import MainWindow

app = QtWidgets.QApplication([])
main_window = MainWindow()
app.aboutToQuit.connect(main_window.deleteLater)
main_window.show()

app.exec()
