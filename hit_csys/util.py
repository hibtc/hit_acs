"""
Utilities for unicode IO.
"""

import csv
import sys


__all__ = [
    'csv_unicode_reader',
]


if sys.version_info[0] < 3:
    def csv_unicode_reader(lines, encoding='utf-8', **kwargs):
        """Load unicode CSV file."""
        return [[r.decode(encoding) for r in row]
                for row in csv.reader(lines, **kwargs)]

else:
    def csv_unicode_reader(lines, encoding='utf-8', **kwargs):
        """Load unicode CSV file."""
        lines = [l.decode(encoding) for l in lines]
        return csv.reader(lines, **kwargs)
