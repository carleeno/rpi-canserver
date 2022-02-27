from threading import Thread

import dash_bootstrap_components as dbc
import dash_daq as daq
from dash import Dash, Input, Output, dcc, html
from faster_fifo import Empty

data = {}
reader_queues = []

app = Dash(__name__, external_stylesheets=[dbc.themes.DARKLY], update_title=None)

# super basic example for testing:
app.layout = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        daq.Gauge(
                            id="volts",
                            value=0,
                            units="Volts",
                            min=250,
                            max=400,
                            showCurrentValue=True,
                        )
                    ],
                    style={"display": "inline-block"},
                ),
                html.Div(
                    [
                        daq.Gauge(
                            id="amps",
                            value=0,
                            units="Amps",
                            min=-500,
                            max=1000,
                            showCurrentValue=True,
                        )
                    ],
                    style={"display": "inline-block"},
                ),
            ]
        ),
        dcc.Interval(id="dash-update", interval=100),
    ]
)


# super basic example for testing:
@app.callback(
    [Output("amps", "value"), Output("volts", "value")],
    Input("dash-update", "n_intervals"),
)
def update_dash(_):
    if data.get("ID132HVBattAmpVolt"):
        amps = data["ID132HVBattAmpVolt"]["SmoothBattCurrent132"]
        volts = data["ID132HVBattAmpVolt"]["BattVoltage132"]
        return amps, volts
    return 0, 0


def run():
    server_thread = Thread(target=app.run_server, daemon=True)
    server_thread.start()
    try:
        get_data()
    except KeyboardInterrupt:
        pass


def get_data():
    global data
    while True:
        for queue in reader_queues:
            try:
                messages = queue.get_many(timeout=0.01)
            except Empty:
                continue
            for msg in messages:
                data[msg["name"]] = msg["data"]
