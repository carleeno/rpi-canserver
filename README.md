# rpi-canserver

Raspberry Pi based can server using a pican2 duo

## Pi setup

Add the following to the end of `/boot/firmware/usercfg.txt`:

```text
dtparam=spi=on
dtoverlay=mcp2515-can0,oscillator=16000000,interrupt=25
dtoverlay=mcp2515-can1,oscillator=16000000,interrupt=24
dtoverlay=spi-bcm2835-overlay
```

You'll need lm-sensors to get cpu temperature: `sudo apt install lm-sensors`

Install docker and docker-compose (Google is your friend)

## Bring up can network at boot

If you're using systemd-networkd, it's easy.

Create: `/etc/systemd/network/80-can0.network` (and `/etc/systemd/network/81-can1.network` if you have both)

```test
[Match]
Name=can0

[CAN]
BitRate=500K
RestartSec=100ms
```

(don't forget to change `Name=` to `can1` for the 2nd file)

Then reboot or restart systemd-networkd

## Configuration

If you only have a single-channel PICAN: edit config.py and set `pican_duo = False`

If you want to decode the messages, edit `dbc_file` to point to a .dbc file.

(by default it uses `Model3CAN.dbc`, download from <https://github.com/joshwardell/model3dbc>)

If you are decoding, it's recommended to set up a filter. Raw messages are not filtered, so .asc logging is not affected.
However by filtering which messages are decoded, you'll save considerable CPU usage.

After edits, run `docker-compose build`

## Running

`docker-compose up`

By default it will always restart the containers at boot.
