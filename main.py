import logging
from time import sleep

import config as cfg
from can_logger import CanLogger
from can_reader import CanReader
from logging_setup import setup_logging

setup_logging()


def main():
    logging.info("################ CAN-Server is starting ################")

    can_logger = CanLogger()

    can0 = CanReader(
        out_queue=can_logger.message_queue,
        channel="can0",
        dbc_file=cfg.can0_dbc,
        bus_name=cfg.can0_bus,
    )
    can0.set_decode_filter(cfg.can0_filter, cfg.can0_filter_exact_match)
    can0.start()

    if cfg.pican_duo:
        can1 = CanReader(
            out_queue=can_logger.message_queue,
            channel="can1",
            dbc_file=cfg.can1_dbc,
            bus_name=cfg.can1_bus,
        )
        can1.set_decode_filter(cfg.can1_filter, cfg.can1_filter_exact_match)
        can1.start()

    # can_logger.start_logging()

    try:
        # future (blocking) web_server.run() will go here. for now we sleep.
        while True:
            sleep(1)
    except KeyboardInterrupt:
        logging.warning("Keyboard interrupt detected.")
    except SystemExit:
        logging.warning("System exit requested.")

    # can_logger.stop_logging()
    can0.stop()
    if cfg.pican_duo:
        can1.stop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception(e)
