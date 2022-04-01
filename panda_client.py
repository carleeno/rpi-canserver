import logging
import socket
import struct
from time import time
from typing import Tuple

from can import Message
from can.util import channel2int

from logging_setup import setup_logging

setup_logging()


# Not actually a client, just represents a client for panda_server.py
class PandaClient:
    _ack_packet = struct.pack("<IIQ", 0x006 << 21, 15 << 4, 0)
    _udp_socket: socket.socket
    address: Tuple[str, int]
    connected: bool
    last_seen: float
    is_v2: bool
    v2_send_all: bool
    v2_filter_list: Tuple[list]

    def __init__(
        self, socket: socket.socket, data: bytes, address: Tuple[str, int]
    ) -> None:
        self.logger = logging.getLogger(f"panda_client.{address[0]}")
        self._udp_socket = socket
        self.address = address
        self.connected = False
        self.is_v2 = False
        self.v2_send_all = False
        self.v2_filter_list = ([], [])
        self.process(data, address)

    def process(self, data: bytes, address: Tuple[str, int]):
        self.address = address
        self.last_seen = time()
        try:
            decoded = data.decode()
        except UnicodeDecodeError:
            decoded = "(raw)"
        self.logger.debug(f"received: {decoded}")
        if decoded.lower() == "hello":
            if not self.connected:
                self._connect_v1()
        elif decoded.lower() == "ehllo":
            if not self.connected or not self.is_v2:
                self._connect_v2()
        elif not self.connected or not self.is_v2:
            return
        elif decoded.lower() == "bye":
            self._disconnect()
        elif data[0] == 0x0F:
            self._filter_add(data)
        elif data[0] == 0x0E:
            self._filter_del(data)
        elif data[0] == 0x0C:
            self._filter_all()
        elif data[0] == 0x18:
            self._filter_clear()

    def alive_check(self):
        if self.connected and int(time() - self.last_seen) > 10:
            self.logger.info("Hearbeat expired")
            self._disconnect()

    def send_frame(self, frame: Message) -> bool:
        if not self.connected:
            return False
        frame_id = frame.arbitration_id
        bus = channel2int(frame.channel)
        if (not self.is_v2) or self.v2_send_all or frame_id in self.v2_filter_list[bus]:
            data = struct.pack(
                "<II",
                frame.arbitration_id << 21,
                (frame.dlc & 0x0F) | (channel2int(frame.channel) << 4),
            )
            data += struct.pack("<%dB" % frame.dlc, *frame.data)
            self._send_raw(data)
            return True
        return False

    def _send_raw(self, data: bytes):
        if data == self._ack_packet:
            self.logger.debug("Sending v2 ack packet")
        self._udp_socket.sendto(data, self.address)

    def _connect_v1(self):
        self.logger.info(f"New v1 connection from {self.address[0]}:{self.address[1]}")
        self.connected = True
        # send a v2 ack just in case the client can upgrade
        self._send_raw(self._ack_packet)

    def _connect_v2(self):
        self.logger.info(f"New v2 connection from {self.address[0]}:{self.address[1]}")
        self.connected = True
        self.is_v2 = True
        self._send_raw(self._ack_packet)

    def _disconnect(self):
        self.logger.info("Disconnected")
        self.connected = False
        self.is_v2 = False
        self.v2_send_all = False
        self.v2_filter_list = ([], [])

    def _filter_add(self, data: bytes):
        for byte_chunk in self._divide_bytes(data[1:], 3):
            buses, frame_id = self._get_filter_info_from(byte_chunk)
            for bus in buses:
                self.v2_filter_list[bus].append(frame_id)
        self.logger.debug(
            f"Filter add command received. Filter is now: {self.v2_filter_list}"
        )

    def _filter_del(self, data: bytes):
        for byte_chunk in self._divide_bytes(data[1:], 3):
            buses, frame_id = self._get_filter_info_from(byte_chunk)
            for bus in buses:
                try:
                    self.v2_filter_list[bus].remove(frame_id)
                except ValueError:
                    pass
        self.logger.debug(
            f"Filter del command received. Filter is now: {self.v2_filter_list}"
        )

    def _divide_bytes(self, bts: bytes, chunk_size: int):
        for i in range(0, len(bts), chunk_size):
            yield bts[i : i + chunk_size]

    def _get_filter_info_from(self, byte_chunk: bytes):
        bus_id = byte_chunk[0]
        frame_id = int.from_bytes(byte_chunk[1:], "big")
        self.logger.debug(f"Filter item: bus={bus_id}, frame={frame_id}")
        if bus_id in [-1, 255]:
            buses = [0, 1]
        else:
            buses = [bus_id]
        return buses, frame_id

    def _filter_all(self):
        self.v2_send_all = True
        self.logger.debug("Filter (include) all command received")

    def _filter_clear(self):
        self.v2_send_all = False
        self.v2_filter_list = ([], [])
        self.logger.debug("Filter clear command received")
