"""
Start an interactive testing console for the BeamOptikDLL wrapper.

Note that this cannot equivalently be done without the GUI: The
'BeamOptikDLL.dll' library creates an application window and therefore
requires a main loop to process window messages. This module uses wxPython_
to create the main loop and PyCrust_ to provide an interactive python
console.

.. _wxPython: http://wxpython.org/
.. _PyCrust: http://wxpython.org/py.php

The DLL is connected on startup and the wrapper object is stored in the
global variable ``dll``.
"""

from __future__ import absolute_import

import wx
import wx.py.crust
import logging

from .beamoptikdll import BeamOptikDLL


class App(wx.App):

    def OnInit(self):
        loc = {}
        frame = wx.py.crust.CrustFrame(locals=loc)
        frame.Show()
        frame.crust.shell.redirectStdout()
        frame.crust.shell.redirectStderr()
        logging.basicConfig(level=logging.INFO)
        loc['frame'] = frame
        loc['dll'] = BeamOptikDLL()
        loc['dll'].GetInterfaceInstance()
        return True


def main():
    """Invoke GUI application."""
    app = App(redirect=False)
    app.MainLoop()


if __name__ == '__main__':
    main()
