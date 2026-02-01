import logging
from enum import Enum
from queue import Queue
from typing import Dict, Any, Optional, Tuple
from json import loads, JSONDecodeError
from datetime import datetime

from PySide6 import QtCore, QtNetwork

logger = logging.getLogger(__name__)


class CommunicationError(Enum):
    NoSize = 0
    UnderSize = 1
    OverSize = 2
    Timeout = 3
    DecodeError = 4
    Malformed = 5


class VariableReceiver(QtCore.QObject):
    finished = QtCore.Signal(int)
    socket_error = QtCore.Signal(QtNetwork.QTcpSocket.SocketError)
    communication_error = QtCore.Signal(CommunicationError)
    message_received = QtCore.Signal(int)

    def __init__(self, id: int, handle: int, queue: Queue[Dict[str, Any]]) -> None:
        super().__init__()

        self.id = id
        self.handle = handle
        self.queue = queue
        self.socket: Optional[QtNetwork.QAbstractSocket] = None
        self.buffer = QtCore.QByteArray()
        self.timeout = QtCore.QTimer(self, singleShot=True, interval=500)
        self.timeout.timeout.connect(self.handle_timeout)

    @QtCore.Slot()
    def read_block(self):
        assert self.socket is not None
        self.buffer.append(self.socket.readAll())

    @QtCore.Slot()
    def on_disconnect(self):
        self.timeout.stop()
        if self.buffer.length() < 4:
            self.communication_error.emit(CommunicationError.NoSize)
            self.finished.emit(self.id)
            return
        size = int.from_bytes(self.buffer.data()[:4], signed=False)

        if size + 4 < self.buffer.length():
            self.communication_error.emit(CommunicationError.UnderSize)
            self.finished.emit(self.id)
            return
        elif size + 4 > self.buffer.length():
            self.communication_error.emit(CommunicationError.OverSize)
            self.finished.emit(self.id)
            return

        try:
            message = loads(self.buffer.data()[4:])
        except JSONDecodeError as e:
            logger.error(f"Failed to decode json message: {e}")
            self.communication_error.emit(CommunicationError.DecodeError)
            self.finished.emit(self.id)
            return

        self.queue.put(message)
        self.message_received.emit(self.id)

    @QtCore.Slot(QtNetwork.QTcpSocket.SocketError)
    def handle_error(self, error: QtNetwork.QTcpSocket.SocketError):
        if error is not QtNetwork.QTcpSocket.SocketError.RemoteHostClosedError:
            self.socket_error.emit(error)
            self.finished.emit(self.handle)

    @QtCore.Slot()
    def handle_timeout(self):
        self.communication_error.emit(CommunicationError.Timeout)
        self.finished.emit(self.handle)

    @QtCore.Slot()
    def open_socket(self):
        tcp_socket = QtNetwork.QTcpSocket()
        self.socket = tcp_socket

        if not tcp_socket.setSocketDescriptor(self.handle):
            self.socket_error.emit(tcp_socket.error())
            self.finished.emit(self.id)
            return

        tcp_socket.readyRead.connect(self.read_block)
        tcp_socket.errorOccurred.connect(self.handle_error)
        tcp_socket.disconnected.connect(self.on_disconnect)
        self.timeout.start()


class VariableServer(QtNetwork.QTcpServer):
    socket_error = QtCore.Signal(QtNetwork.QTcpSocket.SocketError)
    communication_error = QtCore.Signal(ConnectionError)
    values_updated = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self.threads = dict[int, Tuple[QtCore.QThread, VariableReceiver]]()
        self.queue = Queue[Dict[str, Any]]()

        self.variable_store = dict[str, Any]()
        self.time_stamps = dict[str, datetime]()

        self.socket_error.connect(self.handle_socket_error)
        self.communication_error.connect(self.handle_communication_error)

        # thread garbage collection, dirty hack
        self.garbage = QtCore.QTimer(self, singleShot=False, interval=1000)
        self.garbage.timeout.connect(self.free_threads)
        self.garbage.start()

        self.id = 0

    @QtCore.Slot()
    def handle_message(self, id: int):
        # this function does not necessarily receive the message that caused the signal, we do not care
        msg = self.queue.get()
        try:
            identity = msg["identity"]
            variables = msg["vars"]
        except KeyError:
            print(msg)
            self.communication_error.emit(CommunicationError.Malformed)
            return

        if not isinstance(identity, str):
            print(msg)
            self.communication_error.emit(CommunicationError.Malformed)
            return

        self.variable_store[identity] = variables
        self.time_stamps[identity] = datetime.now()

        _, w = self.threads[id]
        w.finished.emit(id)
        self.values_updated.emit(identity)

    def free_threads(self):
        n_cleaned = 0
        for k, (t, _) in list(self.threads.items()):
            if t.isFinished():
                n_cleaned += 1
                del self.threads[k]
        logger.info(f"Cleaned {n_cleaned} threads")

    def incomingConnection(self, handle: int) -> None:
        thread = QtCore.QThread()

        worker = VariableReceiver(self.id, handle, self.queue)
        worker.moveToThread(thread)
        thread.started.connect(worker.open_socket)
        worker.finished.connect(thread.quit)

        worker.message_received.connect(self.handle_message)
        worker.socket_error.connect(self.socket_error.emit)
        worker.communication_error.connect(self.communication_error.emit)

        thread.start()

        self.threads[self.id] = (thread, worker)
        self.id += 1

    def handle_communication_error(self, err: CommunicationError):
        logger.error(err)

    def handle_socket_error(self, err: QtNetwork.QTcpSocket.SocketError):
        logger.error(err)

    def deleteLater(self):
        for t, _ in self.threads.values():
            t.quit()
        super().deleteLater()
