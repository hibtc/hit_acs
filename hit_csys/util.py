"""
Utilities for unicode IO.
"""

import csv
import sys

from pkg_resources import resource_string

import yaml


__all__ = [
    'csv_unicode_reader',
    'yaml_load_unicode',
    'load_yaml_resource',
]


if sys.version_info[0] < 3:
    def csv_unicode_reader(lines, encoding='utf-8', **kwargs):
        """Load unicode CSV file."""
        return [[r.decode(encoding) for r in row]
                for row in csv.reader(stream, **kwargs)]

else:
    def csv_unicode_reader(lines, encoding='utf-8', **kwargs):
        """Load unicode CSV file."""
        lines = [l.decode(encoding) for l in lines]
        return csv.reader(lines, **kwargs)


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


def load_yaml_resource(package, filename):
    """Return the builtin configuration."""
    return yaml.safe_load(resource_string(package, filename))
