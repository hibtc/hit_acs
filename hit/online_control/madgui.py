"""
Plugin that integrates a beamoptikdll UI into MadGUI.
"""

from __future__ import absolute_import

import re
from collections import namedtuple
from pkg_resources import resource_string

import yaml

from cern.cpymad.types import Expression

from madgui.core import wx
from madgui.util import unit

# TODO: make GetFloatValueSD useful by implementing ranges
# TODO: catch exceptions and display error messages


DVM_PREFIX = 'DVM_'


def is_identifier(name):
    """Check if ``name`` is a valid identifier."""
    return bool(re.match(r'^[a-z_]\w*$', s, re.IGNORECASE))


def get_dvm_name(expr):
    """Return DVM name for an element parameter or raise ``ValueError``."""
    if not isinstance(expr, Expression):
        raise ValueError("Not an expression!")
    s = str(expr)
    if not is_identifier(s):
        raise ValueError("Not an identifier!")
    if not s.startswith(DVM_PREFIX):
        raise ValueError("Parameter not marked to be read from DVM.")
    # remove the prefix:
    return s[len(DVM_PREFIX):]


class Param(object):

    """Struct that holds information about DVM parameters."""

    def __init__(self,
                 elem_type,
                 param_type,
                 dvm_name,
                 madx_name,
                 madx_value):
        """
        Construct struct instance.

        :elem_type: element type (e.g. 'quadrupole')
        :param_type: parameter type (e.g. 'K1')
        :dvm_name: parameter name as expected by DVM
        :madx_name: knob name as defined in .madx file
        :madx_value: knob value as retrieved from MAD-X
        """
        self.elem_type = elem_type
        self.param_type = param_type
        self.dvm_name = dvm_name
        self.madx_name = madx_name
        self.madx_value = madx_value


def load_config():
    """Return the builtin configuration."""
    return yaml.safe_load(resource_string('hit.online_control', 'config.yml'))


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
        self._config = load_config()
        units = unit.from_config_dict(self._config['units'])
        self._utool = unit.UnitConverter(units, None)
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
        """
        Iterate over all DVM parameters in the current sequence.

        Yields instances of type :class:`Param`.
        """
        for elem in self._control.elements:
            for param in elem:
                knob = elem[param]
                try:
                    dvm_name = get_dvm_name(knob)
                except ValueError:
                    continue
                yield Param(elem_type=elem.type,
                            param_type=param_name,
                            dvm_name=dvm_name,
                            madx_name=str(knob),
                            madx_value=knob.value)

    def read_all(self):
        """Read all parameters from the online database."""
        control = self._control
        madx = control.madx
        for par in self.iter_dvm_params():
            value = self.get_value(par.param_type, par.dvm_name)
            plain_value = madx.utool.strip_unit(par.param_type, value)
            madx.command(**{str(par.madx_name): plain_value})
        control.twiss()

    def write_all(self):
        """Write all parameters to the online database."""
        for par in self.iter_dvm_params():
            self.set_value(par.param_type, par.dvm_name, par.madx_value)

    def get_float_value(self, dvm_name):
        """Get a single float value from the online database."""
        return self._dvm.GetFloatValue(dvm_name)

    def set_float_value(self, dvm_name, value):
        """Set a single float value in the online database."""
        self._dvm.SetFloatValue(dvm_name, value)

    def get_value(self, param_type, dvm_name):
        """Get a single value from the online database with unit."""
        plain_value = self.get_float_value(dvm_name)
        return self._utool.add_unit(param_type, value)

    def set_value(self, param_type, dvm_name, value):
        """Set a single parameter in the online database with unit."""
        plain_value = self._utool.strip_unit(param_type, value)
        self.set_float_value(dvm_name, plain_value)
