# encoding: utf-8
from setuptools import setup
from distutils.util import convert_path


def read_file(path):
    """Read a file in binary mode."""
    with open(convert_path(path), 'rb') as f:
        return f.read()


def exec_file(path):
    """Execute a python file and return the `globals` dictionary."""
    namespace = {}
    exec(read_file(path), namespace, namespace)
    return namespace


def main():
    """Execute setup."""
    long_description = read_file('README.rst').decode('utf-8')
    meta = exec_file('hit/online_control/__init__.py')
    setup(
        name='hit_online_control',
        version=meta['__version__'],
        description=meta['__summary__'],
        long_description=long_description,
        author=meta['__author__'],
        author_email=meta['__email__'],
        url=meta['__uri__'],
        license=meta['__license__'],
        classifiers=meta['__classifiers__'],
        packages=[
            'hit',
            'hit.online_control'
        ],
        namespace_packages=['hit'],
        entry_points={
            'gui_scripts': [
                'online_control = hit.online_control.__main__:main'
            ],
            'madgui.widget.notebook.menu': [
                'online_control = hit.online_control.madgui:Plugin'
            ]
        },
    )


if __name__ == '__main__':
    main()
