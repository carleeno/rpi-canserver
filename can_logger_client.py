import logging
import os
import pickle
from argparse import ArgumentParser
from datetime import datetime
from time import sleep, time

import redis
import socketio
from can import ASCWriter

from logging_setup import setup_logging

setup_logging()


class CanLogger:
    def __init__(self):
        self.parse_args()
        self.logger = logging.getLogger(f"can_logger.{self.channel}")
        self.sio = socketio.Client()
        self.red = redis.StrictRedis("localhost", 6379)
        self.red_sub = self.red.pubsub()

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
            "--log_dir",
            "-l",
            default="/tmp/canserver-logs/asc_logs",
            help="Where to write the logs",
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
        try:
            self.sio.connect(
                self.server_address,
                headers={"X-Username": f"can_logger.{self.channel}"},
                wait_timeout=60,
            )
            self.red_sub.subscribe(
                **{f"{self.channel}_frame_batch": self._pubsub_handler}
            )
            self._pubsub_thread = self.red_sub.run_in_thread(daemon=True)
            while True:
                sleep(1)
                self._stats_publisher()
        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.shutdown()

    def shutdown(self):
        self._stop_logging()
        self._pubsub_thread.stop()

    def _pubsub_handler(self, msg):
        if not self.logging:
            return
        if msg and isinstance(msg, dict) and msg["type"] == "message":
            pickled_batch = msg.get("data")
            batch = pickle.loads(pickled_batch)
            self._on_frame_batch(batch)

    def _on_frame_batch(self, batch):
        for msg in batch:
            self.writer.on_message_received(msg)

        self.frame_count += len(batch)

    def _start_logging(self):
        if self.logging:
            return
        start_time = datetime.now()
        self.file_name = start_time.strftime("%Y-%m-%d_%H.%M.%S_") + self.channel
        self.file_path = f"{self.log_dir}/{self.file_name}.asc"
        self.writer = ASCWriter(self.file_path)

        self.count_start = time()
        self.frame_count = 0
        self.logging = True

    def _stop_logging(self):
        if self.logging:
            self.logging = False
            sleep(1)
            self.writer.stop()

    def _stats_publisher(self):
        now = time()
        delta = now - self.count_start
        fps = int(self.frame_count / delta)
        if self.sio.connected:
            self.sio.emit(
                "broadcast_stats",
                {
                    "fps": {f"{self.channel} log": fps},
                    "system": {
                        f"{self.channel} log file": self.file_name,
                        f"{self.channel} logging": self.logging,
                    },
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
    try:
        can_logger = CanLogger()
    except Exception as e:
        logging.exception(e)

    can_logger.run()
