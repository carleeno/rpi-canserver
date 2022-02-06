# rpi-canserver
Raspberry Pi based can server using a pican2 duo


## Pi setup:

Allow can_reader to automatically bring can network link up/down:

Run `sudo visudo` and add this to the bottom of the file:
```
# Allow bringing up/down can network
%users ALL = NOPASSWD: /sbin/ip
```

Add the following to the end of `/boot/firmware/usercfg.txt`:
```
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
dtoverlay=spi-bcm2835-overlay
```

Ensure you have python3 and pip, then: `pip3 install python-can`

## Configuration:

If you have a pican DUO: edit config.py and set `pican_duo = True`

If you want to decode the messages, edit `can0_dbc` (and `can1_dbc` for pican DUO) to point to a .dbc file.

(by default it uses `Model3CAN.dbc`, download from https://github.com/joshwardell/model3dbc)

If you are decoding, it's recommended to set up a filter. Raw messages are not filtered, so .asc logging is not affected. 
However by filtering which messages are decoded, you'll save considerable CPU usage.

## Running:

`python3 main.py`