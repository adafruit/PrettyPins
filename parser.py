#!/usr/bin/python3

import click
import xml.etree.ElementTree as ET
from xml.dom import minidom
import xmltodict
import svgutils.transform as sg
import sys
import re
import csv
import svgwrite
import shutil
import zipfile
import glob
import os
import math
import time
import textwrap
import subprocess

MM_TO_PX = 96 / 25.4 # SVGs measure in px but maybe we want mm!
PX_TO_MM = 25.4 / 96 # SVGs measure in px but maybe we want mm!
FONT_HEIGHT_PX = 10.5
FONT_CHAR_W = 4

# SVG is canonically supposed to be 96 DPI, but something along the way
# (maybe it's just Illustrator import) is thinking it's 72, or is using
# points instead of pixels.
MM_TO_PT = 72 / 25.4
PT_TO_MM = 25.4 / 72
BOX_HEIGHT = 2.54 * MM_TO_PT  # 0.1 inch to match pin spacing
BOX_WIDTH_PER_CHAR = BOX_HEIGHT / 2
BOX_STROKE_WIDTH = 0.125 * MM_TO_PT
BOX_CORNER_RADIUS = (0.4 * MM_TO_PT, 0.4 * MM_TO_PT)
ROW_STROKE_WIDTH = 0.25 * MM_TO_PT
ROW_STROKE_COLOR = '#8C8C8C'
BOX_INSET = (0.2 * MM_TO_PT, 0.2 * MM_TO_PT)
LABEL_FONTSIZE = 6
LABEL_HEIGHTADJUST = 1.75
LABEL_FONT = "Courier New"
TITLE_FONTSIZE = 16
URL_FONTSIZE = 12


# The following table is derived from
# http://mkweb.bcgsc.ca/biovis2012/color-blindness-palette.png
# It provides 13 to 15 colors (plus white) that appear perceptually distinct
# to most types of color blindness (they do NOT appear as the SAME colors,
# merely DISTINGUISHABLE from one another).
# It is generally not advised (but occasionally acceptable) to use colors
# not in this table (as regular #RRGGBB), BUT they should be made distinct
# some other way -- for example, CircuitPython pin name boxes are light gray
# (not in table) but assigned an outline. Also, STEMMA QT SDA and SCL boxes
# are assigned colors of the physical wiring, so the wires and labels match
# (BOTH are then similarly 'off' to color blind users). Some of these entries
# are a bit vivid to the normally-sighted, but they should be used exacly,
# do NOT try to adjust a little lighter or darker, as the result might go in
# a different direction for color blind users. Pick a different index, or
# distinguish it with/without an outline, thanks.
palette = (
    '#FFFFFF', # Keeps list index in sync w/numbers in ref image (1-15)
    '#000000', # #1
    '#004949', # #2
    '#009292', # #3  do not use w/#7
    '#FF6DB6', # #4  do not use w/#13
    '#FFB6DB', # #5
    '#490092', # #6
    '#006DDB', # #7  do not use w/#3
    '#B66DFF', # #8
    '#6DB6FF', # #9
    '#B6DBFF', # #10
    '#920000', # #11
    '#924900', # #12
    '#DB6D00', # #13 do not use w/#4
    '#24FF24', # #14
    '#FFFF6D') # #15

# This is a sequence of 9 palette indices that appear in a chromatic-ish
# sequence for normal-sighted viewers, and are distinct and non-repeating
# for anyone else. MUX boxes, when drawn from center-to-outskirts in this
# order, are nicely appealing. If a chip type has fewer than 9 muxes,
# colors in the sequence can be skipped by adding an empty column in the
# CSV (e.g. brown isn't very appealing). For future ref, if more than 9
# muxes become necessary, maybe repeat the sequence but add a box outline?
chroma = (
    15, # Yellow
    14, # Green
    3,  # Teal
    10, # Cyan
    9,  # Light blue
    8,  # Purple
    5,  # Light Pink
    12, # Brown
    13) # Orange (after this, list repeats but adds box outline)
# NOT in this list, but still distinct and available for other uses, are
# #1 (black, used for ground), #11 (dark red, used for power), #6 (dark
# purple, used for control), #2 (dark teal, used for Arduino pin name), #7
# (medium blue, not currently used and should be avoided if possible as it
# appears similar to #3 for some) and #4 (hot pink, not used and also
# should be avoided as it resembles #13 orange to some.)

# This is a base set of pin themes that are common to ALL chips.
# Any additional 'muxed' functions get drawn in chroma sequence
# following left-to-right column order in CSV file.
themes = [
    {'type':'Power', 'fill':palette[11], 'font-weight':'bold'},
    {'type':'GND', 'fill':palette[1], 'font-weight':'bold'},
    {'type':'Control', 'fill':palette[6], 'font-weight':'bold'},
    {'type':'Arduino', 'fill':palette[2], 'font-weight':'bold'},
    {'type':'CircuitPython Name', 'fill':'#E6E6E6', 'outline':'auto', 'font-weight':'bold'},
    {'type':'QT_SCL', 'fill':'#FFFF00', 'font-weight':'bold'},
    {'type':'QT_SDA', 'fill':'#0000FF', 'font-weight':'bold'},
    ]

# some eagle cad names are not as pretty
conn_renames = [('!RESET', 'RESET'),
                ('D5_5V', 'D5'),
                ('+3V3', '3.3V'),
                ('3V3', '3.3V'),
                ('+5V', '5V')
                ]
product_url = None
product_title = None
chip_description = None
pinmuxes = None        # Set by get_chip_pinout() on CSV load
pinmux_in_use = None   # Ditto
arduino_in_use = False # Is set true if Arduino pin names found
longest_arduinopin = 0 # Longest label for Arduino pins (for box sizing)

# This function digs through the FZP (XML) file and the SVG (also, ironically, XML) to find what
# frtizing calls a connection - these are pads that folks can connect to! they are 'named' by
# eaglecad, so we should use good names for eaglecad nets that will synch with circuitpython names
def get_connections(fzp, svg, substitute):
    connections = []
    global product_url, product_title

    # check the FPZ for every 'connector' type element
    f = open(fzp)
    xmldict = xmltodict.parse(f.read())
    for c in xmldict['module']['connectors']['connector']:
        c_name = c['@name']     # get the pad name
        c_svg = c['views']['breadboardView']['p']['@svgId']   # and the SVG ID for the pad
        d = {'name': c_name, 'svgid': c_svg}
        connections.append(d)

    if 'url' in xmldict['module']:
        product_url = xmldict['module']['url']
    else:
        product_url = 'Missing product URL'
    product_title = xmldict['module']['title']
    print(product_title, product_url)
    #print(connections)

    # ok now we can open said matching svg xml
    xmldoc = minidom.parse(svg)

    # Find all circle/pads
    circlelist = xmldoc.getElementsByTagName('circle')
    for c in circlelist:
        try:
            idval = c.attributes['id'].value   # find the svg id
            cx = c.attributes['cx'].value      # x location
            cy = c.attributes['cy'].value      # y location
            d = next((conn for conn in connections if conn['svgid'] == c.attributes['id'].value), None)
            if d:
                d['cx'] = float(cx)
                d['cy'] = float(cy)
                d['svgtype'] = 'circle'
        except KeyError:
            pass
    # sometimes pads are ellipses, note they're often transformed so ignore the cx/cy
    ellipselist = xmldoc.getElementsByTagName('ellipse')
    for c in ellipselist:
        try:
            print(c)
            idval = c.attributes['id'].value   # find the svg id
            d = next((conn for conn in connections if conn['svgid'] == c.attributes['id'].value), None)
            if d:
                d['cx'] = None
                d['cy'] = None
                d['svgtype'] = 'ellipse'
        except KeyError:
            pass

    if substitute:
        for c in connections:
           c['name'] =  re.sub(substitute[0], substitute[1], c['name'])
    return connections

def get_arduino_mapping(connections, variantfolder):
    global longest_arduinopin
    if not variantfolder:
        return connections
    ###################################################### special case of very early chips
    if ("atmega328" in variantfolder) or ("atmega32u4" in variantfolder) or ("attiny8x" in variantfolder):
        pinmap8x = ["PB0", "PB1", "PB2", "PB3", "PB4"]
        pinmap328 = ["PD0", "PD1", "PD2", "PD3", "PD4", "PD5", "PD6", "PD7",
                     "PB0", "PB1", "PB2", "PB3", "PB4", "PB5",
                     "PC0", "PC1", "PC2", "PC3", "PC4", "PC5"]
        specialnames328 = {"A0" : "PC0", "A1" : "PC1", "A2" : "PC2",
                           "A3" : "PC3", "A4" : "PC4", "A5" : "PC5",
                           "A4/SDA" : "PC4", "A5/SCL" : "PC5",
                           "SS" : "PB2", "MOSI" : "PB3",
                           "MISO": "PB4", "SCK": "PB5"}
        pinmap32u4 = ["PD2", "PD3", "PD1", "PD0", "PD4", "PC6", "PD7", "PE6",
                      "PB4", "PB5", "PB6", "PB7", "PD6", "PC7",
                      "PB3", "PB1", "PB2", "PB0",
                      "PF7", "PF6", "PF5", "PF4", "PF1", "PF0"]
        specialnames32u4 = {"SDA" : "PD1", "SCL" : "PD0",
                            "MISO" : "PB3", "SCK" : "PB1", "MOSI" : "PB2",
                            "A0" : "PF7", "A1" : "PF6", "A2" : "PF5",
                            "A3" : "PF4", "A4" : "PF1", "A5" : "PF0" }
        
        if "attiny8x" in variantfolder:
            pinmap = pinmap8x
            specialnames = None
        if "atmega328" in variantfolder:
            pinmap = pinmap328
            specialnames = specialnames328
        if "atmega32u4" in variantfolder:
            pinmap = pinmap32u4
            specialnames = specialnames32u4
            
        for conn in connections:
            print(conn['name'])
            # digital pins
            matches = re.match(r'(IO|D|#)([0-9]+)', conn['name'])
            if matches:
                #print(matches)
                digitalname = matches.group(2)
                conn['pinname'] = pinmap[int(digitalname)]
                conn['arduinopin'] = digitalname
                longest_arduinopin = max(longest_arduinopin, len(str(conn['arduinopin'])))
            # other pins :/
            if specialnames:
                if conn['name'] in specialnames:
                    conn['pinname'] = specialnames[conn['name']]
                    conn['arduinopin'] = pinmap.index(conn['pinname'])
                    longest_arduinopin = max(longest_arduinopin, len(str(conn['arduinopin'])))
        #print(connections)
        return connections
        
    ###################################################### NRF52 board variant handler
    elif "nrf52" in variantfolder.lower():
        # copy over the variant.cpp minus any includes

        variantcpp = open(variantfolder+"/"+"variant.cpp").readlines()
        outfilecpp = open("variant.cpp", "w")
        # Add some new header text so we can compile the raw variant cpp/h without arduino BSP
        outfilecpp.write("""
#include <stdint.h>
#include <stdio.h>
#include "variant.h"
#define OUTPUT 1
#define INPUT 0
#define HIGH 1
#define LOW 0
#define ledOff(x) (x)
#define pinMode(x, y) (x)
#define digitalWrite(x, y) (x)

        """)
        for line in variantcpp:
            # cut out the arduino deps
            if "#include" in line:
                continue
            outfilecpp.write(line)

        # here's the code that will actually print out the pin mapping as a CSV:
        outfilecpp.write("""
int main(void) {
   for (uint32_t pin=0; pin<sizeof(g_ADigitalPinMap)/4; pin++) {
     uint8_t portnum = g_ADigitalPinMap[pin] / 32;
     uint8_t portpin = g_ADigitalPinMap[pin] % 32;
     printf("%d", pin);
""")
        for analog in range(0, 32):
            outfilecpp.write("#ifdef PIN_A%d\n" % analog)
            outfilecpp.write("     if (PIN_A%d == pin) printf(\"/A%d\");\n" % (analog, analog))
            outfilecpp.write("#endif\n")
        outfilecpp.write("""
     printf(", P%d.%02d\\n", portnum, portpin);
   }
}
""")
        outfilecpp.close()

        # ditto for the header file, copy it over, except remove all arduino headers
        varianth = open(variantfolder+"/"+"variant.h").readlines()
        outfileh = open("variant.h", "w")
        outfileh.write("#include <stdint.h>\n")
        for line in varianth:
            if "#include" in line:
                continue
            outfileh.write(line)
        outfileh.close()

    ###################################################### SAMDxx board variant handler
    elif "samd" in variantfolder.lower():
        # copy over the variant.cpp minus any includes

        variantcpp = open(variantfolder+"/"+"variant.cpp").readlines()
        outfilecpp = open("variant.cpp", "w")
        # Add some new header text so we can compile the raw variant cpp/h without arduino BSP
        outfilecpp.write("""
#include <stdint.h>
#include <stdio.h>
#include "variant.h"
#define OUTPUT 1
#define INPUT 0
#define HIGH 1
#define LOW 0
#define ledOff(x) (x)
#define pinMode(x, y) (x)
#define digitalWrite(x, y) (x)


#define EXTERNAL_INT_NMI 32
#define PIN_ATTR_PWM 0
#define PIN_ATTR_ANALOG 0
#define PIN_ATTR_ANALOG_ALT 0
#define PIN_ATTR_DIGITAL 0
#define PIO_SERCOM 0
#define PIO_DIGITAL 0
#define PIO_ANALOG 0
#define PIO_SERCOM_ALT 0
#define PIO_OUTPUT 0
#define PIO_TIMER 0
#define PIO_TIMER_ALT 0
#define PIO_PWM 0
#define PIO_PWM_ALT 0
#define PIN_ATTR_TIMER 0        
#define PIN_ATTR_TIMER_ALT 0        
#define PIO_COM 0
#define PORTA 0
#define PORTB 1
#define PORTC 2
#define PORTD 3
#define DAC_Channel0 0
""")
        for define in ("NOT_ON_TIMER", "NOT_ON_PWM", "No_ADC_Channel",
                       "EXTERNAL_INT_NONE", "PIN_ATTR_NONE",
                       "PIN_ATTR_PWM_E", "PIN_ATTR_PWM_F", "PIN_ATTR_PWM_G",
                       "DAC_Channel1", "TCC_INST_NUM", "TC_INST_NUM", 
                       "NOT_A_PORT", "PIO_NOT_A_PIN", "PIN_NOT_A_PIN"):
            outfilecpp.write("#define %s 10\n" % define)
        for adc in range(0, 32):
            outfilecpp.write("#define ADC_Channel%d %d\n" % (adc, adc))
        for irq in range(0, 32):
            outfilecpp.write("#define EXTERNAL_INT_%d %d\n" % (irq, irq))
        for tcc in range(0, 8):
            outfilecpp.write("#define PWM0_CH%d %d\n" % (tcc, tcc))
            outfilecpp.write("#define TCC0_CH%d %d\n" % (tcc, tcc))
            outfilecpp.write("#define PWM1_CH%d %d\n" % (tcc, tcc))
            outfilecpp.write("#define TCC1_CH%d %d\n" % (tcc, tcc))
            outfilecpp.write("#define TCC%d_GCLK_ID %d\n" % (tcc, tcc))
        for tc in range(0, 8):
            outfilecpp.write("#define PWM2_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TCC2_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TCC3_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TCC4_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define PWM3_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TC3_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define PWM4_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TC7_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TC6_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TC5_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TC4_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TC2_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TC1_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TC0_CH%d %d\n" % (tc, tc))
            outfilecpp.write("#define TC%d_GCLK_ID %d\n" % (tc, tc))
        outfilecpp.write("""
typedef struct _PinDescription
{
  uint32_t       ulPort ;
  uint32_t        ulPin ;
  uint32_t        ulPinType ;
  uint32_t        ulPinAttribute ;
  uint32_t  ulADCChannelNumber ;
  uint32_t     ulPWMChannel ;
  uint32_t      ulTCChannel ;
  uint32_t ulExtInt ;
} PinDescription ;

        """)
        blocklist = ("#include", "extern", "apTCInstances", "IrqHandler", "Uart", "SERCOM ")
        for line in variantcpp:
            # cut out the arduino deps
            if any([block in line for block in blocklist]):
                continue
            outfilecpp.write(line)

        # here's the code that will actually print out the pin mapping as a CSV:
        outfilecpp.write("""
int main(void) {
   for (uint32_t pin=0; pin<sizeof(g_APinDescription)/sizeof(PinDescription); pin++) {
     uint8_t portnum = g_APinDescription[pin].ulPort;
     uint8_t portpin = g_APinDescription[pin].ulPin;
     printf("%d", pin);
""")
        for analog in range(0, 32):
            outfilecpp.write("#ifdef PIN_A%d\n" % analog)
            outfilecpp.write("      if ((PIN_A%d == pin) || ((g_APinDescription[PIN_A%d].ulPort == portnum) && (g_APinDescription[PIN_A%d].ulPin == portpin))) printf(\"/A%d\");\n" % (analog, analog, analog, analog))
            outfilecpp.write("#endif\n")
        outfilecpp.write("""
     printf(", P%c%02d\\n", 'A'+portnum, portpin);
   }
}
""")
        outfilecpp.close()

        # ditto for the header file, copy it over, except remove all arduino headers
        varianth = open(variantfolder+"/"+"variant.h").readlines()
        outfileh = open("variant.h", "w")
        outfileh.write("#include <stdint.h>\n")
        blocklist = ("#include", "extern SERCOM", "extern Uart")
        for line in varianth:
            if any([block in line for block in blocklist]):
                continue
            outfileh.write(line)

        outfileh.close()
        arduinopins = ""

    ###################################################### SAMDxx board variant handler
    elif "esp32" in variantfolder.lower():
        for conn in connections:
            print(conn['name'])
            # digital pins
            iomatches = re.match(r'(GPIO|IO|D|I|#)([0-9]+)', conn['name'])
            if iomatches:
                print(iomatches)
                digitalname = iomatches.group(2)
                conn['pinname'] = digitalname
                #conn['arduinopin'] = digitalname
                longest_arduinopin = max(longest_arduinopin, len(digitalname))
            else:
                conn['pinname'] = conn['name']

        # open the file
        varianth = open(variantfolder+"/"+"pins_arduino.h").readlines()
        arduinopins = ""
        for line in varianth:
            #print(line)
            # find the const defines
            matches2 = re.match(r'\s*static\s*const\s*uint8_t\s*([A-Z0-9_]+)\s*=\s*([0-9]+)\s*;.*', line)
            if matches2:
                prettyname = matches2[1]
                pinnumber = matches2[2]
                print(prettyname, pinnumber)
                for conn in connections:
                    if conn['pinname'] == prettyname:
                        conn['pinname'] = pinnumber
                    #print(conn)
                arduinopins +=  pinnumber + ", " + prettyname + "\n"
        # ok after we map everything, lets find internal pins
        for pinpair in arduinopins.split('\n'):
            if not pinpair:
                continue
            pinnumber, prettyname = pinpair.split(",")
            conn = next((c for c in connections if c.get('pinname') == pinnumber), None)
            if conn:
                continue
            print("Found an internal pin!")
            newconn = {'name': prettyname, 'pinname': pinnumber}
            print(newconn)
            connections.append(newconn)
        #print(arduinopins)


    else:
        raise NotImplementedError("Unknown Arduino variant type! (if RP2040, leave off -a arguments and try again)", variantfolder.lower())

    if not arduinopins:  # some variants can auto-extract the pins for us, if not we do it the hard way
        time.sleep(1)
        # now compile it!
        compileit = subprocess.Popen("g++ -w variant.cpp -o arduinopins", shell=True, stdout=subprocess.PIPE)
        #print(compileit.stdout.read())
        runit = subprocess.Popen("./arduinopins", shell=True, stdout=subprocess.PIPE)
        time.sleep(1)
        arduinopins = runit.stdout.read().decode("utf-8")
        #print(arduinopins)
        #exit()
    for pinpair in arduinopins.split("\n"):
        if not pinpair:
            continue
        arduinopin, pinname = pinpair.split(", ")
        for conn in (c for c in connections if c.get('pinname') == pinname):
            if 'arduinopin' in conn:
                continue
            conn['arduinopin'] = arduinopin
            print(arduinopin, pinname, conn)
        longest_arduinopin = max(longest_arduinopin, len(arduinopin))

    return connections

def get_circuitpy_aliases(connections, circuitpydef):
    # now check the circuitpython definition file
    pyvar = open(circuitpydef).readlines()
    pypairs = []
    for line in pyvar:
        # find the QSTRs
        matches = re.match(r'.*MP_QSTR_(.*)\)\s*,\s*MP_ROM_PTR\(&pin_(.*)\)', line)
        if not matches:
            continue

        # Special case for nRF52840, we cant use . in the pin name so rename P0_0 -> P0.0
        # so it matches the 'true' name of the pin
        pinname = matches.group(2)
        if re.match(r"P[0-1]_[0-9]+", pinname):
            pinname = pinname.replace("_", ".")
        pypairs.append([matches.group(1), pinname])

    # for every known connection, lets set the 'true' pin name
    for conn in connections:
        pypair = next((p for p in pypairs if p[0] == conn['name']), None)
        if not pypair:
            #print("Couldnt find python name for ", conn['name'])
            continue
        # set the true pin name!
        conn['pinname'] = pypair[1]

    # for any remaining un-matched qstr pairs, it could be aliases or internal pins
    for pypair in pypairs:
        #print(pypair)
        connection = next((c for c in connections if c.get('pinname') == pypair[1]), None)
        if connection:
            print("Found an alias!")
            if not 'alias' in connection:
                connection['alias'] = []
            connection['alias'].append(pypair[0])
        else:
            print("Found an internal pin!")
            newconn = {'name': pypair[0], 'pinname': pypair[1]}
            print(newconn)
            connections.append(newconn)

    # now look for pins that havent been accounted for!
    for line in pyvar:
        matches = re.match(r'.*MP_ROM_QSTR\(MP_QSTR_(.*)\),\s+MP_ROM_PTR\(&pin_(.*)\)', line)
        if not matches:
            continue
        qstrname = matches.group(1)
        gpioname = matches.group(2)
        connection = next((c for c in connections if c.get('pinname') == gpioname), None)
        if not connection:
            print(qstrname, gpioname)

    return connections

def get_chip_pinout(connections, pinoutcsv):
    global themes, chip_description, pinmuxes, pinmux_in_use

    with open(pinoutcsv, mode='r') as infile:
        pinarray = []
        reader = csv.reader(infile)
        csvlist = [row for row in reader]
        header = csvlist.pop(0)
        for pin in csvlist:
            if pin[0] == "DESCRIPTION":
                chip_description = pin[1]
                continue
            gpioname = pin[0]
            d = {}
            for i,mux in enumerate(pin):
                d[header[i]] = mux
            pinarray.append(d)
        pinmuxes = header
        pinmux_in_use = [0] * len(pinmuxes)
    print("Mux options available: ", pinmuxes)
    return pinarray


def draw_label(dwg, group, label_text, label_type, box_x, box_y, box_w, box_h):

    # Some initial assumptions on label style, might override later below
    box_outline = None # No box outline
    text_weight = None # Normal text weight
    text_color = 'black'

    # Check if label_type is in the theme set...
    theme = next((theme for theme in themes if theme['type'] == label_type), None)

    if theme: # label_type IS one of the global theme settings
        box_fill = theme['fill']
        if 'outline' in theme:
            box_outline = theme['outline']
        if 'font-weight' in theme:
            text_weight = theme['font-weight']
    elif label_type == 'Arduino':
        box_fill = palette[2]
    else: # label_type IS NOT in themes, must be a muxed pin.
        # Switch to chromatic color scheme based on index of label_type
        # in the CSV pinmuxes header.
        box_fill = palette[chroma[pinmuxes.index(label_type) % len(chroma)]]
        if pinmuxes.index(label_type) >= len(chroma):
            box_outline = 'auto' # Repeating color sequence, add outline

    if (box_fill == 'black'):
        text_color = 'white'
    elif (box_fill[0] == '#'):
        red = int(box_fill[1:3], 16)
        green = int(box_fill[3:5], 16)
        blue = int(box_fill[5:7], 16)
        lightness = red * 0.299 + green * 0.587 + blue * 0.114
        # This might offer better contrast in some settings, TBD
        #lightness = math.sqrt(red * red * 0.299 + green * green * 0.587 + blue * blue * 0.114)
        # Use white text on dark backgrounds
        if lightness < 128:
            text_color = 'white'
        # If outline is 'auto', stroke w/50% brightness of fill color.
        if box_outline == 'auto':
            rgb = ((red // 2)) << 16 | ((green // 2) << 8) | (blue // 2)
            box_outline = '#{0:0{1}X}'.format(rgb, 6)

    # draw a box
    box_x += BOX_INSET[0]  # Inset a bit so boxes aren't touching
    box_y += BOX_INSET[1]
    box_w -= BOX_INSET[0] * 2
    box_h -= BOX_INSET[1] * 2
    if box_outline:
        box_x += BOX_STROKE_WIDTH * 0.5 # Inset further for stroke
        box_y += BOX_STROKE_WIDTH * 0.5 # (so box extents visually align)
        box_w -= BOX_STROKE_WIDTH
        box_h -= BOX_STROKE_WIDTH
        group.add(dwg.rect(
            (box_x, box_y),
            (box_w, box_h),
            BOX_CORNER_RADIUS[0] - BOX_STROKE_WIDTH * 0.5,
            BOX_CORNER_RADIUS[1] - BOX_STROKE_WIDTH * 0.5,
            stroke = box_outline,
            stroke_width = BOX_STROKE_WIDTH,
            fill = box_fill
            ))
    else:
        group.add(dwg.rect(
            (box_x, box_y),
            (box_w, box_h),
            BOX_CORNER_RADIUS[0], BOX_CORNER_RADIUS[1],
            fill = box_fill
            ))
    if label_text:
        if text_weight:
            group.add(dwg.text(
                label_text,
                insert = (box_x+box_w/2, box_y+box_h/2+LABEL_HEIGHTADJUST),
                font_size = LABEL_FONTSIZE,
                font_family = LABEL_FONT,
                font_weight = text_weight,
                fill = text_color,
                text_anchor = "middle",
                ))
        else:
            group.add(dwg.text(
                label_text,
                insert = (box_x+box_w/2, box_y+box_h/2+LABEL_HEIGHTADJUST),
                font_size = LABEL_FONTSIZE,
                font_family = LABEL_FONT,
                fill = text_color,
                text_anchor = "middle",
                ))


def draw_pinlabels_svg(connections):
    global arduino_in_use
    
    dwg = svgwrite.Drawing(filename=str("pinlabels.svg"), profile='tiny', size=(100,100))

    # collect all muxstrings to calculate label widths:
    muxstringlen = {}
    for i, conn in enumerate(connections):
        if not conn.get('mux'):
            continue
        for mux in conn['mux']:
            if not mux in muxstringlen:
                muxstringlen[mux] = 0
            muxstringlen[mux] = max(muxstringlen[mux], len(conn['mux'][mux]))
    #print(muxstringlen)

    # group connections by cx/cy
    tops = sorted([c for c in connections if c['location'] == 'top'], key=lambda k: k['cx'])
    bottoms = sorted([c for c in connections if c['location'] == 'bottom'], key=lambda k: k['cx'])
    rights = sorted([c for c in connections if c['location'] == 'right'], key=lambda k: k['cy'])
    lefts = sorted([c for c in connections if c['location'] == 'left'], key=lambda k: k['cy'])
    others = [c for c in connections if c['location'] == 'unknown']
    #print(connections)

    # A first pass through all the connectors draws the
    # row lines behind the MUX boxes
    group = []
    for i, conn in enumerate(tops+[None,]+bottoms+[None,]+rights+[None,]+lefts+[None,]+others):
        if conn == None: # Gap between groups
            continue
        box_x = 0
        box_w = max(6, len(conn['name'])+1) * BOX_WIDTH_PER_CHAR
        # If it's a left/bottom box, and wider than the standard width,
        # scoot left so the right edge is aligned with other boxes.
        if conn['location'] in ('left', 'bottom'):
            box_x -= box_w - 6 * BOX_WIDTH_PER_CHAR
        last_used_x = box_x
        first_box_w = box_w
        last_used_w = box_w
        if conn['location'] in ('top', 'right', 'unknown'):
            box_x += box_w

        # Adjust endpoint if there's an Arduino pin defined.
        # Neither a theme nor a mux, just a weird one-off...
        if 'arduinopin' in conn:
            #box_w = (longest_arduinopin + 1) * BOX_WIDTH_PER_CHAR
            box_w = longest_arduinopin * BOX_WIDTH_PER_CHAR

            if conn['location'] in ('top', 'right', 'unknown'):
                last_used_x = box_x # Save-and-increment
                box_x += box_w
            elif conn['location'] in ('left', 'bottom'):
                box_x -= box_w # Increment-and-save
                last_used_x = box_x
            last_used_w = box_w

        if conn.get('mux'): # power pins don't have muxing, its cool!
            for mux in conn['mux']:
                box_w = (muxstringlen[mux]+1) * BOX_WIDTH_PER_CHAR
                # Increment box_x regardless to maintain mux columns.
                if conn['location'] in ('top', 'right', 'unknown'):
                    # Save-and-increment (see notes in box-draw loop later)
                    if conn['mux'][mux]:
                        last_used_x = box_x # For sparse table rendering
                        last_used_w = box_w
                    box_x += box_w
                if conn['location'] in ('bottom', 'left'):
                    # Increment-and-save
                    box_x -= box_w
                    if conn['mux'][mux]:
                        last_used_x = box_x # For sparse table rendering
                        last_used_w = box_w
        line_y = (i + 0.5) * BOX_HEIGHT
        g = dwg.g()     # Create group for connection
        group.append(g) # Add to list
        if conn['location'] in ('top', 'right', 'unknown'):
            g.add(dwg.line(start=(-4, line_y), end=(last_used_x + last_used_w * 0.5, line_y), stroke=ROW_STROKE_COLOR, stroke_width = ROW_STROKE_WIDTH, stroke_linecap='round'))
        if conn['location'] in ('bottom', 'left'):
            g.add(dwg.line(start=(6 * BOX_WIDTH_PER_CHAR + 4, line_y), end=(last_used_x + last_used_w * 0.5, line_y), stroke=ROW_STROKE_COLOR, stroke_width = ROW_STROKE_WIDTH, stroke_linecap='round'))

    # pick out each connection
    group_index = 0 # Only increments on non-None connections, unlike enum
    for i, conn in enumerate(tops+[None,]+bottoms+[None,]+rights+[None,]+lefts+[None,]+others):
        if conn == None:
            continue  # a space!
        #print(conn)

        # start with the pad name
        box_x = 0
        box_y = BOX_HEIGHT * i
        # First-column boxes are special
        box_w = max(6, len(conn['name'])+1) * BOX_WIDTH_PER_CHAR
        box_h = BOX_HEIGHT

        name_label = conn['name']

        # clean up some names!

        label_type = 'CircuitPython Name'
        if name_label in ("3.3V", "VMAX", "VHIGH", "VIN", "5V", "VBAT", "VBUS", "VHI", "VCCIO", "VIO"):
            label_type = 'Power'
        if name_label in ("GND"):
            label_type = 'GND'
        if name_label in ("EN", "RST", "RESET", "SWCLK", "SWC", "SWDIO", "SWD"):
            label_type = 'Control'
        if name_label in ('SCL', 'SCL1', 'SCL0') and conn.get('svgtype') == 'ellipse':
            # special stemma QT!
            label_type = 'QT_SCL'
        if name_label in ('SDA', 'SDA1', 'SDA0') and conn.get('svgtype') == 'ellipse':
            # special stemma QT!
            label_type = 'QT_SDA'

        # Draw the first-column box (could be power pin or Arduino pin #)
        # (this box/label relates to the global 'themes' list).
        # If it's in left/bottom groups, scoot left a little if box is
        # wider than the 6-char default (so right edges align).
        if conn['location'] in ('left', 'bottom'):
            box_x -= box_w - 6 * BOX_WIDTH_PER_CHAR
        draw_label(dwg, group[group_index], name_label, label_type, box_x, box_y, box_w, box_h)
        # Increment box_x only on 'right' locations, because the behavior
        # for subsequent right boxes is to draw-and-increment, whereas
        # 'left' boxes increment-and-draw.
        if conn['location'] in ('top', 'right', 'unknown'):
            box_x += box_w
        mark_as_in_use(label_type)

        # Arduino pins are sort of brute-force wedged in here, neither a
        # theme nor a muxed pin...the position and label-drawing from
        # above are duplicated (except box_x decrement is different).
        if 'arduinopin' in conn:
            box_w = (longest_arduinopin + 1) * BOX_WIDTH_PER_CHAR
            if conn['location'] in ('left', 'bottom'):
                box_x -= box_w
            draw_label(dwg, group[group_index], conn['arduinopin'], 'Arduino', box_x, box_y, box_w, box_h)
            if conn['location'] in ('top', 'right', 'unknown'):
                box_x += box_w
            arduino_in_use = True

        if conn.get('mux'): # power pins don't have muxing, its cool!
            for mux in conn['mux']:
                label = conn['mux'][mux] # Label (if any) for this pin/mux
                if muxstringlen[mux]:    # Typical label length for this mux
                    box_w = (muxstringlen[mux]+1) * BOX_WIDTH_PER_CHAR
                else:
                    box_w = 0
                if not label:
                    # Increment box_x regardless for sparse tables
                    if conn['location'] in ('top', 'right', 'unknown'):
                        box_x += box_w
                    if conn['location'] in ('bottom', 'left'):
                        box_x -= box_w
                    continue
                if mux == 'GPIO':  # the underlying pin GPIO name
                    label_type = 'Port'
                elif mux in ('SPI', 'HS/QSPI', 'QSPI/CAN') :  # SPI ports
                    label_type = 'SPI'
                elif mux in ('I2C',):  # I2C ports
                    label_type = 'I2C'
                elif mux in ('UART', 'Debug'):  # UART ports
                    label_type = 'UART'
                elif mux == 'PWM':  # PWM's
                    label_type = 'PWM'
                elif mux in('Touch', 'TOUCH'):  # touch capable
                    label_type = 'Touch'
                elif mux == 'ADC':  # analog ins
                    label_type = 'Analog'
                elif mux == 'Arduino ADC':  # analog ins
                    label_type = 'SERCOM'
                elif mux == 'Other':
                    label_type = 'I2C'
                elif mux == 'Power Domain':
                    label_type = 'Power Domain'
                elif mux in ('High Speed', "PCC"):
                    label_type = 'High Speed'
                elif mux == 'Low Speed':
                    label_type = 'Low Speed'
                elif mux == 'RTC':
                    label_type = 'Low Speed'
                elif mux == 'Speed':
                    label_type = 'Speed'
                elif mux in('Special', 'SPECIAL'):
                    label_type = 'Special'
                elif mux == 'INT':
                    label_type = 'Interrupt'
                elif mux == 'DAC/AREF':
                    label_type = 'DAC/AREF'
                elif mux == 'SERCOM':
                    label_type = 'SERCOM'
                elif mux == 'SERCOM Alt':
                    label_type = 'SERCOM Alt'
                elif mux == 'Timer':
                    label_type = 'Timer'
                elif mux == 'Timer Alt':
                    label_type = 'Timer Alt'
                elif mux == 'Timer Alt2':
                    label_type = 'Timer Alt2'
                elif mux in ('SDMMC', "I2S"):
                    label_type = 'SERCOM'
                else:
                    continue
                
                # Here, labels are chromatic mux items, not in themes
                if conn['location'] in ('top', 'right', 'unknown'):
                    # Draw-and-increment
                    draw_label(dwg, group[group_index], label, mux, box_x, box_y, box_w, box_h)
                    box_x += box_w
                if conn['location'] in ('bottom', 'left'):
                    # Increment-and-draw
                    box_x -= box_w
                    draw_label(dwg, group[group_index], label, mux, box_x, box_y, box_w, box_h)

                mark_as_in_use(mux) # Show label type on legend
        else:
            # For power pins with no mux, keep legend up to date
            # and don't 'continue,' so group_index keeps in sync.
            mark_as_in_use(label_type)

        dwg.add(group[group_index])
        group_index += 1 # Increment on non-None connections

    # Add legend
    g = dwg.g()
    box_y = BOX_HEIGHT * (i + 4)
    # Draw legend items for in-use themes
    for theme in themes:
        # Skip themes not in use, and the STEMMA QT connector
        if 'in_use' in theme and not theme['type'].startswith('QT_'):
            box_y = draw_legend_box(dwg, g, theme['type'], box_y)
    # Wedge the Arduino pin in there if needed
    if arduino_in_use:
        box_y = draw_legend_box(dwg, g, 'Arduino', box_y)
    # And then add in-use pin mux items to legend
    for i, mux in enumerate(pinmuxes):
        if pinmux_in_use[i]:
            box_y = draw_legend_box(dwg, g, mux, box_y)
    dwg.add(g)

    # add title and url
    g = dwg.g()
    g.add(dwg.text(
        product_title,
        insert = (0, -40),
        font_size = TITLE_FONTSIZE,
        font_family = LABEL_FONT,
        font_weight = 'bold',
        fill = 'black',
        text_anchor = 'middle'
        ))
    g.add(dwg.text(
        product_url,
        insert = (0, -25),
        font_size = URL_FONTSIZE,
        font_family = LABEL_FONT,
        font_weight = 'bold',
        fill = 'black',
        text_anchor = 'middle'
        ))
    dwg.add(g)

    print(chip_description)
    box_y += 30
    g = dwg.g() # Create group for description
    strings = textwrap.wrap(chip_description, width=40)
    for s in strings:
        g.add(dwg.text(
            s,
            insert = (0, box_y),
            font_size = LABEL_FONTSIZE,
            font_family = LABEL_FONT,
            font_weight = 'normal',
            fill = 'black',
            text_anchor = 'start',
            ))
        box_y += LABEL_FONTSIZE
    dwg.add(g)

    dwg.save()


# Draws colored box and label, returns next avail Y position
def draw_legend_box(dwg, g, label_text, box_y):
    draw_label(dwg, g, None, label_text, 0, box_y, BOX_HEIGHT, BOX_HEIGHT)
    if label_text == 'Arduino':
        label_text = 'Arduino Name'
    g.add(dwg.text(
        label_text,
        insert = (BOX_HEIGHT * 1.2, box_y+BOX_HEIGHT/2+LABEL_HEIGHTADJUST),
        font_size = LABEL_FONTSIZE,
        font_family = LABEL_FONT,
        font_weight = 'bold',
        fill = 'black',
        text_anchor = 'start'
        ))
    return box_y + BOX_HEIGHT

# Add an 'in_use' key to themes that get referenced.
# Only these items are shown on the legend.
def mark_as_in_use(label_type):
    # If label_type matches a theme, add/set 'in_use' element:
    for theme in themes:
        if theme['type'] == label_type:
            theme['in_use'] = '1'
            return
    # If label_type didn't match any themes, it must be a pinmux,
    # marked in a simple array.
    pinmux_in_use[pinmuxes.index(label_type)] = 1


@click.command()
@click.argument('FZPZ')
@click.argument('circuitpydef')
@click.argument('pinoutcsv')
@click.option('-a', '--arduino', 'arduinovariantfolder')
@click.option('-s', '--substitute', 'substitute', nargs=2)
def parse(fzpz, circuitpydef, pinoutcsv, arduinovariantfolder, substitute):
    # fzpz are actually zip files!
    shutil.copyfile(fzpz, fzpz+".zip")
    # delete any old workdir
    try:
        shutil.rmtree('workdir')
    except FileNotFoundError:
        pass
    # unzip into the work dir
    with zipfile.ZipFile(fzpz+".zip", 'r') as zip_ref:
        zip_ref.extractall('workdir')
    fzpfilename = glob.glob(r'workdir/*.fzp')[0]
    svgfilename = glob.glob(r'workdir/svg.breadboard*.svg')[0]
    time.sleep(0.5)
    os.remove(fzpz+".zip")

    # get the connections dictionary
    connections = get_connections(fzpfilename, svgfilename, substitute)

    # rename any that need it
    for conn in connections:
        for rename in conn_renames:
            if conn['name'] == rename[0]:
                conn['name'] = rename[1]

    # find the 'true' GPIO pin names via the circuitpython file
    # e.g. "MISO" and "D2" map to "GPIO03" or "P0.04"
    if circuitpydef != "None":
        connections = get_circuitpy_aliases(connections, circuitpydef)

    # find the mapping between gpio pins and arduino pins
    # atmega 328's/32u4 dont have a mapping
    if not arduinovariantfolder and pinoutcsv == "atmega328pins.csv":
        arduinovariantfolder = "atmega328"
    if not arduinovariantfolder and pinoutcsv == "atmega32u4pins.csv":
        arduinovariantfolder = "atmega32u4"
    if not arduinovariantfolder and pinoutcsv == "attiny8xpins.csv":
        arduinovariantfolder = "attiny8x"
    connections = get_arduino_mapping(connections, arduinovariantfolder)
    # open and parse the pinout mapper CSV
    pinarray = get_chip_pinout(connections, pinoutcsv)
    #print(pinarray)
    
    # get SVG width and height
    bb_sg = sg.fromfile(svgfilename)
    bb_root = bb_sg.getroot()
    svg_width = bb_sg.width
    svg_height = bb_sg.height
    if "in" in svg_width:
        svg_width = 25.4 * float(svg_width[:-2]) * MM_TO_PX
    elif "mm" in svg_width:
        svg_width = float(svg_width[:-2]) * MM_TO_PX
    else:
        raise RuntimeError("Dont know units of width!", svg_width)
    if "in" in svg_height:
        svg_height = 25.4 * float(svg_height[:-2]) * MM_TO_PX
    elif "mm" in svg_height:
        svg_height = float(svg_height[:-2]) * MM_TO_PX
    else:
        raise RuntimeError("Dont know units of width!", svg_height)

    print("Width, Height in px: ", svg_width, svg_height)

    # Create a new SVG as a copy!
    newsvg = sg.SVGFigure()
    newsvg.set_size(("%dpx" % svg_width, "%dpx" % svg_height))
    #print(newsvg.get_size())
    # DO NOT SCALE THE BREADBOARD SVG. We know it's 1:1 size.
    # If things don't align, issue is in the newly-generated pin table SVG.
    #bb_root.rotate(90)
    #bb_root.moveto(0, 0, 1.33)
    newsvg.append(bb_root)
    newsvg.save("output.svg")

    # try to determine whether its top/bottom/left/right
    sh = svg_height * 0.75  # fritzing scales everything by .75 which is confusing!
    sw = svg_width * 0.75  # so get back to the size we think we are
    #print("scaled w,h", sw, sh)
    for conn in connections:
        if not conn.get('cy'):
            conn['location'] = 'unknown'
        elif conn['cy'] < 12:
            conn['location'] = 'top'
        elif conn['cy'] > sh-12:
            conn['location'] = 'bottom'
        elif conn['cx'] > sw-12:
            conn['location'] = 'right'
        elif conn['cx'] < 12:
            conn['location'] = 'left'
        else:
            conn['location'] = 'unknown'
        print(conn)

        # add muxes to connections
        if not 'pinname' in conn:
            continue
        # find muxes next

        muxes = next((pin for pin in pinarray if pin['GPIO'] == conn['pinname']), None)
        #print("***", muxes)
        conn['mux'] = muxes
    draw_pinlabels_svg(connections)
    
    newsvg.save("output.svg")




if __name__ == '__main__':
    parse()
