import logging
from typing import Optional, Callable, Tuple, Any, Dict
from datetime import datetime

from PySide6 import QtWidgets, QtNetwork, QtCore, QtGui
import pyqtgraph as pg
import numpy as np

from VizDebug.var_server import VariableServer

logger = logging.getLogger(__name__)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Viz Debug")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout()

        self.plot = pg.PlotWidget()
        self.plot.setAntialiasing(True)
        layout.addWidget(self.plot)

        hlayout = QtWidgets.QHBoxLayout()

        self.lineEditQuery = QtWidgets.QLineEdit()
        self.lineEditQuery.returnPressed.connect(
            lambda: self.eval_query(self.lineEditQuery.text())
        )
        hlayout.addWidget(self.lineEditQuery)

        self.buttonQuery = QtWidgets.QPushButton("Eval")
        self.buttonQuery.clicked.connect(
            lambda: self.eval_query(self.lineEditQuery.text())
        )
        hlayout.addWidget(self.buttonQuery)
        layout.addLayout(hlayout)

        self.labelOutput = QtWidgets.QLabel()
        layout.addWidget(self.labelOutput)

        central.setLayout(layout)

        self.server = VariableServer()
        self.server.values_updated.connect(self.var_update)
        self.server.socket_error.connect(
            lambda err: self.statusBar().showMessage(str(err))
        )
        self.server.communication_error.connect(
            lambda err: self.statusBar().showMessage(str(err))
        )

        if not self.server.listen(port=4444):
            reason = self.server.errorString()
            QtWidgets.QMessageBox.critical(
                self, "Viz Debug", "Unable to start the TCP server.\n" + reason
            )
            self.close()
            return

        for ip_address in QtNetwork.QNetworkInterface.allAddresses():
            if (
                ip_address != QtNetwork.QHostAddress.SpecialAddress.LocalHost
                and ip_address.toIPv4Address != 0
            ):
                break
        else:
            ip_address = QtNetwork.QHostAddress(
                QtNetwork.QHostAddress.SpecialAddress.LocalHost
            )

        ip_address = ip_address.toString()
        port = self.server.serverPort()

        self.statusBar().showMessage(f"Serving on {ip_address}:{port}")
        self.statusLabels = dict[str, QtWidgets.QLabel]()
        update_timer = QtCore.QTimer(self, interval=1000)
        update_timer.timeout.connect(self.update_time_info)
        update_timer.start()

        self.last_query = ""

    @QtCore.Slot(str)
    def var_update(self, identity: str) -> None:
        if identity not in self.statusLabels.keys():
            label = QtWidgets.QLabel(f"{identity}: now")
            self.statusLabels[identity] = label
            self.statusBar().addPermanentWidget(label)
        self.eval_query(self.last_query)

    @QtCore.Slot()
    def update_time_info(self):
        now = datetime.now()
        for identity, label in self.statusLabels.items():
            delta = now - self.server.time_stamps[identity]
            if delta.seconds < 60:
                label.setText(
                    f"{identity}: {delta.seconds} second{'s' if delta.seconds == 1 else ''} ago"
                )
            elif delta.seconds < 60 * 60:
                minutes = delta.seconds // 60
                label.setText(
                    f"{identity}: {minutes} minute{'s' if minutes > 1 else ''} ago"
                )
            else:
                label.setText(f"{identity}: a long time ago")

    @QtCore.Slot(str)
    def eval_query(self, query: str):
        self.last_query = query
        try:
            value: Any = eval(query, {"np": np}, self.server.variable_store)
        except Exception as e:
            value: Any = e
        match value:
            case list() | np.ndarray():
                p = self.plot.plot(value, clear=True)
                self.plot.fitInView(p)
            case _:
                pass
        value = str(value)
        self.labelOutput.setToolTip(value)
        elided = QtGui.QFontMetrics(self.labelOutput.font()).elidedText(
            value, QtCore.Qt.TextElideMode.ElideMiddle, self.labelOutput.width()
        )
        self.labelOutput.setText(elided)

    @QtCore.Slot()
    def deleteLater(self) -> None:
        self.server.deleteLater()
        return super().deleteLater()
