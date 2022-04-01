import logging
import pickle
import socket
from argparse import ArgumentParser
from time import sleep, time
from typing import Dict, List

import redis
import socketio
from can import Message

from logging_setup import setup_logging
from panda_client import PandaClient

setup_logging()


class PandaServer:
    def __init__(self):
        self._parse_args()
        self.logger = logging.getLogger("panda_server")
        self.sio = socketio.Client()
        self.red = redis.StrictRedis("localhost", 6379)
        self.red_sub = self.red.pubsub()
        self.last_stats_time = time()
        self.frame_count = 0
        self._last_decoded_ts = {"id": "ts"}
        self._frame_batch = []
        self._batch_start = time()
        self._batch_interval = 1 / 120  # stream 120hz to panda clients
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setblocking(False)
        self.udp_socket.bind(self.panda_address)
        self.panda_clients: Dict[str, PandaClient] = {}
        self._callbacks()

    def _parse_args(self):
        parser = ArgumentParser()
        parser.add_argument(
            "--server",
            "-s",
            default="http://localhost:8000",
            help="Socket.IO server to use",
        )
        parser.add_argument(
            "--panda_bind",
            "-p",
            default="127.0.0.1:1338",
            help="Address to bind panda server to",
        )

        args = parser.parse_args()
        self.server_address = args.server
        p_host = args.panda_bind.split(":")[0]
        p_port = int(args.panda_bind.split(":")[1])
        self.panda_address = (p_host, p_port)

    def run(self):
        try:
            self.sio.connect(
                self.server_address,
                headers={"X-Username": "panda_server"},
                wait_timeout=60,
            )
            self.red_sub.psubscribe(**{"can*_frame_batch": self._pubsub_handler})
            self._pubsub_thread = self.red_sub.run_in_thread(
                sleep_time=0.1, daemon=True
            )
            while True:
                sleep(0.05)
                now = time()
                if now >= self.last_stats_time + 1:
                    for client in self.panda_clients.values():
                        client.alive_check()
                    self._cleanup_clients()
                    self._stats_publisher()
                    self.last_stats_time = now

                try:
                    data, address = self.udp_socket.recvfrom(1024)
                except socket.error:
                    continue
                try:
                    self.panda_clients[address[0]].process(data, address)
                except KeyError:
                    self.panda_clients[address[0]] = PandaClient(
                        self.udp_socket, data, address
                    )
        except KeyboardInterrupt:
            pass
        except Exception as e:
            self.logger.exception(e)
        finally:
            self.shutdown()

    def shutdown(self):
        self._pubsub_thread.stop()

    def _pubsub_handler(self, msg):
        if msg and isinstance(msg, dict) and msg["type"] == "pmessage":
            pickled_batch = msg.get("data")
            batch = pickle.loads(pickled_batch)
            self._on_frame_batch(batch)

    def _on_frame_batch(self, batch):
        self._frame_batch.extend(batch)
        now = time()
        if now >= self._batch_start + self._batch_interval:
            msgs_to_send = self._clean_batch(self._frame_batch)
            try:
                clients = list(self.panda_clients.values()).copy()
                for client in clients:
                    for frame in msgs_to_send:
                        sent = client.send_frame(frame)
                        if sent:
                            self.frame_count += 1
            except Exception as e:
                self.logger.exception(e)
                self.shutdown()
            self._frame_batch = []
            self._batch_start = now

    def _clean_batch(self, batch: List[Message]):
        batch.reverse()
        cleaned_batch = {}
        for msg in batch:
            try:
                if self._last_decoded_ts[msg.arbitration_id] >= msg.timestamp:
                    continue
            except:
                pass
            cleaned_batch[msg.arbitration_id] = msg
            self._last_decoded_ts[msg.arbitration_id] = msg.timestamp
        batch = list(cleaned_batch.values())
        batch.reverse()
        return batch

    def _stats_publisher(self):
        now = time()
        delta = now - self.last_stats_time
        fps = int(self.frame_count / delta)

        if self.sio.connected:
            self.sio.emit(
                "broadcast_stats",
                {
                    "fps": {"panda": fps},
                    "system": {"panda clients": len(self.panda_clients)},
                },
            )
        self.last_stats_time = now
        self.frame_count = 0

    def _cleanup_clients(self):
        dead_panda_client_hosts = [
            x.address[0] for x in self.panda_clients.values() if not x.connected
        ]
        for host in dead_panda_client_hosts:
            del self.panda_clients[host]

    def _callbacks(self):
        @self.sio.event
        def connect_error(e):
            self.logger.error(e)


if __name__ == "__main__":
    try:
        panda_server = PandaServer()
    except Exception as e:
        logging.exception(e)

    panda_server.run()
