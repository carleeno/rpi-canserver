import logging
from time import sleep

import config as cfg
from can_reader import CanReader
from logging_setup import setup_logging

setup_logging()

if __name__ == "__main__":
    logging.info("################ CAN-Server is starting ################")
    can0 = CanReader(channel="can0", dbc_file=cfg.can0_dbc, bus_name=cfg.can0_bus)
    can0.set_decode_filter(cfg.can0_filter, cfg.can0_filter_exact_match)
    can0.start()
    if cfg.pican_duo:
        can1 = CanReader(channel="can1", dbc_file=cfg.can1_dbc, bus_name=cfg.can1_bus)
        can1.set_decode_filter(cfg.can1_filter, cfg.can1_filter_exact_match)
        can1.start()

    while True:
        try:
            sleep(1)
        except KeyboardInterrupt:
            logging.warning("Keyboard interrupt detected.")
            break
        except SystemExit:
            logging.warning("System exit requested.")
            break

    can0.stop()
    if cfg.pican_duo:
        can1.stop()
