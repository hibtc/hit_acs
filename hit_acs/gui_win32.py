"""
Loads BeamOptikDLL in a python process and waits in a simple win32 message
loop. This module does not provide any custom/interactive GUI apart from the
GUI provided by BeamOptikDLL itself.
"""

from __future__ import absolute_import

import logging
import win32gui

from .beamoptikdll import BeamOptikDLL


def main():
    """Invoke GUI application."""
    logging.basicConfig(level=logging.INFO)
    dll = BeamOptikDLL()
    dll.GetInterfaceInstance()
    win32gui.PumpMessages()


if __name__ == '__main__':
    main()
