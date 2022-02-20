import logging
import os
from multiprocessing import Pipe, Process, Queue
from queue import Empty, Full
from threading import Thread
from time import sleep

import can
import cantools


BUFFER_SIZE = 1000


class CanReader:
    """Class for getting can messages from a specified bus.
    Incoming messages are buffered for stability, a full buffer will drop messages.

    Messages are also decoded if provided a dbc file.
    """

    decode_buffer_usage: int
    """Smoothed buffer usage for monitoring performance. Fast rise, slow fall (10/sec)."""
    channel: str
    """The name of the can channel this reader was init'd with."""
    db: cantools.db.Database
    """Cantools database from provided DBC file (if any)."""
    decoded_messages: dict
    """Contains decoded messages if a dbc_file is specified."""
    failed_messages: dict
    """Contains message names which failed to decode, and their reason"""

    def __init__(
        self,
        logger_queue: Queue,
        channel: str = "can0",
        dbc_file: str = "",
        bus_name: str = None,
    ):
        """Create can reader instance. Nothing happens until you call start().

        Args:
            logger_queue: queue for sending raw messages to logger
            channel: can0 or can1 (if you have a pican duo)
            dbc_file: optionally provide a filepath to define message decoding
            bus_name: if using dbc file, specify this bus' name
        """
        self.__decode_thread = Thread(target=self.__decoder_task)
        self.__thread_stop = False
        self.channel = channel
        self.logger_queue = logger_queue

        # Buffer setup
        self.__decode_buffer = Queue(BUFFER_SIZE)
        self.__queue_write_thread = Process(target=self.__write_to_queues)
        self.__proc_stop_in, self.__proc_stop_out = Pipe()
        self.decode_buffer_usage = 0
        self.__smooth_buffer_usage_thread = Thread(target=self.__smooth_buffer_usage)

        # Decoding setup
        self.__bus_name = bus_name
        self.__decode_filter = []
        self.decoded_messages = {}
        self.failed_messages = {}
        if dbc_file:
            self.db = cantools.db.load_file(dbc_file)
        else:
            self.db = None
        if self.db:
            buses = [msg.senders[0] for msg in self.db.messages]
            buses = list(set(buses))
            if bus_name not in buses:
                raise Exception(f"({self.channel}) You must specify bus_name as one of: {buses}")

    def __safe_can_rx(self):
        try:
            message = self.__bus.recv(timeout=1)
        except can.CanError as e:
            message = None
            logging.error(f"({self.channel}) Error reading from {self.channel}: {e}")

        return message

    def __write_to_queues(self):
        decode_dropped = 0
        logging_dropped = 0
        try:
            while True:
                try:
                    if self.__proc_stop_out.poll() and self.__proc_stop_out.recv():
                        return

                    message = self.__safe_can_rx()
                    if not message:
                        continue

                    try:
                        self.__decode_buffer.put_nowait(message)
                    except Full:
                        decode_dropped += 1
                        if decode_dropped % 100 == 0:
                            logging.warning(f"({self.channel}) Dropped {decode_dropped} messages in decode buffer.")
                    try:
                        self.logger_queue.put_nowait(message)
                    except Full:
                        # logging_dropped += 1
                        # if logging_dropped % 1000 == 0:
                        #     logging.warning(f"({self.channel}) Dropped {logging_dropped} messages in logging buffer.")
                        pass  # this will be full when not logging.
                except KeyboardInterrupt:
                    pass
        except Exception as e:
            logging.exception(e)

    def __smooth_buffer_usage(self):
        while True:
            if self.decode_buffer_usage > 0:
                self.decode_buffer_usage += -1
            if self.__thread_stop:
                return
            sleep(0.1)

    def __decoder_task(self):
        while True:
            self.decode_buffer_usage = max((self.__decode_buffer.qsize(), self.decode_buffer_usage))
            try:
                message = self.__decode_buffer.get(timeout=1)
            except Empty:
                message = None
                if self.__thread_stop:
                    return

            if message:
                self.__decode(message)

    def __decode(self, message: can.Message):
        if not self.db:
            return
        if self.__decode_filter and message.arbitration_id not in self.__decode_filter:
            return
        try:
            db_msg = self.db.get_message_by_frame_id(message.arbitration_id)
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
        This does not filter can messages in logger_queue.

        If exact_matching is False, a message is decoded if it's name contains any string from
        message_names, not case-sensitive.

        Args:
            message_names: str list of message names to decode, other messages will be ignored.
            exact_matching: whether the message name in the filter must exactly match the name in the DBC file.
        """
        if not message_names and self.db:
            self.__decode_filter = []
            logging.info(f"({self.channel}) Decoding all messages (unfiltered).")
            return
        if not self.db:
            raise Exception(f"({self.channel}) Unable to create decode filter, no DBC file provided.")

        for name in message_names:
            if exact_matching:
                try:
                    db_msg = self.db.get_message_by_name(name)
                    self.__decode_filter.append(db_msg.frame_id)
                except KeyError:
                    logging.warning(
                        f"({self.channel}) Filter message '{name}' not found in dbc."
                    )
            else:
                matched_msgs = [
                    m.frame_id
                    for m in self.db.messages
                    if name.lower() in m.name.lower()
                ]
                self.__decode_filter.extend(matched_msgs)

        # remove duplicates:
        self.__decode_filter = list(set(self.__decode_filter))
        logging.info(
            f"({self.channel}) Decoding {len(self.__decode_filter)} filtered messages."
        )

    def start(self):
        """This non-blocking method starts the can reader."""
        # TODO don't allow running twice
        os.system(f"sudo /sbin/ip link set {self.channel} up type can bitrate 500000")
        self.__bus = can.interface.Bus(channel=self.channel, bustype="socketcan_native")
        self.__thread_stop = False
        self.decoded_messages = {}
        self.failed_messages = {}

        self.__decode_thread.start()
        self.__queue_write_thread.start()
        self.__smooth_buffer_usage_thread.start()
        logging.info(f"({self.channel}) Started can_reader.")

    def stop(self):
        """This cleanly stops all threads."""
        # TODO don't allow stopping twice
        logging.info(f"({self.channel}) Stopping can_reader...")
        self.__proc_stop_in.send(True)
        self.__thread_stop = True
        self.__queue_write_thread.join()
        self.__smooth_buffer_usage_thread.join()
        self.__decode_thread.join()
        os.system(f"sudo /sbin/ip link set {self.channel} down")
        logging.info(f"({self.channel}) Stopped can_reader.")
