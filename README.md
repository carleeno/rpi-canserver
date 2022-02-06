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

If you have a pican DUO: edit main.py and set `PICAN_DUO = True`

## Running:

`python3 main.py`