import struct
import unittest
from unittest.mock import patch

from time_sync import (
    DEFAULT_NTP_SERVERS,
    TimeSyncService,
    _pack_ntp_timestamp,
)


class _FakeNtpSocket:
    def __init__(self, response_builder):
        self._response_builder = response_builder
        self.request = None
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def connect(self, address):
        self.address = address

    def send(self, request):
        self.request = request

    def recv(self, size):
        return self._response_builder(self.request)

    def close(self):
        self.closed = True


def _response(request, receive_time, transmit_time, *, mode=4, stratum=2):
    packet = bytearray(48)
    packet[0] = (4 << 3) | mode
    packet[1] = stratum
    packet[24:32] = request[40:48]
    packet[32:40] = _pack_ntp_timestamp(receive_time)
    packet[40:48] = _pack_ntp_timestamp(transmit_time)
    return bytes(packet)


class TimeSyncValidationTests(unittest.TestCase):
    def test_valid_response_uses_full_ntp_offset_formula(self):
        t1 = 1_700_000_000.0
        t4 = t1 + 0.3
        fake = _FakeNtpSocket(
            lambda request: _response(request, t1 + 2.1, t1 + 2.2)
        )
        with patch("time_sync.socket.socket", return_value=fake), patch(
            "time_sync.time"
        ) as time_module:
            time_module.time.side_effect = [t1, t4]
            offset = TimeSyncService()._query_ntp("ntp.example")

        self.assertAlmostEqual(offset, 2.0, places=3)
        self.assertTrue(fake.closed)

    def test_mismatched_request_timestamp_is_rejected(self):
        t1 = 1_700_000_000.0

        def bad_response(request):
            packet = bytearray(_response(request, t1 + 0.1, t1 + 0.2))
            packet[24:32] = struct.pack("!Q", 0)
            return bytes(packet)

        fake = _FakeNtpSocket(bad_response)
        with patch("time_sync.socket.socket", return_value=fake), patch(
            "time_sync.time"
        ) as time_module:
            time_module.time.side_effect = [t1, t1 + 0.3]
            offset = TimeSyncService()._query_ntp("ntp.example")

        self.assertIsNone(offset)
        self.assertTrue(fake.closed)

    def test_invalid_server_mode_is_rejected(self):
        t1 = 1_700_000_000.0
        fake = _FakeNtpSocket(
            lambda request: _response(request, t1 + 0.1, t1 + 0.2, mode=3)
        )
        with patch("time_sync.socket.socket", return_value=fake), patch(
            "time_sync.time"
        ) as time_module:
            time_module.time.side_effect = [t1, t1 + 0.3]
            offset = TimeSyncService()._query_ntp("ntp.example")

        self.assertIsNone(offset)

    def test_configured_server_keeps_default_fallbacks(self):
        service = TimeSyncService(server="custom.example")

        self.assertEqual(service._servers[0], "custom.example")
        self.assertEqual(service._servers[1:], DEFAULT_NTP_SERVERS)


if __name__ == "__main__":
    unittest.main()
