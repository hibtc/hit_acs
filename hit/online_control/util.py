"""
Utilities for unicode IO.
"""

import csv
import sys

import yaml


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

