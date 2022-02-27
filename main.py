import logging
from time import sleep

import config as cfg
from can_logger import CanLogger
from can_reader import CanReader
from logging_setup import setup_logging


setup_logging()
log = logging.getLogger("canserver.main")


def main():
    log.info("################ CAN-Server is starting ################")

    can0_reader = CanReader(channel="can0")
    can0_reader.setup_decoding(
        cfg.can0_dbc, cfg.can0_bus, cfg.can0_filter, cfg.decode_interval
    )
    can0_logger = CanLogger(can0_reader)

    if cfg.pican_duo:
        can1_reader = CanReader(channel="can1")
        can1_reader.setup_decoding(
            cfg.can1_dbc, cfg.can1_bus, cfg.can1_filter, cfg.decode_interval
        )
        can1_logger = CanLogger(can1_reader)

    can0_logger.start_logging()
    can0_reader.start_reading()
    if cfg.pican_duo:
        can1_logger.start_logging()
        can1_reader.start_reading()

    try:
        # future (blocking) web_server.run() will go here. for now we sleep.
        while True:
            sleep(10)
    except KeyboardInterrupt:
        log.warning("Keyboard interrupt detected.")

    can0_reader.stop_reading()
    can0_logger.stop_logging()
    if cfg.pican_duo:
        can1_reader.stop_reading()
        can1_logger.stop_logging()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.exception(e)
