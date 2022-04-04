import json
import logging
import shlex
import signal
import subprocess
from argparse import ArgumentParser
from time import sleep, time
from typing import List

import psutil
import socketio

import config as cfg
import tools
from logging_setup import setup_logging

setup_logging()
logger = logging.getLogger("canserver.main")

server_stderr = open("/tmp/canserver-logs/server.stderr.log", "w")


class CanServer:
    def __init__(self, address, panda_bind, batch_size, test, timesync) -> None:
        self.server_address = address
        self.batch_size = batch_size
        self.test = test
        self.timesync = timesync
        self.last_detected_offset = 0.0
        self.server_proc = None
        self.client_procs: List[subprocess.Popen] = []
        self.sio = socketio.Client()
        self._callbacks()

        self.server_cmd = shlex.split(
            f"gunicorn -k eventlet -w 1 -b {self.server_address} --worker-tmp-dir /dev/shm server:app"
        )
        self.rx_client_cmd = shlex.split(
            f"python can_rx_client.py -s http://{self.server_address} --batch_size {self.batch_size}"
        )
        if test:
            self.rx_client_cmd += ["--test"]
        self.logger_client_cmd = shlex.split(
            f"python can_logger_client.py -s http://{self.server_address}"
        )
        self.decoder_client_cmd = shlex.split(
            f"python can_decoder_client.py -s http://{self.server_address}"
        )
        self.panda_server_cmd = shlex.split(
            f"python panda_server.py -s http://{self.server_address} -p {panda_bind}"
        )

        self.stats = {"last_logged": int(time())}
        psutil.cpu_percent()  # initial call to set start of interval
        self.rolling_disk_io = [(time(), psutil.disk_io_counters(nowrap=True))]
        self.disk_io_time_window = 30
        self.killer = tools.GracefulKiller()

    def run(self):
        self.server_proc = subprocess.Popen(
            self.server_cmd,
            stderr=server_stderr,
        )
        sleep(2)
        self.sio.connect(
            f"http://{self.server_address}",
            headers={"X-Username": "canserver.main"},
            wait_timeout=60,
        )
        self.client_procs.append(subprocess.Popen(self.rx_client_cmd))
        self.client_procs.append(subprocess.Popen(self.logger_client_cmd))
        if cfg.pican_duo:
            self.client_procs.append(
                subprocess.Popen(self.rx_client_cmd + ["-c", "can1"])
            )
            self.client_procs.append(
                subprocess.Popen(self.logger_client_cmd + ["-c", "can1"])
            )
        self.client_procs.append(subprocess.Popen(self.decoder_client_cmd))
        self.client_procs.append(subprocess.Popen(self.panda_server_cmd))
        if self.sio.connected:
            self.sio.emit("broadcast_message", "canserver started")
        while not self.killer.kill_now:
            self._system_stats()
            self._check_clients()
            sleep(1)

    def shutdown(self, send_sigint=True, reason=""):
        message = "Shutting down"
        if reason:
            message += f" for: {reason}"
        logger.info(message)
        if self.sio.connected:
            self.sio.emit("broadcast_message", message)
        for proc in self.client_procs:
            if send_sigint:
                proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        if self.sio.connected:
            self.sio.disconnect()
        if send_sigint:
            self.server_proc.send_signal(signal.SIGINT)
        try:
            self.server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.server_proc.kill()
        self.killer.kill_now = True

    def _system_stats(self):
        system_stats = {}
        per_cpu_usage = psutil.cpu_percent(percpu=True)
        system_stats["cpu all"] = {
            "value": round(sum(per_cpu_usage) / len(per_cpu_usage)),
            "unit": "%",
        }
        for i, usage in enumerate(per_cpu_usage):
            system_stats[f"cpu {i}"] = {"value": round(usage), "unit": "%"}
        cpu_temp = self._cpu_temp()
        if cpu_temp:
            system_stats["cpu temp"] = {"value": round(cpu_temp, 1), "unit": "°C"}
        system_stats["memory usage"] = {
            "value": round(psutil.virtual_memory().percent),
            "unit": "%",
        }
        system_stats["disk usage"] = {
            "value": round(psutil.disk_usage("/").percent),
            "unit": "%",
        }
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
        try:
            write_speed = write_bytes_delta / time_delta / 1024
            write_ops = write_ops_delta / time_delta
            system_stats["disk write speed"] = {
                "value": round(write_speed, 2),
                "unit": "KB/s",
            }
            system_stats["disk write ops"] = {
                "value": round(write_ops, 2),
                "unit": "ops/s",
            }
        except ZeroDivisionError:
            pass

        if self.sio.connected:
            self.sio.emit("broadcast_stats", {"system": system_stats})

    def _check_clients(self):
        dead_procs = [x for x in self.client_procs if x.poll() != None]
        if dead_procs:
            self.shutdown(reason="Dead client")

    def _cpu_temp(self):
        try:
            stdout = subprocess.run(
                ["sensors", "-jA"], capture_output=True, text=True
            ).stdout.strip("\n")
            data = json.loads(stdout)
            for k, v in data.items():
                if "coretemp" in k or "cpu_thermal" in k:
                    temp = next(iter(v.values()))["temp1_input"]
                    return temp
        except Exception as e:
            # logger.exception(f"Exception trying to get cpu temp: {e}")
            return

    def _callbacks(self):
        @self.sio.event
        def message(msg):
            logger.info(msg)

        @self.sio.event
        def stats(data):
            tools.deep_update(self.stats, data)
            now = int(time())
            if self.stats["last_logged"] + 60 <= now:
                logger.debug(self.stats)
                self.stats["last_logged"] = now

        @self.sio.event
        def vehicle_stats(data):
            if self.test:
                return
            if data.get(cfg.vehicle_time_frame_id):
                car_time = data[cfg.vehicle_time_frame_id]["data"][cfg.vehicle_time_signal_name]["value"]
                offset = tools.sys_time_offset(data[cfg.vehicle_time_frame_id]["timestamp"], car_time)
                if abs(offset) > 0.1 and round(offset, 2) != self.last_detected_offset:
                    logger.warning(
                        f"System time appears off by {offset} seconds (vs vehicle time)"
                    )
                    self.last_detected_offset = round(offset, 2)
                    if self.timesync:
                        tools.fix_sys_time(offset)
                        self.last_detected_offset = 0.0
                        logger.warning(f"Adjusted system time by {offset} seconds")


def parse_args():
    parser = ArgumentParser()
    parser.add_argument(
        "--address",
        "-a",
        default="127.0.0.1:5000",
        help="Address to run socketIO on",
    )
    parser.add_argument(
        "--panda_bind",
        "-p",
        default="127.0.0.1:1338",
        help="Address to bind panda server to",
    )
    parser.add_argument(
        "--batch_size", default=50, help="Size of batches to send can frames"
    )
    parser.add_argument(
        "--test", action="store_true", help="Run in test mode (no can device)"
    )
    parser.add_argument(
        "--timesync", action="store_true", help="Sync system time from vehicle"
    )

    return parser.parse_args()


def main():
    logger.info("################ CAN-Server is starting ################")
    args = parse_args()
    canserver = CanServer(
        args.address, args.panda_bind, args.batch_size, args.test, args.timesync
    )
    try:
        canserver.run()
        canserver.shutdown(reason="run completed")
    except KeyboardInterrupt:
        logger.warning("Keyboard interrupt")
        canserver.shutdown(send_sigint=False, reason="KeyboardInterrupt")
    except Exception as e:
        logger.exception(e)
        canserver.shutdown(reason=e)
    finally:
        server_stderr.close()


if __name__ == "__main__":
    main()
