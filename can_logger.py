import logging
import os
from datetime import datetime
from multiprocessing import Pipe, Process, Queue
from queue import Empty

from can.io.asc import ASCWriter


class CanLogger:
    def __init__(self, log_path="logs/can_logs"):
        self.log_path = log_path.rstrip("/")
        os.makedirs(log_path, exist_ok=True)

        self.__stop, self.__recv_stop = Pipe()
        self.__asc_thread = Process(target=self.__asc_writer)

        self.message_queue = Queue(100)

    def __asc_writer(self):
        try:
            asc_writer = ASCWriter(self.asc_file_path)
            logging.info(f"Started log: {self.asc_file_path}")
            while True:
                try:
                    if self.__recv_stop.poll() and self.__recv_stop.recv():
                        asc_writer.stop()
                        logging.info(f"Stopped log: {self.asc_file_path}")
                        return
                    try:
                        message = self.message_queue.get(timeout=1)
                        asc_writer.on_message_received(message)
                    except Empty:
                        pass
                except KeyboardInterrupt:
                    pass
        except Exception as e:
            logging.exception(e)

    def start_logging(self):
        """This non-blocking method starts the can logger."""
        # TODO don't allow starting twice
        logging.info("Starting logger...")
        start_time = datetime.now()
        file_name = start_time.strftime("%Y-%m-%d_%H.%M.%S")
        self.asc_file_path = f"{self.log_path}/{file_name}.asc"
        self.__asc_thread.start()

    def stop_logging(self):
        """This cleanly stops all logs."""
        # TODO don't allow stopping twice
        logging.info("Stopping logger...")
        self.__stop.send(True)
        self.__asc_thread.join()
