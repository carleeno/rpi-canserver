import logging
import pickle
from argparse import ArgumentParser
from threading import Thread
from time import sleep, time

import can
import redis
import socketio
from can import ASCReader

from logging_setup import setup_logging

setup_logging()


class CanReader:
    def __init__(self):
        self._parse_args()
        self.logger = logging.getLogger(f"can_rx_client.{self.channel}")
        self.sio = socketio.Client()
        self.red = redis.StrictRedis("localhost", 6379)

        self.count_start = time()
        self.frame_count = 0
        self._msg_batch = []
        self._running = False
        self._callbacks()

        self._setup_bus()

    def _parse_args(self):
        parser = ArgumentParser()
        parser.add_argument(
            "--channel", "-c", default="can0", help="Bus channel to use"
        )
        parser.add_argument(
            "--bustype", "-b", default="socketcan", help="Bus type to use"
        )
        parser.add_argument(
            "--server",
            "-s",
            default="http://localhost:8000",
            help="Socket.IO server to use",
        )
        parser.add_argument(
            "--batch_size", default=10, help="Size of batches to send can frames"
        )
        parser.add_argument(
            "--test", action="store_true", help="Run in test mode (no can device)"
        )

        args = parser.parse_args()
        self.channel = args.channel
        self.bustype = args.bustype
        self.server_address = args.server
        self.batch_size = int(args.batch_size)
        if self.batch_size < 1:
            raise Exception("batch_size must be greater than 0")
        self.testing = args.test

    def _setup_bus(self):
        if self.testing:
            self.reader = ASCReader(
                f"test_data/{self.channel}_cleaned.asc", relative_timestamp=False
            )
            self.test_batch_interval = 1 / (3000 / self.batch_size)  # 3000fps
            self.test_batch_send = time() + self.test_batch_interval
        else:
            self.bus = can.interface.Bus(channel=self.channel, bustype=self.bustype)

    def run(self):
        try:
            self.sio.connect(
                self.server_address,
                headers={"X-Username": f"can_logger.{self.channel}"},
                wait_timeout=60,
            )
            self._running = True
            self._stats_thread = Thread(target=self._stats_publisher_task, daemon=True)
            self._stats_thread.start()

            while self._running:
                self._add_message_to_batch()
                if len(self._msg_batch) >= self.batch_size:
                    self._publish_batch()

        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.shutdown()

    def shutdown(self):
        self._running = False
        self._stats_thread.join(timeout=2)
        self.sio.disconnect()

    def _add_message_to_batch(self):
        if self.testing:
            try:
                message = next(iter(self.reader))
            except (StopIteration, ValueError):
                self.logger.info("test data complete, shutting down soon")
                sleep(5)
                self.shutdown()
                return
        else:
            message = self.bus.recv(timeout=1)
        if message:
            self._msg_batch.append(message)
            self.frame_count += 1

    def _publish_batch(self):
        if self.testing:
            now = time()
            time_left = self.test_batch_send - now
            sleep(max((time_left, 0)))
            self.test_batch_send = time() + self.test_batch_interval
        pickled_batch = pickle.dumps(self._msg_batch)
        self.red.publish(f"{self.channel}_frame_batch", pickled_batch)
        self._msg_batch = []

    def _stats_publisher_task(self):
        while self._running:
            sleep(1)
            self._stats_publisher()

    def _stats_publisher(self):
        now = time()
        delta = now - self.count_start
        fps = int(self.frame_count / delta)
        if self.sio.connected:
            self.sio.emit("broadcast_stats", {"fps": {f"{self.channel} rx": fps}})
        self.count_start = now
        self.frame_count = 0

    def _callbacks(self):
        @self.sio.event
        def connect_error(e):
            self.logger.error(e)


if __name__ == "__main__":
    try:
        can_reader = CanReader()
    except Exception as e:
        logging.exception(e)

    can_reader.run()
