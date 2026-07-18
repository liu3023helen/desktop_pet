"""
网络时间校准服务 - 使用NTP协议获取准确时间
不修改系统时间，仅提供偏移量供提醒引擎使用
"""
import socket
import struct
import time
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


class TimeSyncService:
    """NTP时间同步服务"""

    def __init__(self, server: str = None):
        self._server = server or DEFAULT_NTP_SERVERS[0]
        self._servers = [server] if server else DEFAULT_NTP_SERVERS
        self._last_offset: Optional[float] = None
        self._last_sync_time: Optional[datetime] = None

    def _query_ntp(self, host: str) -> Optional[float]:
        """
        发送NTP请求并计算时间偏移量
        返回: ntp_time - local_time （秒），None表示失败
        """
        try:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.settimeout(NTP_TIMEOUT)

            # 构建NTP请求包（48字节，版本3，模式3=客户端）
            ntp_packet = b'\x1b' + b'\x00' * 47

            # 记录发送时间
            send_time = time.time()

            client.sendto(ntp_packet, (host, NTP_PORT))
            response, _ = client.recvfrom(256)

            # 记录接收时间
            recv_time = time.time()

            client.close()

            if len(response) < 48:
                logger.warning(f"NTP响应过短: {len(response)} 字节")
                return None

            # 解析服务器发送时间戳（第32-39字节，transmit timestamp）
            transmit_timestamp = struct.unpack("!Q", response[40:48])[0]
            transmit_timestamp /= 2**32  # 转换为浮点秒数
            transmit_timestamp -= NTP_EPOCH_OFFSET  # 转换为Unix时间戳

            # 计算偏移量
            # offset = ((t2 - t1) + (t3 - t4)) / 2
            # t1 = send_time (客户端发送), t2 = 服务器收到(未知)
            # t3 = transmit_timestamp (服务器发送), t4 = recv_time (客户端收到)
            # 简化: offset ≈ t3 - (t1 + t4) / 2
            local_avg = (send_time + recv_time) / 2
            offset = transmit_timestamp - local_avg

            round_trip = recv_time - send_time
            logger.info(f"NTP [{host}]: 偏移={offset:.3f}s, RTT={round_trip:.3f}s")

            return offset

        except socket.timeout:
            logger.warning(f"NTP超时: {host}")
        except socket.gaierror as e:
            logger.warning(f"NTP域名解析失败: {host}, {e}")
        except Exception as e:
            logger.warning(f"NTP查询异常: {host}, {e}")

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
