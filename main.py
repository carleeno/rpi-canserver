import logging
import shlex
import signal
import subprocess
from time import sleep, time

import psutil
import socketio
from gpiozero import CPUTemperature

import config as cfg
import tools
from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger("canserver.main")

devnull = open("/dev/null", "w")


class CanServer:
    def __init__(self, address="127.0.0.1:8000") -> None:
        self.server_bind = address
        self.server_address = f"http://{address}"
        self.server_proc = None
        self.client_procs = []
        self.sio = socketio.Client()
        self._callbacks()
        self.stats = {"last_logged": int(time())}
        psutil.cpu_percent()  # initial call to set start of interval
        self.rolling_disk_io = [(time(), psutil.disk_io_counters(nowrap=True))]
        self.disk_io_time_window = 30
        self.cpu_temp = CPUTemperature()

    def run(self):
        self.server_proc = subprocess.Popen(
            shlex.split(f"gunicorn -k eventlet -w 1 -b {self.server_bind} server:app"),
            stderr=devnull,
        )
        sleep(2)
        self.sio.connect(
            self.server_address,
            headers={"X-Username": "canserver.main"},
            wait_timeout=5,
        )
        self.client_procs.append(
            subprocess.Popen(
                shlex.split(
                    f"python can_rx_client.py -s {self.server_address} --batch_size 50"
                )
            )
        )
        self.client_procs.append(
            subprocess.Popen(
                shlex.split(f"python can_logger_client.py -s {self.server_address}")
            )
        )
        self.client_procs.append(
            subprocess.Popen(
                shlex.split(f"python can_decoder_client.py -s {self.server_address}")
            )
        )
        if cfg.pican_duo:
            self.client_procs.append(
                subprocess.Popen(
                    shlex.split(
                        f"python can_rx_client.py -c can1 -s {self.server_address} --batch_size 50"
                    )
                )
            )
            self.client_procs.append(
                subprocess.Popen(
                    shlex.split(
                        f"python can_logger_client.py -c can1 -s {self.server_address}"
                    )
                )
            )
        while True:
            self._system_stats()
            sleep(2)

    def shutdown(self, send_sigint=True):
        logger.info("Shutting down")
        proc: subprocess.Popen
        for proc in self.client_procs:
            if send_sigint:
                proc.send_signal(signal.SIGINT)
            proc.wait(timeout=5)
        if self.sio.connected:
            self.sio.disconnect()
        if send_sigint:
            self.server_proc.send_signal(signal.SIGINT)
        self.server_proc.wait(timeout=5)

    def _system_stats(self):
        system_stats = {}
        per_cpu_usage = psutil.cpu_percent(percpu=True)
        system_stats["cpu all"] = f"{int(sum(per_cpu_usage)/len(per_cpu_usage))} %"
        for i, usage in enumerate(per_cpu_usage):
            system_stats[f"cpu {i}"] = f"{int(usage)} %"
        system_stats["cpu temp"] = f"{int(self.cpu_temp.temperature)} °C"
        system_stats["memory usage"] = f"{int(psutil.virtual_memory().percent)} %"
        system_stats["disk usage"] = f"{int(psutil.disk_usage('/').percent)} %"
        self.rolling_disk_io.append((time(), psutil.disk_io_counters(nowrap=True)))
        time_delta = self.rolling_disk_io[-1][0] - self.rolling_disk_io[0][0]
        while time_delta > self.disk_io_time_window:
            self.rolling_disk_io.pop(0)
            time_delta = self.rolling_disk_io[-1][0] - self.rolling_disk_io[0][0]
        write_bytes_delta = (
            self.rolling_disk_io[-1][1].write_bytes
            - self.rolling_disk_io[0][1].write_bytes
        )
        write_ops_delta = (
            self.rolling_disk_io[-1][1].write_count
            - self.rolling_disk_io[0][1].write_count
        )
        write_speed = write_bytes_delta / time_delta / 1024
        write_ops = write_ops_delta / time_delta
        system_stats["disk write speed"] = f"{write_speed:.2f} KB/s"
        system_stats["disk write ops"] = f"{write_ops:.2f} ops/s"

        self.sio.emit("broadcast_stats", {"system": system_stats})

    def _callbacks(self):
        @self.sio.event
        def message(msg):
            logger.info(msg)

        @self.sio.event
        def stats(data):
            tools.deep_update(self.stats, data)
            now = int(time())
            if self.stats["last_logged"] + 60 <= now:
                del self.stats["last_logged"]
                logger.debug(self.stats)
                self.stats["last_logged"] = now


def main():
    logger.info("################ CAN-Server is starting ################")
    canserver = CanServer()
    try:
        canserver.run()
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt")
        canserver.shutdown(send_sigint=False)
        return
    except Exception as e:
        logger.exception(e)
    canserver.shutdown()


if __name__ == "__main__":
    main()
