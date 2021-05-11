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
    '#004949', # #1
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
    12, # Brown
    13, # Orange
    15, # Yellow
    14, # Green
    3,  # Teal
    10, # Cyan
    9,  # Light blue
    8,  # Purple
    5)  # Light Pink
# NOT in this list, but still distinct and available for other uses, are
# #1 (black, used for ground), #11 (dark red, used for power), #6 (dark
# purple, used for control), #2 (dark teal, not currently used, is ugly),
# #7 (medium blue, not currently used and should be avoided if possible as
# it appears similar to #3 for some) and #4 (hot pink, not used and also
# should be avoided as it resembles #13 orange to some.)

# This is a base set of pin themes that are common to ALL chips.
# TO DO: decide on 'Arduino' position in list, and palette index.
themes = [
    {'type':'Power', 'fill':palette[11], 'font-weight':'bold'},
    {'type':'GND', 'fill':palette[1], 'font-weight':'bold'},
    {'type':'Control', 'fill':palette[6], 'font-weight':'bold'},
    {'type':'Arduino', 'fill':'#00FF00', 'font-weight':'bold'},
    {'type':'CircuitPython Name', 'fill':'#E6E6E6', 'outline':'auto', 'font-weight':'bold'},
    {'type':'QT_SCL', 'fill':'#FFFF00', 'font-weight':'bold'},
    {'type':'QT_SDA', 'fill':'#0000FF', 'font-weight':'bold'},
    ]
# TO-DO: These will go away, mux boxes will simply proceed in chroma order!
# Additional themes unique to RP2040 devices
rp2040_themes = [
    {'type':'Port', 'fill':palette[15]},
    {'type':'SPI', 'fill':palette[14]},
    {'type':'UART', 'fill':palette[10]},
    {'type':'I2C', 'fill':palette[8]},
    {'type':'PWM', 'fill':palette[5]},
    {'type':'Analog', 'fill':palette[13]},
    {'type':'ExtInt', 'fill':'#FF00FF'},
    {'type':'PCInt', 'fill':'#FFC000'},
    {'type':'Misc', 'fill':'#A0A0FF'},
    {'type':'Misc2', 'fill':'#C0C0FF'},
    ]
# Additional themes unique to ESP32 devices
esp32_themes = [
    {'type':'Port', 'fill':palette[15]},
    {'type':'Power Domain', 'fill':palette[14]},
    {'type':'Analog', 'fill':palette[3]},
    {'type':'SPI', 'fill':palette[10]},
    {'type':'Touch', 'fill':palette[8]},
    {'type':'UART', 'fill':palette[5]},
    {'type':'I2C', 'fill':palette[13]},
#    {'type':'Other', 'fill':palette[12], 'outline':'auto'},
    ]

# some eagle cad names are not as pretty
conn_renames = [('!RESET', 'RESET'),
                ('D5_5V', 'D5'),
                ('+3V3', '3.3V'),
                ('+5V', '5V')
                ]
product_url = None
product_title = None
chip_description = None

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

    product_url = xmldict['module']['url']
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

def get_circuitpy_aliases(connections, circuitpydef):
    # now check the circuitpython definition file
    pyvar = open(circuitpydef).readlines()
    pypairs = []
    for line in pyvar:
        # find the QSTRs
        matches = re.match(r'.*MP_QSTR_(.*)\)\s*,\s*MP_ROM_PTR\(&pin_(.*)\)', line)
        if not matches:
            continue
        pypairs.append((matches.group(1), matches.group(2)))

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
    global themes, chip_description

    # This is kinda gross and modifies the global 'themes' to append one of
    # the canned theme tables. Just wondering if it would be less gross to
    # put the themes in their own .py files and import or something, I
    # dunno, just getting the basics going right now.
    if pinoutcsv.lower().startswith('rp2040'):
        themes += rp2040_themes
    elif pinoutcsv.lower().startswith('esp32'):
        themes += esp32_themes

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
    print("Mux options available: ", pinmuxes)
    return pinarray


def draw_label(dwg, group, label_text, label_type, box_x, box_y, box_w, box_h):
    theme = next((theme for theme in themes if theme['type'] == label_type), None)
    if 'outline' in theme:
        box_outline = theme['outline']
    else:
        box_outline = 'none'
    box_fill = theme['fill']
    text_color = 'black'
    # Some auto-color things only work if RGB (not named) fill is specified...
    if (box_fill[0] == '#'):
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
    elif (box_fill == 'black'):
        text_color = 'white'

    #box_opacity = theme['opacity'] # Not used, everything's gone opaque
    if 'font-weight' in theme:
        weight = theme['font-weight']
    else:
        weight = 'normal'
    # draw a box
    box_x += BOX_INSET[0]  # Inset a bit so boxes aren't touching
    box_y += BOX_INSET[1]
    box_w -= BOX_INSET[0] * 2
    box_h -= BOX_INSET[1] * 2
    if box_outline != 'none':
        box_x += BOX_STROKE_WIDTH * 0.5 # Inset further for stroke
        box_y += BOX_STROKE_WIDTH * 0.5 # (so box extents visually align)
        box_w -= BOX_STROKE_WIDTH
        box_h -= BOX_STROKE_WIDTH
        group.add(dwg.rect(
            (box_x, box_y),
            (box_w, box_h),
            BOX_CORNER_RADIUS[0], BOX_CORNER_RADIUS[1],
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
        if weight != 'normal':
            group.add(dwg.text(
                label_text,
                insert = (box_x+box_w/2, box_y+box_h/2+LABEL_HEIGHTADJUST),
                font_size = LABEL_FONTSIZE,
                font_family = LABEL_FONT,
                font_weight = weight,
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
    dwg = svgwrite.Drawing(filename=str("pinlabels.svg"), profile='tiny', size=(100,100))

    # collect all muxstrings to calculate label widths:
    muxstringlen = {}
    for i, conn in enumerate(connections):
        if not 'mux' in conn:
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
        box_x = last_used_x = 0
        box_w = max(6, len(conn['name'])+1) * BOX_WIDTH_PER_CHAR
        first_box_w = box_w
        last_used_w = box_w
        if conn['location'] in ('top', 'right', 'unknown'):
            box_x += box_w
        if 'mux' in conn: # power pins don't have muxing, its cool!
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
            g.add(dwg.line(start=(-4, line_y), end=(last_used_x + last_used_w * 0.5, line_y), stroke=ROW_STROKE_COLOR, stroke_width = ROW_STROKE_WIDTH, stroke_linecap='round'));
        if conn['location'] in ('bottom', 'left'):
            g.add(dwg.line(start=(first_box_w + 4, line_y), end=(last_used_x + last_used_w * 0.5, line_y), stroke=ROW_STROKE_COLOR, stroke_width = ROW_STROKE_WIDTH, stroke_linecap='round'));

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
        if name_label in ("3.3V", "VHIGH", "VIN", "5V", "VBAT", "VBUS", "VHI"):
            label_type = 'Power'
        if name_label in ("GND"):
            label_type = 'GND'
        if name_label in ("EN", "RESET", "SWCLK", "SWC", "SWDIO", "SWD"):
            label_type = 'Control'
        if name_label in ('SCL', 'SCL1', 'SCL0') and conn['svgtype'] == 'ellipse':
            # special stemma QT!
            label_type = 'QT_SCL'
        if name_label in ('SDA', 'SDA1', 'SDA0') and conn['svgtype'] == 'ellipse':
            # special stemma QT!
            label_type = 'QT_SDA'

        # Draw the first-column box (could be power pin or Arduino pin #)
        draw_label(dwg, group[group_index], name_label, label_type, box_x, box_y, box_w, box_h)
        # Increment box_x only on 'right' locations, because the behavior
        # for subsequent right boxes is to draw-and-increment, whereas
        # 'left' boxes increment-and-draw.
        if conn['location'] in ('top', 'right', 'unknown'):
            box_x += box_w
        mark_as_in_use(label_type)

        if 'mux' in conn: # power pins don't have muxing, its cool!
            for mux in conn['mux']:
                label = conn['mux'][mux]
                box_w = (muxstringlen[mux]+1) * BOX_WIDTH_PER_CHAR
                if not label:
                    # Increment box_x regardless for sparse tables
                    if conn['location'] in ('top', 'right', 'unknown'):
                        box_x += box_w
                    if conn['location'] in ('bottom', 'left'):
                        box_x -= box_w
                    continue
                if mux == 'GPIO':  # the underlying pin GPIO name
                    label_type = 'Port'
                elif mux in ('SPI', 'HS/QSPI') :  # SPI ports
                    label_type = 'SPI'
                elif mux == 'I2C':  # I2C ports
                    label_type = 'I2C'
                elif mux in ('UART', 'Debug'):  # UART ports
                    label_type = 'UART'
                elif mux == 'PWM':  # PWM's
                    label_type = 'PWM'
                elif mux == 'Touch':  # touch capable
                    label_type = 'Touch'
                elif mux == 'ADC':  # analog ins
                    label_type = 'Analog'
                elif mux == 'Other':
                    label_type = 'I2C'
                elif mux == 'Power Domain':
                    #label_type = 'Power'
                    label_type = 'Power Domain'
                else:
                    continue

                if conn['location'] in ('top', 'right', 'unknown'):
                    # Draw-and-increment
                    draw_label(dwg, group[group_index], label, label_type, box_x, box_y, box_w, box_h)
                    box_x += box_w
                if conn['location'] in ('bottom', 'left'):
                    # Increment-and-draw
                    box_x -= box_w
                    draw_label(dwg, group[group_index], label, label_type, box_x, box_y, box_w, box_h)

                mark_as_in_use(label_type) # Show label type on legend
        else:
            # For power pins with no mux, keep legend up to date
            # and don't 'continue,' so group_index keeps in sync.
            mark_as_in_use(label_type)

        dwg.add(group[group_index])
        group_index += 1 # Increment on non-None connections

    # Add legend
    g = dwg.g()
    box_y = BOX_HEIGHT * (i + 4)
    for theme in themes:
        # Skip themes not in use, and the STEMMA QT connector
        if 'in_use' in theme and not theme['type'].startswith('QT_'):
            label_type = theme['type']
            draw_label(dwg, g, None, label_type, 0, box_y, BOX_HEIGHT, BOX_HEIGHT)
            label_text = label_type
            g.add(dwg.text(
                label_text,
                insert = (BOX_HEIGHT * 1.2, box_y+box_h/2+LABEL_HEIGHTADJUST),
                font_size = LABEL_FONTSIZE,
                font_family = LABEL_FONT,
                font_weight = 'bold',
                fill = 'black',
                text_anchor = 'start'
                ))
            box_y += BOX_HEIGHT
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
        text_anchor = 'end'
        ))
    g.add(dwg.text(
        product_url,
        insert = (0, -25),
        font_size = URL_FONTSIZE,
        font_family = LABEL_FONT,
        font_weight = 'bold',
        fill = 'black',
        text_anchor = 'end'
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


# Add an 'in_use' key to themes that get referenced.
# Only these items are shown on the legend.
def mark_as_in_use(label_type):
    for theme in themes:
        if theme['type'] == label_type and not 'in_use' in theme:
            theme['in_use'] = '1'


@click.command()
@click.argument('FZPZ')
@click.argument('circuitpydef')
@click.argument('pinoutcsv')
@click.option('-s', '--substitute', 'substitute', nargs=2)
def parse(fzpz, circuitpydef, pinoutcsv, substitute):
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

    # find the 'true' GPIO pine via the circuitpython file
    connections = get_circuitpy_aliases(connections, circuitpydef)

    # open and parse the pinout mapper CSV
    pinarray = get_chip_pinout(connections, pinoutcsv)

    # get SVG width and height
    bb_sg = sg.fromfile(svgfilename)
    bb_root = bb_sg.getroot()
    svg_width = bb_sg.width
    svg_height = bb_sg.height
    if "in" in svg_width:
        svg_width = 25.4 * float(svg_width[:-2]) * MM_TO_PX
    else:
        raise RuntimeError("Dont know units of width!", svg_width)
    if "in" in svg_height:
        svg_height = 25.4 * float(svg_height[:-2]) * MM_TO_PX
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
        conn['mux'] = muxes
    draw_pinlabels_svg(connections)
    
    newsvg.save("output.svg")




if __name__ == '__main__':
    parse()
