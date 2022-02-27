import logging
import os
import signal
from datetime import datetime
from multiprocessing import Process

from can import ASCWriter
from faster_fifo import Empty

from can_reader import CanReader


class CanLogger:
    def __init__(self, reader: CanReader, log_path="logs/can_logs"):
        self.log_path = log_path.rstrip("/")
        os.makedirs(log_path, exist_ok=True)

        self.__attached_reader = reader
        self.__message_queue = reader.logger_out
        if reader.bus_name:
            self.__file_suffix = reader.bus_name
        else:
            self.__file_suffix = reader.channel
        self.running = False

        self.__log = logging.getLogger(f"{__name__}.{reader.channel}")

    def __write_thread(self):
        try:
            while True:
                try:
                    messages = self.__message_queue.get_many()
                except Empty:
                    continue
                for msg in messages:
                    self.__asc_writer.on_message_received(msg)
        except Exception as e:
            self.__log.exception(e)

    def start_logging(self):
        """This non-blocking method starts the can logger."""
        if self.running:
            self.__log.warning("Logging already started.")
            return
        self.__log.debug("Starting logger...")

        start_time = datetime.now()
        file_name = start_time.strftime("%Y-%m-%d_%H.%M.%S_") + self.__file_suffix
        self.asc_file_path = f"{self.log_path}/{file_name}.asc"

        s = signal.signal(signal.SIGINT, signal.SIG_IGN)
        self.__asc_writer = ASCWriter(self.asc_file_path)
        self.__logger_thread = Process(target=self.__write_thread)
        self.__logger_thread.start()
        signal.signal(signal.SIGINT, s)
        self.__attached_reader.logger_running_pipe.send(True)
        self.running = True
        self.__log.info(f"Started log: {self.asc_file_path}")

    def stop_logging(self):
        """This cleanly stops all logs."""
        if not self.running:
            self.__log.warning("Logging already stopped.")
            return
        self.__log.debug("Stopping logger...")
        self.__attached_reader.logger_running_pipe.send(False)
        self.__logger_thread.kill()
        self.__asc_writer.stop()
        self.running = False
        self.__log.info(f"Stopped log: {self.asc_file_path}")
