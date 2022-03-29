# rpi-canserver
Raspberry Pi based can server using a pican2 duo


## Pi setup:

Allow can_reader to automatically bring can network link up/down:

Run `sudo visudo` and add this to the bottom of the file:
```
# Allow bringing up/down can network
%users ALL = NOPASSWD: /sbin/ip link set can*
```

Add the following to the end of `/boot/firmware/usercfg.txt`:
```
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=24
dtoverlay=spi-bcm2835-overlay
```

Ensure you have python3 and pip, then:

`python3 -m venv venv`

`source venv/bin/activate`

`pip install -r requirements.txt` (ok to ignore building wheel failures)

## Configuration:

If you only have a single-channel PICAN: edit config.py and set `pican_duo = False`

If you want to decode the messages, edit `can0_dbc` (and `can1_dbc` for pican DUO) to point to a .dbc file.

(by default it uses `Model3CAN.dbc`, download from https://github.com/joshwardell/model3dbc)

If you are decoding, it's recommended to set up a filter. Raw messages are not filtered, so .asc logging is not affected. 
However by filtering which messages are decoded, you'll save considerable CPU usage.

## Running:

`source venv/bin/activate`

`python3 main.py`