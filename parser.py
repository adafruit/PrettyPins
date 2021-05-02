#!/usr/bin/python3

import click
import xml.etree.ElementTree as ET
from xml.dom import minidom
import xmltodict
import svgutils.transform as sg
import sys 
import re

MM_TO_PX = 96 / 25.4
PX_TO_MM = 25.4 / 96
FONT_HEIGHT_PX = 10.5
FONT_CHAR_W = 4

@click.argument('circuitpydef')
@click.argument('SVG')
@click.argument('FZP')


@click.command()
def parse(fzp, svg, circuitpydef):
    click.echo("HI! THIS IS A MISTAKE!")


    connections = []
    f = open(fzp)
    xmldict = xmltodict.parse(f.read())
    for c in xmldict['module']['connectors']['connector']:
        c_name = c['@name']
        c_svg = c['views']['breadboardView']['p']['@svgId']
        d = {'name': c_name, 'svgid': c_svg}
        connections.append(d)
    print(connections)

    # open and paste the SVG into a new file
    bb_sg = sg.fromfile(svg)
    bb_root = bb_sg.getroot()
    w = bb_sg.width
    h = bb_sg.height
    if "in" in w:
        w = 25.4 * float(w[:-2])
    else:
        raise RuntimeError("Dont know units of width!", w)
    if "in" in h:
        h = 25.4 * float(h[:-2])
    else:
        raise RuntimeError("Dont know units of width!", h)
    print("Width, Height in mm: ", w, h)

    newsvg = sg.SVGFigure()
    newsvg.set_size(("%dpx" % (w * MM_TO_PX), "%dpx" % (h * MM_TO_PX)))    
    print(newsvg.get_size())

    #bb_root.rotate(90)
    #bb_root.moveto(h * MM_TO_PX, 0, 1.33)
    newsvg.append(bb_root)
    newsvg.save("rotated.svg")

    # ok now we can open said new file as an xml
    xmldoc = minidom.parse("rotated.svg")

    # Find all circle/pads
    circlelist = xmldoc.getElementsByTagName('circle')
    for c in circlelist:
        try:
            idval = c.attributes['id'].value
            cx = c.attributes['cx'].value
            cy = c.attributes['cy'].value
            for d in connections:
                if d['svgid'] == c.attributes['id'].value:
                    d['cx'] = float(cx)
                    d['cy'] = float(cy)
        except KeyError:
            pass

    # sometimes pads are ellipses, note they're often transformed!
    ellipselist = xmldoc.getElementsByTagName('ellipse')
    for c in ellipselist:
        try:
            idval = c.attributes['id'].value
            cx = c.attributes['cx'].value
            cy = c.attributes['cy'].value
            for d in connections:
                if d['svgid'] == c.attributes['id'].value:
                    d['cx'] = float(cx)
                    d['cy'] = float(cy)
        except KeyError:
            pass

    # now check the circuitpython definition file
    pyvar = open(circuitpydef).readlines()
    for line in pyvar:
        #print(line)
        matches = re.match(r'.*MP_ROM_QSTR\(MP_QSTR_(.*)\),\s+MP_ROM_PTR\(&pin_(.*)\)', line)
        if not matches:
            continue
        #print(matches.group(1), matches.group(2))
        for d in connections:
            if d['name'] == matches.group(1):
                if not 'aliases' in d:
                    d['aliases'] = []
                d['aliases'].append(matches.group(2))
                
    # add text labels!
    for c in connections:
        print(c)
        is_top = c['cy'] < h/2

        label =  c['name']
        if 'aliases' in c:
            for a in c['aliases']:
                if is_top:
                    label += "/" + a
                else:
                    label = a + "/" + label
        txt = sg.TextElement(0, 0, label, font="Courier New", weight="bold", color='red', size=6)
        txt.rotate(270)
        if is_top:
            txt.moveto(c['cx'] + FONT_HEIGHT_PX/5, c['cy']-FONT_CHAR_W)
        else:
            txt.moveto(c['cx'] + FONT_HEIGHT_PX/5, c['cy']+(FONT_CHAR_W*len(label)))
        newsvg.append(txt)
                
    newsvg.save("rotated.svg")

if __name__ == '__main__':
    parse()
