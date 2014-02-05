#!/usr/bin/env python
# encoding: utf-8
from setuptools import setup

setup(
    name='hit_online_control',
    version='0.0',
    description='Online control for the HIT accelerator facility',
    long_description=open('README.rst').read(),
    author='Thomas Gläßle',
    author_email='t_glaessle@gmx.de',
    maintainer='Thomas Gläßle',
    maintainer_email='t_glaessle@gmx.de',
    url='https://bitbucket.org/coldfix/hit-online-control',
    packages=['hit', 'hit.online_control'],
    namespace_packages=['hit'],
    entry_points={
        'gui_scripts': ['online_control = hit.online_control.__main__:main'],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Healthcare Industry',
        'Intended Audience :: Science/Research',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: Medical Science Apps.',
        'Topic :: Scientific/Engineering :: Physics' ],
    license=None,
)
