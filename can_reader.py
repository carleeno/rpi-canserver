import logging
import os
from queue import Empty, Full, Queue
from threading import Thread
from time import sleep

import can
import cantools


class CanReader:
    """Class for getting can messages from a specified bus.
    Incoming messages are buffered for stability, a full buffer will drop messages.

    Messages are also decoded if provided a dbc file.
    """

    buffer_usage: int
    """Smoothed buffer usage for monitoring performance. Fast rise, slow fall (10/sec)."""
    channel: str
    """The name of the can channel this reader was init'd with."""
    decoded_messages: dict
    """Contains decoded messages if a dbc_file is specified."""
    failed_messages: dict
    """Contains message names which failed to decode, and their reason"""
    message_queue: Queue
    """Contains raw can messages (can.Message). Will stagnate if full."""

    def __init__(self, channel: str = "can0", dbc_file: str = "", bus_name: str = None):
        """Create can reader instance. Nothing happens until you call start().

        Args:
            channel: can0 or can1 (if you have a pican duo)
            dbc_file: optionally provide a filepath to define message decoding
        """
        self.__main_thread = Thread(target=self.__main_task)
        self.__stop = False
        self.channel = channel
        self.message_queue = Queue(100)

        # Buffer setup
        self.__can_rx_buffer = Queue(100)
        self.__buffer_write_thread = Thread(target=self.__write_to_buffer)
        self.buffer_usage = 0
        self.__smooth_buffer_usage_thread = Thread(target=self.__smooth_buffer_usage)

        # Decoding setup
        self.__bus_name = bus_name
        self.__decode_filter = []
        self.decoded_messages = {}
        self.failed_messages = {}
        if dbc_file:
            self.__db = cantools.db.load_file(dbc_file)
        else:
            self.__db = None
        if self.__db:
            buses = [msg.senders[0] for msg in self.__db.messages]
            buses = list(set(buses))
            if bus_name not in buses:
                raise Exception(f"You must specify bus_name as one of: {buses}")

    def __safe_can_rx(self):
        try:
            message = self.__bus.recv(timeout=1)
        except can.CanError as e:
            message = None
            logging.error(f"Error reading from {self.channel}: {e}")

        return message

    def __write_to_buffer(self):
        while True:
            if self.__stop:
                return

            message = self.__safe_can_rx()
            if not message:
                continue

            try:
                self.__can_rx_buffer.put(message, block=False)
            except Full:
                logging.error("Dropping message, buffer is full!")

            self.buffer_usage = max((self.__can_rx_buffer.qsize(), self.buffer_usage))

    def __smooth_buffer_usage(self):
        while True:
            if self.buffer_usage > 0:
                self.buffer_usage += -1
            if self.__stop:
                return
            sleep(0.1)

    def __main_task(self):
        while True:
            try:
                message = self.__can_rx_buffer.get(block=True, timeout=1)
            except Empty:
                message = None
                if self.__stop:
                    return

            if message:
                try:
                    self.message_queue.put(message, block=False)
                except Full:
                    pass  # we don't care if nobody is using this external queue
                self.__decode(message)

    def __decode(self, message: can.Message):
        if not self.__db:
            return
        if self.__decode_filter and message.arbitration_id not in self.__decode_filter:
            return
        try:
            db_msg = self.__db.get_message_by_frame_id(message.arbitration_id)
        except KeyError:
            return  # ignore messages that aren't defined in the db
        if self.__bus_name in db_msg.senders:
            try:
                decoded_data = db_msg.decode(message.data)
            except Exception as e:
                if not self.failed_messages.get(db_msg.name):
                    self.failed_messages[db_msg.name] = e
                    logging.warn(
                        f"({self.channel}) Failed to decode {db_msg.name}: {e}"
                    )
                return
            try:
                self.decoded_messages[db_msg.name]["data"] = decoded_data
                self.decoded_messages[db_msg.name]["timestamp"] = message.timestamp
            except KeyError:
                self.decoded_messages[db_msg.name] = {
                    "data": decoded_data,
                    "msg_def": db_msg,
                    "timestamp": message.timestamp,
                }
        return

    def set_decode_filter(self, message_names: list, exact_matching: bool = True):
        """Provide a list of message names to decode only those messages.

        Providing an empty list will decode all known messages.
        This does not filter can messages in message_queue.

        If exact_matching is False, a message is decoded if it's name contains any string from
        message_names, not case-sensitive.

        Args:
            message_names: str list of message names to decode, other messages will be ignored.
            exact_matching: whether the message name in the filter must exactly match the name in the DBC file.
        """
        if not message_names and self.__db:
            self.__decode_filter = []
            logging.info(f"({self.channel}) Decoding all messages (unfiltered).")
            return
        if not self.__db:
            raise Exception("Unable to create decode filter, no DBC file provided.")

        db_msgs = self.__db.messages
        for name in message_names:
            if exact_matching:
                try:
                    db_msg = self.__db.get_message_by_name(name)
                    self.__decode_filter.append(db_msg.frame_id)
                except KeyError:
                    logging.warning(
                        f"({self.channel}) Filter message '{name}' not found in dbc."
                    )
            else:
                matched_msgs = [
                    m.frame_id for m in db_msgs if name.lower() in m.name.lower()
                ]
                self.__decode_filter.extend(matched_msgs)

        # remove duplicates:
        self.__decode_filter = list(set(self.__decode_filter))
        logging.info(
            f"({self.channel}) Decoding {len(self.__decode_filter)} filtered messages."
        )

    def start(self):
        """This non-blocking method starts the can reader."""
        os.system(f"sudo /sbin/ip link set {self.channel} up type can bitrate 500000")
        self.__bus = can.interface.Bus(channel=self.channel, bustype="socketcan_native")
        self.__main_thread.start()
        self.__buffer_write_thread.start()
        self.__smooth_buffer_usage_thread.start()
        logging.info(f"Started can_reader ({self.channel}).")

    def stop(self):
        """This cleanly stops all threads."""
        logging.info(f"Stopping can_reader ({self.channel})...")
        self.__stop = True
        self.__main_thread.join()
        os.system(f"sudo /sbin/ip link set {self.channel} down")
        logging.info(f"Stopped can_reader ({self.channel}).")
