from threading import Thread
from time import sleep

import dash_bootstrap_components as dbc
import dash_daq as daq
from dash import Dash, Input, Output, dcc, html
from faster_fifo import Empty, Queue

import config as cfg

data = {}
system_stats = {}
reader_queues = []
stats_queue = Queue()

theme = {
    "dark": True,
    "detail": "#007439",
    "primary": "#00EA64",
    "secondary": "#6E6E6E",
}

app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], update_title=None)

# super basic example for testing:
app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [daq.LEDDisplay(id="volts", label="Battery Voltage", theme=theme)],
                    style={"display": "inline-block"},
                ),
                html.Div(
                    [daq.LEDDisplay(id="amps", label="Battery Amps", theme=theme)],
                    style={"display": "inline-block"},
                ),
                html.Div(
                    [daq.LEDDisplay(id="can0_rx_fps", label="CAN0 FPS", theme=theme)],
                    style={"display": "inline-block"},
                ),
                html.Div(
                    [daq.LEDDisplay(id="can1_rx_fps", label="CAN1 FPS", theme=theme)],
                    style={"display": "inline-block"},
                ),
            ]
        ),
        dcc.Interval(id="dash-update", interval=cfg.decode_interval * 1000),
    ]
)


# super basic example for testing:
@app.callback(
    [
        Output("amps", "value"),
        Output("volts", "value"),
        Output("can0_rx_fps", "value"),
        Output("can1_rx_fps", "value"),
    ],
    Input("dash-update", "n_intervals"),
)
def update_dash(_):
    if data.get("ID132HVBattAmpVolt"):
        amps = f'{data["ID132HVBattAmpVolt"]["SmoothBattCurrent132"]:.1f}'
        volts = int(data["ID132HVBattAmpVolt"]["BattVoltage132"])
    else:
        amps, volts = 0, 0

    can0_rx_fps = int(system_stats.get("can0_rx", 0))
    can1_rx_fps = int(system_stats.get("can1_rx", 0))
    return amps, volts, can0_rx_fps, can1_rx_fps


def run():
    server_thread = Thread(target=app.run_server, daemon=True)
    server_thread.start()
    try:
        get_data()
    except KeyboardInterrupt:
        pass


def get_data():
    global data, system_stats
    while True:
        for queue in reader_queues:
            try:
                messages = queue.get_many_nowait()
            except Empty:
                continue
            for msg in messages:
                data[msg["name"]] = msg["data"]
        try:
            stats = stats_queue.get_many_nowait()
            for stat in stats:
                system_stats.update(stat)
        except Empty:
            pass
        sleep(cfg.decode_interval)
