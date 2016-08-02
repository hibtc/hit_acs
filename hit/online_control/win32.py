"""
Loads BeamOptikDLL in a python process and waits in a simple win32 message
loop. This module does not provide any custom/interactive GUI apart from the 
GUI provided by BeamOptikDLL itself.
"""

import logging
import platform
import win32gui

from hit.online_control.beamoptikdll import BeamOptikDLL


def main():
    """Invoke GUI application."""
    logging.basicConfig(level=logging.INFO)
    dll = BeamOptikDLL.load_library()
    dll.GetInterfaceInstance()
    win32gui.PumpMessages()


if __name__ == '__main__':
    main()
