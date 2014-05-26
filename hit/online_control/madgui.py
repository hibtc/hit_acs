"""
Plugin that integrates a beamoptikdll UI into MadGUI.
"""

from __future__ import absolute_import

import re

from cern.cpymad.types import Expression

from madgui.core import wx

# TODO: make GetFloatValueSD useful by implementing ranges
# TODO: catch exceptions and display error messages


DVM_PREFIX = 'DVM_'


def is_identifier(name):
    """Check if ``name`` is a valid identifier."""
    return bool(re.match(r'^[a-z_]\w*$', s, re.IGNORECASE))


def get_dvm_name(expr):
    """Return DVM name for an element parameter or ``None``."""
    if not isinstance(expr, Expression):
        raise ValueError("Not an expression!")
    s = str(expr)
    if not is_identifier(s):
        raise ValueError("Not an identifier!")
    if not s.startswith(DVM_PREFIX):
        raise ValueError("Parameter not marked to be read from DVM.")
    # remove the prefix:
    return s[len(DVM_PREFIX):]


class Plugin(object):

    """
    Plugin class for MadGUI.
    """

    def __init__(self, frame, menubar):
        """
        Add plugin to the frame.

        Add a menu that can be used to connect to the online control. When
        connected, the plugin can be used to access parameters in the online
        database. This works only if the corresponding parameters were named
        exactly as in the database and are assigned with the ":=" operator.
        """
        from hit.online_control.beamoptikdll import BeamOptikDLL
        self._frame = frame
        self._BeamOptikDLL = BeamOptikDLL
        self._dvm = None
        # if the .dll is not available, there should be no menuitem:
        if not BeamOptikDLL.lib:
            pass
            #return # JUST FOR TESTING!
        # Create menu
        menu = wx.Menu()
        menubar.Append(menu, '&Online control')
        # Create menu items:
        def Append(label, help, action, condition):
            item = menu.Append(wx.ID_ANY, label, help)
            def on_click(event):
                if condition():
                    action()
            def on_update(event):
                event.Enable(condition())
            frame.Bind(wx.EVT_MENU, on_click, item)
            frame.Bind(wx.EVT_UPDATE_UI, on_update, item)
        Append('&Connect',
                'Connect online control interface',
                self.connect,
                self.is_disconnected)
        Append('&Disconnect',
                'Disconnect online control interface',
                self.disconnect,
                self.is_connected)
        Append('&Read all',
                'Read all parameters from the online database',
                self.read_all,
                self.has_sequence)
        Append('&Write all',
                'Write all parameters to the online database',
                self.write_all,
                self.has_sequence)

    def is_connected(self):
        """Check if online control is connected."""
        return self.connected

    def is_disconnected(self):
        """Check if online control is disconnected."""
        return not self.connected

    def has_sequence(self):
        """Check if online control is connected and a sequence is loaded."""
        return self.connected and self._control

    def connect(self):
        """Connect to online database."""
        self._dvm = self._BeamOptikDLL.GetInterfaceInstance()
        self._frame.vars['dvm'] = self._dvm

    def disconnect(self):
        """Disconnect from online database."""
        del self._frame.vars['dvm']
        self._dvm.FreeInterfaceInstance()

    @property
    def connected(self):
        """Check if the online control is connected."""
        return bool(self._dvm)

    @property
    def _control(self):
        """Return the online control (:class:`madgui.component.Model`)."""
        return self._frame.vars.get('control')

    def iter_dvm_params(self):
        """Iterate over all DVM parameters in the current sequence."""
        for elem in self._control.elements:
            for param in elem:
                knob = elem[param]
                try:
                    dvm_name = get_dvm_name(knob)
                except ValueError:
                    continue
                yield dvm_name, knob.value

    def read_all(self):
        """Read all parameters from the online database."""
        control = self._control
        madx = control.madx
        for dvm_name, _ in self.iter_dvm_params():
            value = self.get_dvm_param(dvm_name)
            madx.command(**{str(knob): value})
        control.twiss()

    def write_all(self):
        """Write all parameters to the online database."""
        for dvm_name, value in self.iter_dvm_params():
            value = self.set_dvm_param(dvm_name, value)

    def get_dvm_param(self, dvm_name):
        """Get a single parameter from the online database."""
        return self._dvm.GetFloatValue(dvm_name)

    def set_dvm_param(self, dvm_name, value):
        """Set a single parameter in the online database."""
        self._dvm.SetFloatValue(dvm_name, value)

