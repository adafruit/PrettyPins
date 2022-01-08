# PrettyPins

PrettyPins is designed to create lovely pinout diagrams. 

## Requirements
The following is a list of required software and files necessary to run PrettyPins:
* A local clone of the PrettyPins repository
* The Fritzing object file for the board for which you are generating a diagram (available [here](https://github.com/adafruit/Fritzing-Library/tree/master/parts))
* An SVG editor, such as InkScape (free and available for all major OS's) or Illustrator (not free, and not available for all major OS's)
* Python 3 installed on your machine
* A local clone of the CircuitPython repository (for boards that support CircuitPython)
* The latest Arduino core for the board-type you're working with installed on your machine (for boards that support Arduino)
* `pip install` the following libraries (in a virtual environment or otherwise):
  * `click`
  * `lxml`
  * `svgutils`
  * `svgwrite`
  * `xmltodict`

## Running PrettyPins
1. Place the Fritzing object file in the PrettyPins directory.
2. Run the PrettyPins command as shown below.
3. In the case of Arduino support, you must run the command TWICE for the Arduino pins to show up.
4. Open the `output.svg` and `pinlabels.svg` files into your SVG editor.
5. Save the `output.svg` file as something else, such as the name of the board you're diagramming.
   * In Illustrator, when you "Save as", click "Ok", (and "Yes" to replacing the file if it already exists), then, under "Advanced Options", change "CSS Properties" to "Presentation Attributes". and "Decimal Places" to "4". Then, click Ok.
6. Copy the different seconds of labels out of `pinlabels.svg` into your working board file, and arrange them properly.
   * For pins that are not easily accessible (such as NeoPixels or displays), either draw extra lines to the pin location, or create an icon for the pin next to the board and attach the labels to that.
   * If you are replacing an old diagram (as with many of the ATtiny boards), include any notes from the original diagram in the new one.
7. Verify the pin label layout with Kattni by providing a screenshot of your working board file.
8. Finalise the diagram with the pin legend, any text blocks and the title/URL.
9. Save the SVG as follows:
    * In Illustrator, do "Save as", click "Ok", (and "Yes" to replacing the file if it already exists), then, under "Advanced Options", change "CSS Properties" to "Presentation Attributes". and "Decimal Places" to "4". Then, click Ok.
    * In Inkscape, save the file.
10. Finally, save the file as both a PDF and a PNG as well.

## Upload Files
Once you have an SVG, PDF and PNG, you need to upload them to the following locations, and link to them where indicated.
#### The PNG
1. The PNG gets added to the Pinouts page of the guide, rendered, immediately below the board image at the top of the page.

#### The PDF
1. Upload to the board-specific EagleCAD PCB file repository on GitHub.
2. Link under "Files:" on the Downloads page in the applicable board guide.
3. Link on the Pinouts page in the applicable board guide (under the rendered PNG of the diagram).

#### The SVG
1. Upload the SVG to Learn as a file using Media > Upload, under the "Files" section on the Downloads page. Title the file "PrettyPins SVG for Board Name".

## Example PrettyPins Command Structure by Board Type
These are some examples of what the PrettyPins commandline command looks like, based on board chip type. More to be added soon!

#### ATMega328:
ATMega328 does not support CircuitPython.

```python3 parser.py "Adafruit Metro Mini.fzpz" None atmega328pins.csv -s "^IO([0-9])" "D\1"```

#### ATtiny8x
ATtiny8x does not support CircuitPython.

```python parser.py "Adafruit Trinket 3V.fzpz" None attiny8xpins.csv```

#### RP2040:
RP2040 does not have official Arduino support (yet).

```python3 parser.py "Adafruit Feather RP2040.fzpz" path/to/circuitpython/ports/raspberrypi/boards/adafruit_feather_rp2040/pins.c rp2040pins.csv```

```python3 parser.py "Adafruit ItsyBitsy RP2040.fzpz" path/to/circuitpython/ports/raspberrypi/boards/adafruit_itsybitsy_rp2040/pins.c rp2040pins.csv```

```python3 parser.py "Adafruit QT Py RP2040.fzpz" path/to/circuitpython/ports/raspberrypi/boards/adafruit_qtpy_rp2040/pins.c rp2040pins.csv```

#### ESP32-S2:

```python3 parser.py "Adafruit Feather ESP32-S2.fzpz" path/to/circuitpython/ports/espressif/boards/adafruit_feather_esp32s2/pins.c esp32s2pins.csv```

```python3 parser.py "Adafruit Metro ESP32-S2.fzpz" path/to/circuitpython/ports/espressif/boards/adafruit_metro_esp32s2/pins.c esp32s2pins.csv -s "^D([0-9])" "IO\1"```

```python3 parser.py "Adafruit MagTag 2.9in.fzpz" path/to/circuitpython/ports/espressif/boards/adafruit_magtag_2.9_grayscale/pins.c esp32s2pins.csv -s "^D([0-9])" "IO\1"```

```python3 parser.py "Adafruit FunHouse.fzpz"  path/to/circuitpython/ports/espressif/boards/adafruit_funhouse/pins.c esp32s2pins.csv -s "^D([0-9])" "IO\1"```


#### ESP32:

```python3 parser.py "Adafruit QT Py ESP32 Pico.fzpz" None -a ../../ArduinoSketches/hardware/espressif/esp32/variants/adafruit_qtpy_esp32  esp32pins.csv```


#### nRF52:

```python3 parser.py "Adafruit Feather nRF52840.fzpz"  path/to/circuitpython/ports/nrf/boards/feather_nrf52840_express/pins.c  nrf52840pins.csv -a ~/Library/Arduino15/packages/adafruit/hardware/nrf52/0.20.5/variants/feather_nrf52840_express```

```python3 parser.py "Adafruit ItsyBitsy nRF52840.fzpz"  path/to/circuitpython/ports/nrf/boards/itsybitsy_nrf52840_express/pins.c  nrf52840pins.csv -a ~/Library/Arduino15/packages/adafruit/hardware/nrf52/0.20.5/variants/itsybitsy_nrf52840_express```

```python3 parser.py "Adafruit nRF52840 CLUE.fzpz"  path/to/circuitpython/ports/nrf/boards/clue_nrf52840_express/pins.c  nrf52840pins.csv -a ~/Library/Arduino15/packages/adafruit/hardware/nrf52/0.20.5/variants/clue_nrf52840```
