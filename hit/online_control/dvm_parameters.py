# encoding: utf-8
"""
Tools to work with DVM paramater list.
"""

from __future__ import absolute_import

from collections import namedtuple

import yaml

from madgui.util import unit
from .util import csv_unicode_reader, yaml_load_unicode


DVM_Parameter = namedtuple('DVM_Parameter', [
    'name',
    'ui_name',
    'ui_hint',
    'read',
    'write',
    'unit',
    'ui_unit',
])


#----------------------------------------
# CSV column types
#----------------------------------------

def CsvStr(s):
    return s


def CsvBool(s):
    return s == 'ja' if s else None


def CsvFloat(s):
    return float(s) if s else None


def CsvUnit(s):
    if s == '%':
        return 0.01
    s = s.replace(u'grad', u'degree')
    s = s.replace(u'Ohm', u'ohm')
    s = s.replace(u'part.', u'count')   # used for particle count
    return unit.from_config(s)



class DVM_ParameterList(object):

    def __init__(self, data):
        self._data = data

    @classmethod
    def from_csv(cls, filename, encoding='utf-8', delimiter=';'):
        """
        Parse DVM parameters from CSV file exported from XLS documentation
        spreadsheet (e.g. DVM-Parameter_v2.10.0-10-HIT.xls)
        """
        csv_data = csv_unicode_reader(filename,
                                      encoding=encoding,
                                      delimiter=delimiter)
        return cls.from_csv_data(csv_data)

    @classmethod
    def from_csv_data(cls, rows):
        return cls(dict(cls._parse_csv_data(rows)))

    @classmethod
    def _parse_csv_data(cls, rows):
        types = cls._csv_column_types
        index = cls._csv_column_index
        parse_row = lambda row: DVM_Parameter(**{
            n: types[n](row[i].strip())
            for n, i in index.items()
        })
        cluster_name = ''
        cluster_items = []
        for row in rows:
            item = parse_row(row)
            # detect cluster header lines:
            link = row[0]
            if (link and not link.isdigit()
                    and item.read is None
                    and item.write is None):
                # yield previous element/context
                if cluster_items:
                    yield (cluster_name, cluster_items)
                cluster_name = link
                cluster_items = []
            elif item.read or item.write:
                cluster_items.append(item)
        if cluster_items:
            yield (cluster_name, cluster_items)

    # all columns in csv file:
    _csv_column_names = [
        '',                 # Nr. für Link
        'name',             # Code Param (GSI-Nomenklatur)
        '',                 # Code Gerät (GSI- NomenkLatur) entspr. DCU!
        '',                 # Code Gruppe (=Kalkulationsgruppe); möglichst GSI-NomenkLatur
        'ui_name',          # GUI Beschriftung Parameter (ohne Einheit)
        'ui_hint',          # GUI Beschriftung Hint
        '',                 # Position ExpertGrids
        'read',             # DVM liest Parameter
        'write',            # DVM ändert Parameter
        '',                 # DVM Datensatz spezifisch
        '',                 # Rein temporär
        '',                 # MEFI-Abhängigkeit
        '',                 # Input Param wird Output Param bei MEFI
        '',                 # In Gui Init änderbar
        '',                 # Daten-typ
        '',                 # Präzision (Anz. Nachkomma im GUI)
        'unit',             # Einheit Parameter
        'ui_unit',          # Einheit Anzeige im GUI
        '',                 # Umrechnungsfaktor Einheit--> Einheit GUI
        '',                 # Beispielwert für Test in Einheit GUI
        '',                 # Referenz auf DCU /MDE
        '',                 # (nicht verwendet)
        '',                 # Zugriffscode / editierbarkeit
        '',                 # Versions-  Relevanz
        '',                 # Detail Ansicht verfügbar (ja/nein)
        '',                 # Link auf Maximalwert
        '',                 # Link auf Minimalwert
        '',                 # Code Min/Max- Rechen-vorschrift
        '',                 # Master-gruppe
        '',                 # Defaultwert Änderung pro Pfeiltasten-druck/Maus-radsegment in Einheit GUI
        '',                 # Im laufenden Betrieb änderbar (ja/ nein)
        '',                 # Link auf zugehörigen sekundären Wert
    ]

    _csv_column_types = {
        'name': CsvStr,
        'ui_name': CsvStr,
        'ui_hint': CsvStr,
        'read': CsvBool,
        'write': CsvBool,
        'unit': CsvUnit,
        'ui_unit': CsvUnit,
    }

    # inverse map of _csv_columns[i] (used columns)
    _csv_column_index = {
        name: index
        for index, name in enumerate(_csv_column_names)
        if name
    }

    @classmethod
    def from_yaml(cls, filename, encoding='utf-8'):
        with open(filename, 'rb') as f:
            data = yaml_load_unicode(f, yaml.SafeLoader)
        return cls.from_yaml_data(data)

    @classmethod
    def from_yaml_data(cls, raw_data):
        data = {
            name: [DVM_Parameter(*item) for item in items]
            for name, items in raw_data
        }
        return cls(data)

    def to_yaml(self, filename=None, encoding='utf-8'):
        data = {
            name: [tuple(item) for item in items]
            for name, items in self._data.items()
        }
        text = yaml.safe_dump(data, encoding=encoding, allow_unicode=True)
        if filename:
            with open('foo.yml', 'wb') as f:
                f.write(text)
        else:
            return text
