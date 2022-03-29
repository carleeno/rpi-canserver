import logging
import os
from argparse import ArgumentParser
from datetime import datetime
from time import sleep, time

import socketio
from can import ASCWriter

from logging_setup import setup_logging

setup_logging()


class CanLogger:
    def __init__(self):
        self.parse_args()
        self.logger = logging.getLogger(f"can_logger.{self.channel}")
        self.sio = socketio.Client()
        self.log_dir = self.log_dir.rstrip("/")
        os.makedirs(self.log_dir, exist_ok=True)
        self.writer = None
        self.file_path = None
        self.file_name = None
        self.logging = False
        self.count_start = time()
        self.frame_count = 0
        self._callbacks()

    def parse_args(self):
        parser = ArgumentParser()
        parser.add_argument(
            "--channel", "-c", default="can0", help="Bus channel to use"
        )
        parser.add_argument(
            "--log_dir", "-l", default="logs/can_logs", help="Where to write the logs"
        )
        parser.add_argument(
            "--server",
            "-s",
            default="http://localhost:8000",
            help="Socket.IO server to use",
        )

        args = parser.parse_args()
        self.channel = args.channel
        self.server_address = args.server
        self.log_dir = args.log_dir

    def run(self):
        self.sio.connect(
            self.server_address,
            headers={"X-Username": f"can_logger.{self.channel}"},
            wait_timeout=60,
        )
        self.sio.emit("enter_room", "raw_can")
        self.sio.wait()

    def shutdown(self):
        self._stop_logging()

    def _start_logging(self):
        if self.logging:
            self.sio.emit(
                "broadcast_stats",
                {"system": {f"{self.channel} log": self.file_name}},
            )
            return
        start_time = datetime.now()
        self.file_name = start_time.strftime("%Y-%m-%d_%H.%M.%S_") + self.channel
        self.file_path = f"{self.log_dir}/{self.file_name}.asc"
        self.writer = ASCWriter(self.file_path)

        self.count_start = time()
        self.frame_count = 0
        self.logging = True
        self.sio.emit(
            "broadcast_stats", {"system": {f"{self.channel} log": self.file_name}}
        )

    def _stop_logging(self):
        if self.logging:
            self.logging = False
            sleep(1)
            self.writer.stop()
        if self.sio.connected:
            self.sio.emit(
                "broadcast_stats",
                {
                    "fps": {f"{self.channel} log": 0},
                    "system": {f"{self.channel} log": None},
                },
            )

    def _frame_counter(self, count):
        self.frame_count += count
        if self.frame_count >= 10000:
            now = time()
            delta = now - self.count_start
            fps = int(self.frame_count / delta)
            if self.sio.connected:
                self.sio.emit(
                    "broadcast_stats",
                    {
                        "fps": {f"{self.channel} log": fps},
                        "system": {f"{self.channel} log": self.file_name},
                    },
                )
            self.count_start = now
            self.frame_count = 0

    def _callbacks(self):
        @self.sio.event
        def connect_error(e):
            self.logger.error(e)

        @self.sio.event
        def start_logging():
            self._start_logging()

        @self.sio.event
        def stop_logging():
            self._stop_logging()

        @self.sio.event
        def can_frame_batch(data):
            if not self.logging:
                return
            batch = data.get(self.channel)
            if not batch:
                return

            for ts, msg in batch:
                self.writer.log_event(msg, ts)

            self._frame_counter(len(batch))

        @self.sio.event
        def stats(data):
            if self.logging and data.get("system") and data["system"].get("disk usage"):
                usage = int(data["system"]["disk usage"][:-2])
                if usage > 90:
                    self._stop_logging()
                    if self.sio.connected:
                        self.sio.emit(
                            "broadcast_message",
                            f"{self.channel} logger stopped because disk is almost full.",
                        )


if __name__ == "__main__":
    can_logger = CanLogger()
    try:
        can_logger.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        can_logger.logger.exception(e)
    finally:
        can_logger.shutdown()
