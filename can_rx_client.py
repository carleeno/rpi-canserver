import logging
import os
import sys
from argparse import ArgumentParser
from time import time

import can
import socketio

import tools
from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger(f"can_rx_client.unknown")

sio = socketio.Client()


@sio.event
def connect_error(e):
    logger.error(e)


def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--channel", "-c", default="can0", help="Bus channel to use")
    parser.add_argument("--bustype", "-b", default="socketcan", help="Bus type to use")
    parser.add_argument(
        "--server",
        "-s",
        default="http://localhost:8000",
        help="Socket.IO server to use",
    )
    parser.add_argument(
        "--batch_size", default=10, help="Size of batches to send can frames"
    )

    return parser.parse_args()


def main(args):
    channel = args.channel
    bustype = args.bustype
    server = args.server

    global logger
    logger = logging.getLogger(f"can_rx_client.{channel}")

    try:
        batch_size = int(args.batch_size)
        assert batch_size > 0
    except Exception as e:
        logger.exception(e)
        sys.exit(1)

    try:
        sio.connect(server, headers={"X-Username": f"can_rx_client.{channel}"})
    except Exception as e:
        logger.exception(e)
        sys.exit(1)

    os.system(f"sudo /sbin/ip link set {channel} up type can bitrate 500000")
    bus = can.interface.Bus(channel=channel, bustype=bustype)
    logger.debug(f"{channel} bus started")

    try:
        start = time()
        frame_count = 0
        batch = []
        while True:
            message = bus.recv()
            if message:
                frame = tools.msg_to_json(message)
                batch.append(frame)
                frame_count += 1

            if len(batch) >= batch_size:
                if sio.connected:
                    sio.emit("broadcast_can_frame_batch", {channel: batch})
                batch = []

            if frame_count >= 10000:
                delta = time() - start
                fps = int(frame_count / delta)
                if sio.connected:
                    sio.emit("broadcast_stats", {"fps": {f"{channel} rx": fps}})
                start = time()
                frame_count = 0

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.exception(e)
    finally:
        os.system(f"sudo /sbin/ip link set {channel} down")
        logger.debug(f"{channel} stopped")
        sio.disconnect()


if __name__ == "__main__":
    args = parse_args()
    main(args)