import logging

import config as cfg
import web_server
from can_logger import CanLogger
from can_reader import CanReader
from logging_setup import setup_logging


setup_logging()
log = logging.getLogger("canserver.main")


class CanServer:
    def __init__(self) -> None:
        self.can0_reader = CanReader(channel="can0")
        self.can0_reader.setup_decoding(
            cfg.can0_dbc, cfg.can0_bus, cfg.can0_filter, cfg.decode_interval
        )
        web_server.reader_queues.append(self.can0_reader.decoded_messages)
        self.can0_logger = CanLogger(self.can0_reader)

        if cfg.pican_duo:
            self.can1_reader = CanReader(channel="can1")
            self.can1_reader.setup_decoding(
                cfg.can1_dbc, cfg.can1_bus, cfg.can1_filter, cfg.decode_interval
            )
            web_server.reader_queues.append(self.can1_reader.decoded_messages)
            self.can1_logger = CanLogger(self.can1_reader)

    def _start_logging(self):
        self.can0_logger.start_logging()
        if cfg.pican_duo:
            self.can1_logger.start_logging()

    def _stop_logging(self):
        if self.can0_logger.running:
            self.can0_logger.stop_logging()
        if cfg.pican_duo:
            if self.can1_logger.running:
                self.can1_logger.stop_logging()

    def run(self):
        self.can0_reader.start_reading()
        if cfg.pican_duo:
            self.can1_reader.start_reading()
        web_server.run()  # blocking

    def shutdown(self):
        self.can0_reader.stop_reading()
        if cfg.pican_duo:
            self.can1_reader.stop_reading()
        self._stop_logging()


def main():
    log.info("################ CAN-Server is starting ################")
    try:
        canserver = CanServer()
        canserver.run()
    except Exception as e:
        log.exception(e)
    try:
        canserver.shutdown()
    except:
        pass


if __name__ == "__main__":
    main()
