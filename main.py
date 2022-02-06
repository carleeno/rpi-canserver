import logging
from time import sleep

from can_reader import CanReader
from logging_setup import setup_logging

setup_logging()

CAN0_DBC = "Model3CAN.dbc"
CAN0_BUS = "VehicleBus"
# If you have a pican DUO:
PICAN_DUO = False
CAN1_DBC = "Model3CAN.dbc"
CAN1_BUS = "ChassisBus"

if __name__ == "__main__":
    logging.info("################ CAN-Server is starting ################")
    can0 = CanReader(channel="can0", dbc_file=CAN0_DBC, bus_name=CAN0_BUS)
    can0.start()
    if PICAN_DUO:
        can1 = CanReader(channel="can1", dbc_file=CAN1_DBC, bus_name=CAN1_BUS)
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
