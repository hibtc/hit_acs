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
global variable ``i``.

"""
import wx
import wx.py.crust

from hit.online_control.beamoptikdll import BeamOptikDLL

class App(wx.App):
    def OnInit(self):
        frame = wx.py.crust.CrustFrame()
        frame.Show()
        global i
        i = BeamOptikDLL.GetInterfaceInstance()
        return True

def main():
    """Invoke GUI application."""
    app = App(redirect=True, filename='error.log')
    app.MainLoop()

if __name__ == '__main__':
    main()

