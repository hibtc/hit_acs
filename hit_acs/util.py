"""
Utilities for unicode IO.
"""

import csv
import sys
import time


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


class TimeoutCache(object):

    """
    Cache that cycles every ``timeout`` seconds.

    The invalidation interval is global, not per-entry.

    ``timeout=0`` means no caching,
    ``timeout=-1`` means infinite caching.
    """

    def __init__(self, get, timeout=1.0):
        self._get = get
        self._beg = time.time()
        self.timeout = timeout
        self.values = {}

    def __getitem__(self, name):
        now = time.time()
        beg = self._beg
        timeout = self.timeout
        values = self.values
        if now - beg > timeout > 0:
            self._beg = now - (now - beg) % timeout
            values.clear()
        if name not in values or timeout == 0:
            values[name] = self._get(name)
        return values[name]
