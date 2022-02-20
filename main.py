import logging
from time import sleep

import config as cfg
from can_logger import CanLogger
from can_reader import CanReader
from logging_setup import setup_logging

setup_logging()


def main():
    logging.info("################ CAN-Server is starting ################")

    can0_logger = CanLogger(bus_name=cfg.can0_bus)
    can0_reader = CanReader(
        logger=can0_logger,
        channel="can0",
        dbc_file=cfg.can0_dbc,
        bus_name=cfg.can0_bus,
    )
    can0_reader.set_decode_filter(cfg.can0_filter, cfg.can0_filter_exact_match)

    if cfg.pican_duo:
        can1_logger = CanLogger(bus_name=cfg.can1_bus)
        can1_reader = CanReader(
            logger=can1_logger,
            channel="can1",
            dbc_file=cfg.can1_dbc,
            bus_name=cfg.can1_bus,
        )
        can1_reader.set_decode_filter(cfg.can1_filter, cfg.can1_filter_exact_match)

    can0_logger.start_logging()    
    can0_reader.start_reading()
    if cfg.pican_duo:
        can1_logger.start_logging()
        can1_reader.start_reading()

    try:
        # future (blocking) web_server.run() will go here. for now we sleep.
        while True:
            logging.debug(f"can0 buffers: {can0_logger.message_queue.qsize()}, {can0_reader.decode_buffer_usage}")
            logging.debug(f"can1 buffers: {can1_logger.message_queue.qsize()}, {can1_reader.decode_buffer_usage}")
            sleep(10)
    except KeyboardInterrupt:
        logging.warning("Keyboard interrupt detected.")
    except SystemExit:
        logging.warning("System exit requested.")

    can0_reader.stop_reading()
    can0_logger.stop_logging()
    if cfg.pican_duo:
        can1_reader.stop_reading()
        can1_logger.stop_logging()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception(e)
