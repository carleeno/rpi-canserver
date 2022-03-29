import logging
from argparse import ArgumentParser
from time import time

import cantools
import socketio
from can import Message

import config as cfg
import tools
from logging_setup import setup_logging

setup_logging()


class CanDecoder:
    def __init__(self):
        self._parse_args()
        self.logger = logging.getLogger("can_decoder")
        self.sio = socketio.Client()

        self._setup_decoding()
        self._failed_messages = []
        self._last_decoded_ts = {"id": "ts"}
        self.count_start = time()
        self.frame_count = 0
        self._msg_batch = []
        self._batch_start = time()
        self._batch_interval = cfg.decode_interval
        self._callbacks()

    def _parse_args(self):
        parser = ArgumentParser()
        parser.add_argument(
            "--server",
            "-s",
            default="http://localhost:8000",
            help="Socket.IO server to use",
        )

        args = parser.parse_args()
        self.server_address = args.server

    def _setup_decoding(self):
        dbc_file = cfg.dbc_file
        include_list = cfg.can_filter
        if not include_list:
            raise Exception("include_list must not be empty")

        self.db = cantools.db.load_file(dbc_file)

        self._decode_filter = []
        for name in include_list:
            try:
                db_msg = self.db.get_message_by_name(name)
                self._decode_filter.append(db_msg.frame_id)
            except KeyError:
                raise Exception(f"Filter message '{name}' not found in dbc.")

        # remove duplicates:
        self._decode_filter = list(set(self._decode_filter))

        self.logger.debug(f"Decoding {len(self._decode_filter)} filtered messages.")

    def run(self):
        self.sio.connect(
            self.server_address,
            headers={"X-Username": "can_decoder"},
            wait_timeout=60,
        )
        self.sio.emit("enter_room", "raw_can")
        self.sio.wait()

    def _decode(self, message: Message):
        if message.arbitration_id not in self._decode_filter:
            return None
        try:
            if self._last_decoded_ts[message.arbitration_id] >= message.timestamp:
                return None
        except:
            pass
        try:
            db_msg = self.db.get_message_by_frame_id(message.arbitration_id)
        except KeyError:
            return None

        try:
            decoded_data = db_msg.decode(message.data, decode_choices=False)
        except Exception as e:
            if db_msg.name not in self._failed_messages:
                self._failed_messages.append(db_msg.name)
                self.logger.warning(f"Failed to decode {db_msg.name}: {e}")
            return None

        self._last_decoded_ts[message.arbitration_id] = message.timestamp

        return {message.arbitration_id: decoded_data}

    def _frame_counter(self, count):
        self.frame_count += count
        if self.frame_count >= 100:
            now = time()
            delta = now - self.count_start
            fps = int(self.frame_count / delta)
            if self.sio.connected:
                self.sio.emit("broadcast_stats", {"fps": {"decoder": fps}})
            self.count_start = now
            self.frame_count = 0

    def _callbacks(self):
        @self.sio.event
        def connect_error(e):
            self.logger.error(e)

        @self.sio.event
        def can_frame_batch(data: dict):
            msgs: list = next(iter(data.values()))
            self._msg_batch.extend(msgs)
            now = time()
            if now >= self._batch_start + self._batch_interval:
                msgs = self._msg_batch
                msgs.reverse()
                decoded_batch = {}
                for msg in msgs:
                    msg = tools.deserialize_msg(msg)
                    decoded = self._decode(msg)
                    if decoded:
                        decoded_batch.update(decoded)
                if self.sio.connected and decoded_batch:
                    self.sio.emit("broadcast_vehicle_stats", decoded_batch)

                self._frame_counter(len(decoded_batch))
                self._msg_batch = []
                self._batch_start = now


if __name__ == "__main__":
    can_decoder = CanDecoder()
    try:
        can_decoder.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        can_decoder.logger.exception(e)
