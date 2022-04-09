import logging
import os
import pickle
from argparse import ArgumentParser
from datetime import datetime
from time import sleep, time

import redis
import socketio
from can import ASCWriter

import config as cfg
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
        os.makedirs(f"{self.log_dir}/flagged", exist_ok=True)
        self.writer = None
        self.file_path = None
        self.file_name = None
        self.logging = False
        self.auto_start_stop_log = False
        self.disk_full = False
        self.last_flag_log_signal = False
        self.first_flag_log_time = 0
        self.flag_this_log = False
        self.count_start = time()
        self.frame_count = 0
        self._last_gear_state_time = 0.0
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
            self._pubsub_thread = self.red_sub.run_in_thread(
                sleep_time=0.1, daemon=True
            )
            while True:
                sleep(1)
                if (
                    self.auto_start_stop_log
                    and self.logging
                    and time() > self._last_gear_state_time + 2
                ):
                    self.sio.emit(
                        "broadcast_message",
                        "log stopped because vehicle is off",
                    )
                    self._stop_logging()
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
        self.file_name = (
            start_time.strftime("%Y-%m-%d_%H.%M.%S_") + self.channel + ".asc"
        )
        self.file_path = f"{self.log_dir}/{self.file_name}"
        self.writer = ASCWriter(self.file_path)

        self.count_start = time()
        self.frame_count = 0
        self.logging = True

    def _stop_logging(self):
        if not self.logging:
            return
        self.logging = False
        self.writer.stop()
        if self.flag_this_log:
            self.flag_this_log = False
            os.replace(self.file_path, f"{self.log_dir}/flagged/{self.file_name}")

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
                        f"{self.channel} log file": {"value": self.file_name},
                        f"{self.channel} logging": {"value": self.logging},
                        f"{self.channel} auto-log": {"value": self.auto_start_stop_log},
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
        def logging_control(data):
            if data == "start":
                if not self.disk_full:
                    self._start_logging()
                    msg = "log started by request"
                else:
                    msg = "log not started, disk full"
            elif data == "stop":
                self._stop_logging()
                msg = "log stopped by request"
            elif data == "auto_on":
                if not self.disk_full:
                    self.auto_start_stop_log = True
                    msg = "auto logging enabled by request"
                else:
                    msg = "auto logging not enabled, disk full"
            elif data == "auto_off":
                self.auto_start_stop_log = False
                msg = "auto logging disabled by request"

            self.sio.emit("broadcast_message", msg)

        @self.sio.event
        def time_reset():
            now = time()
            self.count_start = now
            self.frame_count = 0
            self._last_gear_state_time = now

        @self.sio.event
        def stats(data):
            msg = None
            if data.get("system") and data["system"].get("disk usage"):
                usage = int(data["system"]["disk usage"]["value"])
                if usage > 90 and not self.disk_full:
                    self.disk_full = True
                    self.auto_start_stop_log = False
                    self._stop_logging()
                    msg = "logging disabled, disk almost full"
                if usage <= 90 and self.disk_full:
                    self.disk_full = False
                    msg = "logging reenabled, disk no longer full"
            if msg and self.sio.connected:
                self.sio.emit("broadcast_message", msg)

        @self.sio.event
        def vehicle_stats(data):
            msg = None
            if data.get(cfg.vehicle_gear_frame_id):
                if (
                    data[cfg.vehicle_gear_frame_id]["data"][
                        cfg.vehicle_gear_signal_name
                    ]["state"]
                    in cfg.vehicle_gear_logging_states
                ):
                    self._last_gear_state_time = time()
                    if (
                        not self.logging
                        and self.auto_start_stop_log
                        and not self.disk_full
                    ):
                        msg = "log started because vehicle is driving"
                        self._start_logging()
                else:
                    if self.logging and self.auto_start_stop_log:
                        msg = "log stopped because vehicle is parked"
                        self._stop_logging()

            if data.get(cfg.auto_logging_frame_id):
                if (
                    data[cfg.auto_logging_frame_id]["data"][
                        cfg.auto_logging_signal_name
                    ]["value"]
                    == cfg.auto_logging_on_value
                ):
                    if not self.auto_start_stop_log and not self.disk_full:
                        self.auto_start_stop_log = True
                        msg = "auto logging enabled by vehicle"
                elif self.auto_start_stop_log:
                    self.auto_start_stop_log = False
                    msg = "auto logging disabled by vehicle"
                    if self.logging:
                        self._stop_logging()
                        msg += ", and logging stopped"

            if data.get(cfg.flag_log_frame_id):
                if (
                    data[cfg.flag_log_frame_id]["data"][cfg.flag_log_signal_name][
                        "state"
                    ]
                    == cfg.flag_log_state
                ):
                    if (
                        self.last_flag_log_signal
                        and time() - self.first_flag_log_time
                        >= cfg.flag_log_signal_duration
                    ):
                        msg = "log flagged"
                        self.flag_this_log = True
                    elif not self.last_flag_log_signal:
                        self.first_flag_log_time = time()
                        self.last_flag_log_signal = True
                elif self.last_flag_log_signal:
                    self.last_flag_log_signal = False

            if msg and self.sio.connected:
                self.sio.emit("broadcast_message", msg)


if __name__ == "__main__":
    try:
        can_logger = CanLogger()
    except Exception as e:
        logging.exception(e)

    can_logger.run()
