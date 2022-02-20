import logging
import os
from datetime import datetime
from multiprocessing import Pipe, Process, Queue
from queue import Empty

from can.io.asc import ASCWriter


QUEUE_SIZE = 10000


class CanLogger:
    def __init__(self, bus_name="", log_path="logs/can_logs"):
        self.log_path = log_path.rstrip("/")
        self.bus_name = bus_name
        os.makedirs(log_path, exist_ok=True)

        self.__stop_pipe_in, self.__stop_pipe_out = Pipe()
        self.__asc_thread = None

        self.message_queue = Queue(QUEUE_SIZE)

        self.running = False
        self.running_pipe_in, self.running_pipe_out = Pipe()
        self.running_pipe_in.send(self.running)

    def __asc_writer(self):
        try:
            asc_writer = ASCWriter(self.asc_file_path)
            logging.info(f"Started log: {self.asc_file_path}")
            while True:
                try:
                    try:
                        message = self.message_queue.get(timeout=1)
                        asc_writer.on_message_received(message)
                    except Empty:
                        if self.__stop_pipe_out.poll() and self.__stop_pipe_out.recv():
                            asc_writer.stop()
                            logging.info(f"Stopped log: {self.asc_file_path}")
                            return
                except KeyboardInterrupt:
                    pass
        except Exception as e:
            logging.exception(e)

    def start_logging(self):
        """This non-blocking method starts the can logger."""
        if self.running:
            logging.warning(f"{self.bus_name} Logging already started.")
            return
        logging.info("Starting logger...")
        start_time = datetime.now()
        file_name = start_time.strftime("%Y-%m-%d_%H.%M.%S")
        if self.bus_name:
            file_name += f"_{self.bus_name}"
        self.asc_file_path = f"{self.log_path}/{file_name}.asc"

        self.__asc_thread = Process(target=self.__asc_writer)
        self.__asc_thread.start()
        self.running = True
        self.running_pipe_in.send(self.running)

    def stop_logging(self):
        """This cleanly stops all logs."""
        if not self.running:
            logging.warning(f"{self.bus_name} Logging already stopped.")
            return
        logging.info("Stopping logger...")
        self.running = False
        self.running_pipe_in.send(self.running)
        self.__stop_pipe_in.send(True)
        self.__asc_thread.join(timeout=10)
        if self.__asc_thread.is_alive():
            logging.error(f"({self.bus_name}) Stopping logging timed out, killing thread.")
            self.__asc_thread.kill()
