# PrettyPins

examples:


RP2040:

```python3 parser.py "Adafruit Feather RP2040.fzpz" path/to/circuitpython/ports/raspberrypi/boards/adafruit_feather_rp2040/pins.c rp2040pins.csv```

```python3 parser.py "Adafruit ItsyBitsy RP2040.fzpz" path/to/circuitpython/ports/raspberrypi/boards/adafruit_itsybitsy_rp2040/pins.c rp2040pins.csv```

```python3 parser.py "Adafruit QT Py RP2040.fzpz" path/to/circuitpython/ports/raspberrypi/boards/adafruit_qtpy_rp2040/pins.c rp2040pins.csv```

ESP32-S2:

```python3 parser.py "Adafruit Metro ESP32-S2.fzpz" path/to/circuitpython/ports/esp32s2/boards/adafruit_metro_esp32s2/pins.c esp32s2pins.csv -s "^D([0-9])" "IO\1"```

```python3 parser.py "Adafruit MagTag 2.9in.fzpz" path/to/circuitpython/ports/esp32s2/boards/adafruit_magtag_2.9_grayscale/pins.c esp32s2pins.csv -s "^D([0-9])" "IO\1"```

```python3 parser.py "Adafruit FunHouse.fzpz"  path/to/circuitpython/ports/esp32s2/boards/adafruit_funhouse/pins.c esp32s2pins.csv -s "^D([0-9])" "IO\1"```

nRF52:

```python3 parser.py "Adafruit Feather nRF52840.fzpz"  path/to/circuitpython/ports/nrf/boards/feather_nrf52840_express/pins.c  nrf52840pins.csv -a ~/Library/Arduino15/packages/adafruit/hardware/nrf52/0.20.5/variants/feather_nrf52840_express```

```python3 parser.py "Adafruit ItsyBitsy nRF52840.fzpz"  path/to/circuitpython/ports/nrf/boards/itsybitsy_nrf52840_express/pins.c  nrf52840pins.csv -a ~/Library/Arduino15/packages/adafruit/hardware/nrf52/0.20.5/variants/itsybitsy_nrf52840_express```

```python3 parser.py "Adafruit nRF52840 CLUE.fzpz"  path/to/circuitpython/ports/nrf/boards/clue_nrf52840_express/pins.c  nrf52840pins.csv -a ~/Library/Arduino15/packages/adafruit/hardware/nrf52/0.20.5/variants/clue_nrf52840```
