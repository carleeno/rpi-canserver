import logging
import os
from datetime import datetime
from queue import Empty
from threading import Thread
from typing import List

from can.io.asc import ASCWriter

from can_reader import CanReader


class CanLogger:
    def __init__(self, readers: List[CanReader], log_path="logs/can_logs"):
        self.readers = readers
        self.log_path = log_path.rstrip("/")
        os.makedirs(log_path, exist_ok=True)

        self.__stop = False
        self.__asc_thread = Thread(target=self.__asc_writer)

    def __asc_writer(self):
        asc_writer = ASCWriter(self.asc_file_path)
        logging.info(f"Started log: {self.asc_file_path}")
        while True:
            if self.__stop:
                asc_writer.stop()
                logging.info(f"Stopped log: {self.asc_file_path}")
                return
            for r in self.readers:
                try:
                    message = r.message_queue.get_nowait()
                    asc_writer.on_message_received(message)
                except Empty:
                    pass

    def start_logging(self):
        """This non-blocking method starts the can logger."""
        logging.info("Starting logger...")
        self.__stop = False
        start_time = datetime.now()
        file_name = start_time.strftime("%Y-%m-%d_%H.%M.%S")
        self.asc_file_path = f"{self.log_path}/{file_name}.asc"
        self.__asc_thread.start()

    def stop_logging(self):
        """This cleanly stops all logs."""
        logging.info("Stopping logger...")
        self.__stop = True
        self.__asc_thread.join()
