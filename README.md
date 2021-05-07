# PrettyPins

examples:

```
python3 parser.py "Adafruit Feather RP2040.fzpz" C:\Users\ladyada\Dropbox\micropython\circuitpython\ports\raspberrypi\boards\adafruit_feather_rp2040\pins.c rp2040pins.csv
```

```
python3 parser.py "Adafruit ItsyBitsy RP2040.fzpz" C:\Users\ladyada\Dropbox\micropython\circuitpython\ports\raspberrypi\boards\adafruit_feather_rp2040\pins.c rp2040pins.csv
```

```
python3 parser.py "Adafruit QT Py RP2040.fzpz" C:\Users\ladyada\Dropbox\micropython\circuitpython\ports\raspberrypi\boards\adafruit_qtpy_rp2040\pins.c rp2040pins.csv
```

```python3 parser.py "Adafruit Metro ESP32-S2.fzpz" C:\Users\ladyada\Dropbox\micropython\circuitpython\ports\esp32s2\boards\adafruit_metro_esp32s2\pins.c esp32s2pins.csv -s "^D([0-9])" "IO\1"