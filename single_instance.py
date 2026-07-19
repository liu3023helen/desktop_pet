"""Single-instance coordination for the desktop application."""
import logging

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

logger = logging.getLogger(__name__)


class SingleInstanceGuard(QObject):
    """Keep one app process and notify it when another launch is attempted."""

    activation_requested = pyqtSignal()

    def __init__(self, server_name: str = "DesktopPet.SingleInstance", parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._handle_connections)
        self._owns_server = False

    def acquire(self) -> bool:
        if self._owns_server:
            return True
        if self._notify_existing_instance():
            return False

        QLocalServer.removeServer(self.server_name)
        if self._server.listen(self.server_name):
            self._owns_server = True
            logger.info("已取得应用单实例锁")
            return True

        # Another process may have won the startup race after our first probe.
        if self._notify_existing_instance():
            return False
        logger.error(f"无法创建应用单实例服务: {self._server.errorString()}")
        return False

    def _notify_existing_instance(self) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(300):
            socket.abort()
            return False
        socket.write(b"activate")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        logger.info("检测到已有实例，已发送激活请求")
        return True

    def _handle_connections(self) -> None:
        handled = False
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.readAll()
            socket.disconnectFromServer()
            socket.deleteLater()
            handled = True
        if handled:
            logger.info("收到第二次启动请求，激活现有窗口")
            self.activation_requested.emit()

    def release(self) -> None:
        if not self._owns_server:
            return
        self._server.close()
        QLocalServer.removeServer(self.server_name)
        self._owns_server = False
        logger.info("已释放应用单实例锁")
