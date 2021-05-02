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

MM_TO_PX = 96 / 25.4
PX_TO_MM = 25.4 / 96
FONT_HEIGHT_PX = 10.5
FONT_CHAR_W = 4



# This function digs through the FZP (XML) file and the SVG (also, ironically, XML) to find what
# frtizing calls a connection - these are pads that folks can connect to! they are 'named' by
# eaglecad, so we should use good names for eaglecad nets that will synch with circuitpython names
def get_connections(fzp, svg):
    connections = []

    # check the FPZ for every 'connector' type element
    f = open(fzp)
    xmldict = xmltodict.parse(f.read())
    for c in xmldict['module']['connectors']['connector']:
        c_name = c['@name']     # get the pad name
        c_svg = c['views']['breadboardView']['p']['@svgId']   # and the SVG ID for the pad
        d = {'name': c_name, 'svgid': c_svg}
        connections.append(d)
    #print(connections)

    # ok now we can open said matching svg xml
    xmldoc = minidom.parse(svg)

    # Find all circle/pads
    circlelist = xmldoc.getElementsByTagName('circle')
    # sometimes pads are ellipses, note they're often transformed!
    ellipselist = xmldoc.getElementsByTagName('ellipse')
    for c in circlelist+ellipselist:
        try:
            idval = c.attributes['id'].value   # find the svg id
            cx = c.attributes['cx'].value      # x location
            cy = c.attributes['cy'].value      # y location
            d = next((conn for conn in connections if conn['svgid'] == c.attributes['id'].value), None)
            if d:
                d['cx'] = float(cx)
                d['cy'] = float(cy)
        except KeyError:
            pass
    return connections

def get_circuitpy_aliases(connections, circuitpydef):
    # now check the circuitpython definition file
    pyvar = open(circuitpydef).readlines()
    for line in pyvar:
        #print(line)
        # find the QSTRs
        matches = re.match(r'.*MP_ROM_QSTR\(MP_QSTR_(.*)\),\s+MP_ROM_PTR\(&pin_(.*)\)', line)
        if not matches:
            continue
        #print(matches.group(1), matches.group(2))
        
        for d in connections:
            if d['name'] == matches.group(1):
                if not 'aliases' in d:
                    d['aliases'] = []
                d['aliases'].append(matches.group(2))
    return connections

def get_chip_pinout(connections, pinoutcsv):
    with open(pinoutcsv, mode='r') as infile:
        pinarray = []
        reader = csv.reader(infile)
        csvlist = [row for row in reader]
        header = csvlist.pop(0)
        for pin in csvlist:
            gpioname = pin[0]
            d = {}
            for i,mux in enumerate(pin):
                d[header[i]] = mux
            pinarray.append(d)
        pinmuxes = header
    print("Mux options available: ", pinmuxes)
    return pinarray

BOX_HEIGHT = 10
BOX_WIDTH_PER_CHAR = 5
LABEL_FONT = "Courier New"
LABEL_FONTSIZE = 8
LABEL_HEIGHTADJUST = 2     # move text down (negative for up)

themes = [
    {'type':'Name', 'fill':'white', 'outline':'black', 'opacity':0.3, 'font-weight':'bold'},
    {'type':'Power', 'fill':'red', 'outline':'black', 'opacity':0.8, 'font-weight':'bold'},
    {'type':'GND', 'fill':'black', 'outline':'black', 'opacity':0.9, 'font-weight':'bold'},
    {'type':'Control', 'fill':'gray', 'outline':'black', 'opacity':0.7, 'font-weight':'bold'},
    {'type':'Arduino', 'fill':'green', 'outline':'black', 'opacity':0.3, 'font-weight':'normal'},
    {'type':'Port', 'fill':'yellow', 'outline':'black', 'opacity':0.4, 'font-weight':'normal'},
    {'type':'Analog', 'fill':'orange', 'outline':'black', 'opacity':0.4, 'font-weight':'normal'},
    {'type':'PWM', 'fill':'green', 'outline':'black', 'opacity':0.3, 'font-weight':'normal'},
    {'type':'UART', 'fill':'pink', 'outline':'black', 'opacity':0.3, 'font-weight':'normal'},
    {'type':'SPI', 'fill':'blue', 'outline':'black', 'opacity':0.3, 'font-weight':'normal'},
    {'type':'I2C', 'fill':'purple', 'outline':'black', 'opacity':0.3, 'font-weight':'normal'},
    {'type':'ExtInt', 'fill':'purple', 'outline':'black', 'opacity':0.2, 'font-weight':'normal'},
    {'type':'PCInt', 'fill':'orange', 'outline':'black', 'opacity':0.5, 'font-weight':'normal'},
    {'type':'Misc', 'fill':'blue', 'outline':'black', 'opacity':0.1, 'font-weight':'normal'},
    {'type':'Misc2', 'fill':'blue', 'outline':'black', 'opacity':0.1, 'font-weight':'normal'},
    ]

def draw_label(dwg, label_text, label_type, box_x, box_y, box_w, box_h):
    theme = next((theme for theme in themes if theme['type'] == label_type), None)
    box_outline = theme['outline']
    box_fill = theme['fill']
    text_color = 'black'
    if (box_fill == 'black'):
        text_color = 'white'
    box_opacity = theme['opacity']
    weight = theme['font-weight']
    # draw a box
    dwg.add(dwg.rect(
        (box_x, box_y),
        (box_w, box_h),
        1, 1,
        stroke = box_outline,
        opacity = box_opacity,
        fill = box_fill
        ))
    dwg.add(dwg.text(
        label_text,
        insert = (box_x+box_w/2, box_y+box_h/2+LABEL_HEIGHTADJUST),
        font_size = LABEL_FONTSIZE,
        font_family = LABEL_FONT,
        font_weight = weight,
        fill = text_color,
        text_anchor = "middle",
        ))

    
def draw_pinlabels_svg(connections):
    dwg = svgwrite.Drawing(filename=str("pinlabels.svg"), profile='tiny', size=(100,100))

    # collect all muxstrings to calculatete label widths:
    muxstringlen = {}
    for i, conn in enumerate(connections):
        if not 'mux' in conn:
            continue
        for mux in conn['mux']:
            if not mux in muxstringlen:
                muxstringlen[mux] = 0
            muxstringlen[mux] = max(muxstringlen[mux], len(conn['mux'][mux]))
    #print(muxstringlen)

    #print(connections)
    # pick out each connection
    for i, conn in enumerate(connections):
        #print(conn)

        # start with the pad name
        box_x = 0
        box_y = BOX_HEIGHT * i
        box_w = BOX_WIDTH_PER_CHAR * 5
        box_h = BOX_HEIGHT

        name_label = conn['name']

        # clean up some names!
        # remove ! starter chars
        name_label = name_label.replace('!', '')
        # some eagle cad names are not as pretty
        if name_label == '+3V3':
            name_label = "3.3V"
            
        label_type = 'Name'
        if name_label in ("3.3V", "VBAT", "VBUS"):
            label_type = 'Power'
        if name_label in ("GND"):
            label_type = 'GND'
        if name_label in ("EN", "RESET"):
            label_type = 'Control'
            
        draw_label(dwg, name_label, label_type, box_x, box_y, box_w, box_h)
        box_x += box_w

        # power pins don't have muxing, its cool!
        if not 'mux' in conn:
            continue
        for mux in conn['mux']:
            label = conn['mux'][mux]
            if not label:
                continue
            if mux == 'GPIO':  # the underlying pin GPIO name
                label_type = 'Port'
            elif mux == 'SPI':  # SPI ports
                label_type = 'SPI'
            elif mux == 'I2C':  # I2C ports
                label_type = 'I2C'
            elif mux == 'UART':  # UART ports
                label_type = 'UART'
            elif mux == 'PWM':  # PWM's
                label_type = 'PWM'
            elif mux == 'ADC':  # analog ins
                label_type = 'Analog'
            else:
                continue
            box_w = (muxstringlen[mux]+1) * BOX_WIDTH_PER_CHAR
            draw_label(dwg, label, label_type, box_x, box_y, box_w, box_h)
            box_x += box_w


    dwg.save()




@click.argument('pinoutcsv')
@click.argument('circuitpydef')
@click.argument('SVG')
@click.argument('FZP')
@click.command()
def parse(fzp, svg, circuitpydef, pinoutcsv):
    click.echo("HI! THIS IS A MISTAKE!")

    # get the connections dictionary
    connections = get_connections(fzp, svg)

    # find the 'true' GPIO pine via the circuitpython file
    connections = get_circuitpy_aliases(connections, circuitpydef)

    # open and parse the pinout mapper CSV
    pinarray = get_chip_pinout(connections, pinoutcsv)
    #print(pinarray)

    # get SVG width and height
    bb_sg = sg.fromfile(svg)
    bb_root = bb_sg.getroot()
    svg_width = bb_sg.width
    svg_height = bb_sg.height
    if "in" in svg_width:
        svg_width = 25.4 * float(svg_width[:-2])
    else:
        raise RuntimeError("Dont know units of width!", svg_width)
    if "in" in svg_height:
        svg_height = 25.4 * float(svg_height[:-2])
    else:
        raise RuntimeError("Dont know units of width!", svg_height)
    #print("Width, Height in mm: ", svg_width, svg_height)
    
    # Create a new SVG as a copy!
    newsvg = sg.SVGFigure()
    newsvg.set_size(("%dpx" % (svg_width * MM_TO_PX), "%dpx" % (svg_height * MM_TO_PX)))    
    #print(newsvg.get_size())
    #bb_root.rotate(90)
    #bb_root.moveto(0, 0, 1.33)
    newsvg.append(bb_root)
    newsvg.save("output.svg")

    # add muxes to connections
    for conn in connections:
        if not 'aliases' in conn:
            continue

        for alias in conn['aliases']:
            # find muxes next
            muxes = next((pin for pin in pinarray if pin['GPIO'] == alias), None)
            conn['mux'] = muxes
            
    draw_pinlabels_svg(connections)

    # create text labels!
    for c in connections:
        #print(c)
        is_top = c['cy'] < svg_height/4

        pinname = c['name']

        label = pinname
        if 'aliases' in c:
            for a in c['aliases']:
                if is_top:
                    label += "/" + a
                else:
                    label = a + "/" + label
                # find muxes next
                muxes = next((pin for pin in pinarray if pin['GPIO'] == a), None)
                if not muxes:
                    continue
                for mux in muxes:
                    if mux == 'GPIO' or not muxes[mux]:
                        continue
                    if is_top:
                        label += "/" + muxes[mux]
                    else:
                        label = muxes[mux] + "/" + label
        #print(label)
        txt = sg.TextElement(0, 0, label, font="Courier New", weight="bold", color='red', size=6)
        txt.rotate(270)
        if is_top:
            txt.moveto(c['cx'] + FONT_HEIGHT_PX/5, c['cy']-FONT_CHAR_W)
        else:
            txt.moveto(c['cx'] + FONT_HEIGHT_PX/5, c['cy']+(FONT_CHAR_W*len(label)))
        newsvg.append(txt)

    newsvg.save("output.svg")




if __name__ == '__main__':
    parse()
