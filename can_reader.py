import logging
import os
import signal
from multiprocessing import Process, Queue
from queue import Full

import can
import cantools


class CanReader:
    def __init__(self, channel: str = "can0"):
        """Create can reader instance. Nothing happens until you call start_reading().

        Args:
            channel: can0 or can1 (if you have a pican duo)
        """
        self.__decode_buffer = Queue(1000)
        self.decoded_messages = Queue(100)
        self.logger_out = Queue(10000)

        self.__last_60s_msg_count = 0
        self.__last_msg_count_time = 0.0

        self.channel = channel
        self.running = False
        self.__decode_enabled = False
        self.bus_name = None

        self.__log = logging.getLogger(f"{__name__}.{channel}")

    def __safe_can_rx(self):
        try:
            return self.__bus.recv()
        except can.CanError as e:
            self.__log.error(f"Error reading from {self.channel}: {e}")

    def __write_to_queues(self):
        try:
            while True:
                message = self.__safe_can_rx()
                if not message:
                    continue
                try:
                    self.__decode_buffer.put_nowait(message)
                except Full:
                    pass
                try:
                    self.logger_out.put_nowait(message)
                except Full:
                    pass
                self.__log_fps(message.timestamp)
        except Exception as e:
            self.__log.exception(e)

    def __log_fps(self, msg_ts):
        self.__last_60s_msg_count += 1
        if msg_ts > self.__last_msg_count_time + 60:
            self.__log.debug(f"Avg. FPS: {self.__last_60s_msg_count/60:.2f}")
            self.__last_60s_msg_count = 0
            self.__last_msg_count_time = msg_ts

    def __decoder_task(self):
        while True:
            message = self.__decode_buffer.get()
            self.__decode(message)

    def __decode(self, message: can.Message):
        if message.arbitration_id not in self.__decode_filter:
            return
        try:
            if (
                self.__last_decoded_time[message.arbitration_id]
                + self.__decode_interval
            ) > message.timestamp:
                return  # Don't decode if interval hasn't elapsed
        except KeyError:
            pass
        self.__last_decoded_time[message.arbitration_id] = message.timestamp

        try:
            db_msg = self.db.get_message_by_frame_id(message.arbitration_id)
        except KeyError:
            return  # ignore messages that aren't defined in the db
        if self.bus_name not in db_msg.senders:
            return

        try:
            decoded_data = db_msg.decode(message.data)
        except Exception as e:
            if db_msg.name not in self.__failed_messages:
                self.__failed_messages.append(db_msg.name)
                self.__log.warn(f"Failed to decode {db_msg.name}: {e}")
            return
        try:
            self.decoded_messages.put_nowait(
                {
                    "data": decoded_data,
                    "name": db_msg.name,
                    "msg_def": db_msg,
                    "timestamp": message.timestamp,
                }
            )
        except Full:
            pass

    def setup_decoding(
        self, dbc_file: str, bus_name: str, include_list: list, interval: float
    ):
        """Setup and enable message decoding by providing a dbc file and filter.

        Args:
            dbc_file: provide a filepath to define message decoding
            bus_name: specify this bus' name (must be included in the dbc file)
            include_list: str list of message names to decode, other messages will be ignored
            interval: period in seconds to wait before decoding next message of same id
        """
        if not include_list:
            raise Exception("include_list must not be empty")

        self.db = cantools.db.load_file(dbc_file)

        db_buses = [msg.senders[0] for msg in self.db.messages]
        db_buses = list(set(db_buses))
        if bus_name not in db_buses:
            raise Exception(f"You must specify bus_name as one of: {db_buses}")
        self.bus_name = bus_name

        self.__decode_filter = []
        for name in include_list:
            try:
                db_msg = self.db.get_message_by_name(name)
                self.__decode_filter.append(db_msg.frame_id)
            except KeyError:
                raise Exception(f"Filter message '{name}' not found in dbc.")

        # remove duplicates:
        self.__decode_filter = list(set(self.__decode_filter))

        self.__decode_interval = float(interval)
        self.__decode_enabled = True
        self.__log.debug(f"Decoding {len(self.__decode_filter)} filtered messages.")

    def start_reading(self):
        """This non-blocking method starts the can reader."""
        if self.running:
            self.__log.warning("can_reader already started.")
            return
        os.system(f"sudo /sbin/ip link set {self.channel} up type can bitrate 500000")
        self.__bus = can.interface.Bus(channel=self.channel, bustype="socketcan")

        s = signal.signal(signal.SIGINT, signal.SIG_IGN)
        if self.__decode_enabled:
            self.__failed_messages = []
            self.__last_decoded_time = {}
            self.__decode_thread = Process(target=self.__decoder_task)
            self.__decode_thread.start()

        self.__queue_write_thread = Process(target=self.__write_to_queues)
        self.__queue_write_thread.start()
        signal.signal(signal.SIGINT, s)
        self.running = True
        self.__log.debug("Started reading.")

    def stop_reading(self):
        """This cleanly stops all threads."""
        if not self.running:
            self.__log.warning("can_reader already stopped.")
            return
        self.__log.debug("Stopping can_reader...")
        self.__queue_write_thread.kill()
        if self.__decode_enabled:
            self.__decode_thread.kill()
        os.system(f"sudo /sbin/ip link set {self.channel} down")
        self.running = False
        self.__log.debug("Stopped reading.")
