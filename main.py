import logging
from time import sleep

from can_reader import CanReader
from logging_setup import setup_logging

setup_logging()

PICAN_DUO = False

if __name__ == "__main__":
    logging.info("################ CAN-Server is starting ################")
    can0 = CanReader(channel="can0")
    can0.start()
    if PICAN_DUO:
        can1 = CanReader(channel="can1")
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
    if PICAN_DUO:
        can1.stop()
