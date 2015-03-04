# encoding: utf-8
"""
Tools to work with DVM paramater list.
"""

from __future__ import absolute_import

import csv
import sys
from collections import namedtuple

import yaml


DVM_Parameter = namedtuple('DVM_Parameter', [
    'name',
    'ui_name',
    'ui_hint',
    'read',
    'write',
    'unit',
    'ui_unit',
])


if sys.version_info[0] < 3:
    def csv_unicode_reader(filename, encoding='utf-8', **kwargs):
        """Load unicode CSV file."""
        with open(filename, 'rb') as f:
            csv_data = f
            for row in csv.reader(csv_data, **kwargs):
                yield [e.decode(encoding) for e in row]

else:
    def csv_unicode_reader(filename, encoding='utf-8', **kwargs):
        """Load unicode CSV file."""
        with open(filename, 'rt', encoding=encoding) as f:
            return csv.reader(list(f), **kwargs)


def yaml_load_unicode(stream, Loader=yaml.SafeLoader):
    """Load YAML with all strings loaded as unicode objects."""
    class UnicodeLoader(Loader):
        pass
    def construct_yaml_str(self, node):
        # Override the default string handling function
        # to always return unicode objects
        return self.construct_scalar(node)
    UnicodeLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG,
        construct_yaml_str)
    return yaml.load(stream, UnicodeLoader)


#----------------------------------------
# CSV column types
#----------------------------------------

def CsvStr(s):
    return s.strip()


def CsvBool(s):
    return s.strip() == 'ja' if s else None


def CsvFloat(s):
    return float(s.strip())


def CsvUnit(s):
    # TODO: parse unit?!
    return s.strip()



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
            n: types[n](row[i])
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
