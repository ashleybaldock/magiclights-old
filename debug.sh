#!/bin/sh

export DEBUG
export PORT=5000
export HOST=127.0.0.1
export SERIAL=/dev/tty.usbmodemfa131

python magiclights.py
