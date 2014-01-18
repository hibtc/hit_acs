"""
Start an interactive testing console for the BeamOptikDLL wrapper.

Note that this cannot equivalently be done without the GUI: The
'BeamOptikDLL.dll' library creates an application window and therefore
requires a main loop to process window messages. This module uses wxPython_
to create the main loop and PyCrust_ to provide an interactive python
console.

.. _wxPython: http://wxpython.org/
.. _PyCrust: http://wxpython.org/py.php

"""
import wx
import wx.py.crust

from hit.online_control.beamoptikdll import BeamOptikDLL as dll, EFI, DVMStatus, GetOptions, ExecOptions, GetSDOptions

class App(wx.App):
    def OnInit(self):
        frame = wx.py.crust.CrustFrame()
        frame.Show()
        global i
        i = dll.GetInterfaceInstance()
        return True

def main():
    """Invoke GUI application."""
    # TODO: add command line options (via docopt!)
    app = App(redirect=True, filename='error.log')
    app.MainLoop()

if __name__ == '__main__':
    main()

