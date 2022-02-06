import logging
import os
from queue import Empty, Full, Queue
from threading import Thread

import can


class CanReader:
    """Class for getting can messages from a specified bus.
    Incoming messages are buffered for stability, a full buffer will drop messages.

    Messages are also decoded if provided a dbc file.
    """

    channel_name: str
    """The name of the can channel this reader was init'd with."""
    decoded_data: dict
    """Contains decoded data if a dbc_file is specified."""
    message_queue: Queue
    """Contains raw can messages (can.Message). Will stagnate if full."""

    def __init__(self, channel: str = "can0", dbc_file: str = ""):
        """Create can reader instance. Nothing happens until you call start().

        Args:
            channel: can0 or can1 (if you have a pican duo)
            dbc_file: optionally provide a filepath to define message decoding
        """
        os.system(f"sudo /sbin/ip link set {channel} up type can bitrate 500000")
        self.__bus = can.interface.Bus(channel=channel, bustype="socketcan_native")
        self.__can_rx_buffer = Queue(100)
        self.__can_rx_thread = Thread(target=self.__can_rx_task)
        self.__main_thread = Thread(target=self.__main_task)
        self.__stop = False
        self.channel_name = channel
        self.decoded_data = {}
        self.message_queue = Queue(100)

    def __safe_read(self):
        try:
            message = self.__bus.recv(timeout=1)
        except can.CanError as e:
            message = None
            logging.error(f"Error reading from bus {self.channel_name}: {e}")

        return message

    def __can_rx_task(self):
        while True:
            if self.__stop:
                return

            message = self.__safe_read()
            if not message:
                continue

            try:
                self.__can_rx_buffer.put(message, block=False)
            except Full:
                logging.error("Dropping message, buffer is full!")

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

    def __decode(self, message):
        # TODO implement this
        return

    def start(self):
        """This non-blocking method starts the can reader."""
        self.__main_thread.start()
        self.__can_rx_thread.start()
        logging.info(f"Started can_reader ({self.channel_name}).")

    def stop(self):
        """This finishes up the buffer and stops. Probably not needed."""
        logging.info(f"Stopping can_reader ({self.channel_name})...")
        self.__stop = True
        self.__main_thread.join()
        os.system(f"sudo /sbin/ip link set {self.channel_name} down")
        logging.info(f"Stopped can_reader ({self.channel_name}).")

    def buffer_usage(self) -> float:
        """Get usage of internal buffer in percentage (100 = full)."""
        buffer_usage = self.__can_rx_buffer.qsize() / self.__can_rx_buffer.maxsize
        return buffer_usage * 100
