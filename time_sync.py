"""
网络时间校准服务 - 使用NTP协议获取准确时间
不修改系统时间，仅提供偏移量供提醒引擎使用
"""
import socket
import struct
import time
import math
from datetime import datetime
from typing import Optional

import logging

logger = logging.getLogger("DesktopPet")

# NTP服务器列表（优先级排序）
DEFAULT_NTP_SERVERS = [
    "ntp.aliyun.com",       # 阿里云NTP（国内首选）
    "time.windows.com",     # Windows NTP
    "pool.ntp.org",         # 国际NTP池
]

# NTP协议参数
NTP_PORT = 123
NTP_TIMEOUT = 5  # 秒
# NTP epoch offset: seconds between 1900-01-01 and 1970-01-01
NTP_EPOCH_OFFSET = 2208988800
MAX_ABS_OFFSET_SECONDS = 86400


def _pack_ntp_timestamp(unix_time: float) -> bytes:
    ntp_time = unix_time + NTP_EPOCH_OFFSET
    seconds = int(ntp_time)
    fraction = int((ntp_time - seconds) * (2 ** 32))
    return struct.pack("!II", seconds, fraction)


def _unpack_ntp_timestamp(raw: bytes) -> float:
    seconds, fraction = struct.unpack("!II", raw)
    return seconds + fraction / (2 ** 32) - NTP_EPOCH_OFFSET


class TimeSyncService:
    """NTP时间同步服务"""

    def __init__(self, server: str = None):
        self._servers = list(DEFAULT_NTP_SERVERS)
        if server:
            self._servers = [server] + [item for item in self._servers if item != server]
        self._last_offset: Optional[float] = None
        self._last_sync_time: Optional[datetime] = None

    def _query_ntp(self, host: str) -> Optional[float]:
        """
        发送NTP请求并计算时间偏移量
        返回: ntp_time - local_time （秒），None表示失败
        """
        client = None
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(NTP_TIMEOUT)

            # 记录发送时间
            send_time = time.time()
            ntp_packet = bytearray(48)
            ntp_packet[0] = 0x23  # LI=0, version=4, mode=3 (client)
            ntp_packet[40:48] = _pack_ntp_timestamp(send_time)

            # Connected UDP only accepts responses from the selected endpoint.
            client.connect((host, NTP_PORT))
            client.send(bytes(ntp_packet))
            response = client.recv(256)

            # 记录接收时间
            recv_time = time.time()

            if len(response) < 48:
                logger.warning(f"NTP响应过短: {len(response)} 字节")
                return None

            leap = response[0] >> 6
            version = (response[0] >> 3) & 0x07
            mode = response[0] & 0x07
            stratum = response[1]
            if leap == 3 or version < 3 or mode != 4 or not 1 <= stratum <= 15:
                logger.warning(
                    f"NTP响应状态无效: leap={leap}, version={version}, "
                    f"mode={mode}, stratum={stratum}"
                )
                return None

            if response[24:32] != bytes(ntp_packet[40:48]):
                logger.warning("NTP响应未匹配当前请求")
                return None

            receive_timestamp = _unpack_ntp_timestamp(response[32:40])
            transmit_timestamp = _unpack_ntp_timestamp(response[40:48])
            if transmit_timestamp <= 0:
                logger.warning("NTP响应缺少有效发送时间戳")
                return None

            offset = (
                (receive_timestamp - send_time)
                + (transmit_timestamp - recv_time)
            ) / 2
            if not math.isfinite(offset) or abs(offset) > MAX_ABS_OFFSET_SECONDS:
                logger.warning(f"NTP偏移超出安全范围: {offset}")
                return None

            round_trip = (recv_time - send_time) - (
                transmit_timestamp - receive_timestamp
            )
            logger.info(f"NTP [{host}]: 偏移={offset:.3f}s, RTT={round_trip:.3f}s")

            return offset

        except socket.timeout:
            logger.warning(f"NTP超时: {host}")
        except socket.gaierror as e:
            logger.warning(f"NTP域名解析失败: {host}, {e}")
        except Exception as e:
            logger.warning(f"NTP查询异常: {host}, {e}")
        finally:
            if client is not None:
                client.close()

        return None

    def sync_once(self) -> Optional[float]:
        """
        执行一次时间同步
        返回: 时间偏移量（秒），None表示所有服务器都失败
        """
        for server in self._servers:
            logger.info(f"正在查询NTP服务器: {server}")
            offset = self._query_ntp(server)
            if offset is not None:
                self._last_offset = offset
                self._last_sync_time = datetime.now()
                logger.info(f"时间校准成功: 偏移={offset:.3f}秒, 服务器={server}")
                return offset

        logger.error("所有NTP服务器均不可用")
        return None

    def get_offset(self) -> Optional[float]:
        """获取上次成功同步的偏移量"""
        return self._last_offset

    def get_last_sync_time(self) -> Optional[datetime]:
        """获取上次成功同步的时间"""
        return self._last_sync_time

    def needs_resync(self, max_age_seconds: int = 86400) -> bool:
        """检查是否需要重新同步（默认超过24小时需要重同步）"""
        if self._last_sync_time is None:
            return True
        age = (datetime.now() - self._last_sync_time).total_seconds()
        return age > max_age_seconds
