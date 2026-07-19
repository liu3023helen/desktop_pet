"""Windows session lock and unlock event monitor."""
import ctypes
import logging
import sys
from ctypes import wintypes

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QWidget

logger = logging.getLogger(__name__)

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0


class _WindowsSessionApi:
    """Small ctypes wrapper around the WTS session notification API."""

    def __init__(self):
        self.available = sys.platform == "win32"
        self._api = None
        if not self.available:
            return

        try:
            self._api = ctypes.WinDLL("wtsapi32", use_last_error=True)
            self._api.WTSRegisterSessionNotification.argtypes = [
                wintypes.HWND,
                wintypes.DWORD,
            ]
            self._api.WTSRegisterSessionNotification.restype = wintypes.BOOL
            self._api.WTSUnRegisterSessionNotification.argtypes = [wintypes.HWND]
            self._api.WTSUnRegisterSessionNotification.restype = wintypes.BOOL
        except (AttributeError, OSError) as error:
            logger.warning(f"Windows 会话监测不可用: {error}")
            self.available = False
            self._api = None

    def register(self, window_handle: int) -> bool:
        if not self.available or self._api is None:
            return False
        if self._api.WTSRegisterSessionNotification(
            wintypes.HWND(window_handle),
            NOTIFY_FOR_THIS_SESSION,
        ):
            return True
        error_code = ctypes.get_last_error()
        logger.error(f"注册 Windows 会话通知失败: error={error_code}")
        return False

    def unregister(self, window_handle: int) -> None:
        if not self.available or self._api is None:
            return
        if not self._api.WTSUnRegisterSessionNotification(
            wintypes.HWND(window_handle)
        ):
            error_code = ctypes.get_last_error()
            logger.warning(f"注销 Windows 会话通知失败: error={error_code}")


class SessionMonitor(QWidget):
    """Receive Windows lock/unlock events through a hidden native window."""

    locked = pyqtSignal()
    unlocked = pyqtSignal()
    lock_state_changed = pyqtSignal(bool)

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self._api = api if api is not None else _WindowsSessionApi()
        self._registered = False
        self._window_handle = None
        self._is_locked = False
        self.setWindowFlags(Qt.Tool)
        self.setAttribute(Qt.WA_DontShowOnScreen, True)

    @property
    def is_locked(self) -> bool:
        return self._is_locked

    @property
    def is_registered(self) -> bool:
        return self._registered

    def start(self) -> bool:
        if self._registered:
            return True
        self._window_handle = int(self.winId())
        self._registered = bool(self._api.register(self._window_handle))
        if self._registered:
            logger.info("Windows 会话锁定/解锁监测已启动")
        else:
            logger.warning("Windows 会话锁定/解锁监测未启动")
        return self._registered

    def stop(self) -> None:
        if not self._registered or self._window_handle is None:
            return
        self._api.unregister(self._window_handle)
        self._registered = False
        logger.info("Windows 会话锁定/解锁监测已停止")

    def _handle_session_change(self, event_code: int) -> bool:
        if event_code == WTS_SESSION_LOCK:
            locked = True
        elif event_code == WTS_SESSION_UNLOCK:
            locked = False
        else:
            return False

        if locked == self._is_locked:
            return True
        self._is_locked = locked
        self.lock_state_changed.emit(locked)
        if locked:
            self.locked.emit()
        else:
            self.unlocked.emit()
        return True

    def nativeEvent(self, event_type, message):
        try:
            native_message = wintypes.MSG.from_address(int(message))
            if native_message.message == WM_WTSSESSION_CHANGE:
                self._handle_session_change(int(native_message.wParam))
        except (TypeError, ValueError):
            logger.exception("解析 Windows 会话通知失败")
        return False, 0

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)
