# encoding: utf-8
"""
Tools to work with DVM paramater list.
"""

from hit_acs.util import csv_unicode_reader


# CSV column types

def CsvStr(s):
    return s


def CsvInt(s):
    return int(s) if s else None


def CsvFloat(s):
    return float(s) if s else None


def CsvUnit(s):
    s = s.replace(u'grad', u'degree')
    s = s.replace(u'Ohm', u'ohm')
    s = s.replace(u'part.', u'count')   # used for particle count
    return s


def load_csv(lines, encoding='utf-8', delimiter=';'):
    """
    Parse DVM parameters from CSV file exported from XLS documentation
    spreadsheet (e.g. DVM-Parameter_v2.10.0-10-HIT.xls)
    """
    return load_csv_data(csv_unicode_reader(
        lines, encoding=encoding, delimiter=delimiter))


def load_csv_data(rows):
    def parse_row(row):
        return {
            n: _csv_column_types[n](row[i].strip())
            for n, i in _csv_column_index.items()
        }
    return map(parse_row, rows)


# all columns in csv file:
_csv_column_names = [
    '',                 # Nr. für Link
    'name',             # Code Param (GSI-Nomenklatur)
    '',                 # Code Gerät (GSI- NomenkLatur) entspr. DCU!
    '',                 # Code Gruppe (=Kalkulationsgruppe); möglichst
                        #       GSI-NomenkLatur
    'ui_name',          # GUI Beschriftung Parameter (ohne Einheit)
    'ui_hint',          # GUI Beschriftung Hint
    '',                 # Position ExpertGrids
    '',                 # DVM liest Parameter
    '',                 # DVM ändert Parameter
    '',                 # DVM Datensatz spezifisch
    '',                 # Rein temporär
    '',                 # MEFI-Abhängigkeit
    '',                 # Input Param wird Output Param bei MEFI
    '',                 # In Gui Init änderbar
    '',                 # Daten-typ
    'ui_prec',          # Präzision (Anz. Nachkomma im GUI)
    'unit',             # Einheit Parameter
    'ui_unit',          # Einheit Anzeige im GUI
    'ui_conv',          # Umrechnungsfaktor Einheit--> Einheit GUI
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
    '',                 # Defaultwert Änderung pro Pfeiltasten-druck/
                        #       Maus-radsegment in Einheit GUI
    '',                 # Im laufenden Betrieb änderbar (ja/ nein)
    '',                 # Link auf zugehörigen sekundären Wert
]

_csv_column_types = {
    'name':     CsvStr,
    'ui_name':  CsvStr,
    'ui_hint':  CsvStr,
    'ui_prec':  CsvInt,
    'unit':     CsvUnit,
    'ui_unit':  CsvUnit,
    'ui_conv':  CsvFloat,
}

# inverse map of _csv_columns[i] (used columns)
_csv_column_index = {
    name: index
    for index, name in enumerate(_csv_column_names)
    if name
}
