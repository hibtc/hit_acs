"""
Utilities for reading .xml file with MWPC offsets.
"""

import os
from glob import glob
from xml.etree import ElementTree

from madgui.util.unit import from_ui, from_config


PREFIX_ROOM = {'Room1': 'T1', 'Room2': 'T2', 'Room3': 'T3', 'Room4': 'T4'}
SUFFIX_MWPC = {'MWPC 1': 'DG1G', 'MWPC 2': 'DG2G', 'MWPC 3': 'DF1'}


def parse_datum(name, datum):
    value = float(datum.text)
    unit = from_config(datum.attrib['Unit'])
    return from_ui(name, unit, value)


def read_offsets_file(path):
    tree = ElementTree.parse(path)
    root = tree.getroot()

    abstract, calibration = root.iter('Table')
    metadata = {datum.attrib['ID']: datum.text
                for datum in abstract.iter('Data')}

    # Columns are:
    # - 0 = device name
    # - 1 = old X offset
    # - 2 = new X offset
    # - 3 = old Y offset
    # - 4 = new Y offset
    offsets = {
        row[0].text: (
            parse_datum('x', row[2][0]),
            parse_datum('y', row[4][0]))
        for row in calibration[1:]
    }

    room = metadata['TreatmentRoom']
    prefix = PREFIX_ROOM[room]
    return {prefix+SUFFIX_MWPC[mwpc]: xy
            for mwpc, xy in offsets.items()}


def find_offsets(path):
    """Find and read .xml files MWPC offsets in `path`."""
    offsets = {}
    for path in glob(os.path.join(path, '*', '*.xml')):
        try:
            offsets.update(read_offsets_file(path))
        except Exception:
            pass
    return offsets


def print_offsets(path):
    print(path+':')
    for mwpc, (x, y) in read_offsets_file(path).items():
        print("  {:6}: {:+.3f} mm, {:+.3f} mm".format(mwpc, x*1000, y*1000))


if __name__ == '__main__':
    import sys
    for path in sys.argv[1:]:
        print_offsets(path)
