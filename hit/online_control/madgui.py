"""
Plugin that integrates a beamoptikdll UI into MadGUI.
"""

from __future__ import absolute_import

import re
from collections import namedtuple
from pkg_resources import resource_string

import yaml

from cpymad.types import Expression
from madgui.util.symbol import SymbolicValue
from madgui.core import wx
from madgui.util import unit

from .beamoptikdll import BeamOptikDLL, ExecOptions
from .dvm_parameters import DVM_ParameterList


# TODO: catch exceptions and display error messages


DVM_PREFIX = 'dvm_'


def is_identifier(name):
    """Check if ``name`` is a valid identifier."""
    return bool(re.match(r'^[a-z_]\w*$', name, re.IGNORECASE))


def strip_prefix(name, prefix):
    """Strip a specified prefix substring from a string."""
    if name.startswith(prefix):
        return name[len(prefix):]
    else:
        return name


def get_dvm_name(expr):
    """Return DVM name for an element parameter or raise ``ValueError``."""
    if isinstance(expr, SymbolicValue):
        s = str(expr._expression)
    elif isinstance(expr, Expression):
        s = str(expr)
    else:
        raise ValueError("Not an expression!")
    if not is_identifier(s):
        raise ValueError("Not an identifier!")
    if not s.startswith(DVM_PREFIX):
        raise ValueError("Parameter not marked to be read from DVM.")
    # remove the prefix:
    return s[len(DVM_PREFIX):]


Param = namedtuple('Param', [
    'elem_type',    # element type (e.g. 'quadrupole')
    'param_type',   # parameter type (e.g. 'K1')
    'dvm_name',     # parameter name as expected by DVM
    'madx_name',    # knob name as defined in .madx file
    'madx_value',   # knob value as retrieved from MAD-X
])


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
        # TODO: don't show menuitem if the .dll is not available?
        self._frame = frame
        self._BeamOptikDLL = BeamOptikDLL
        self._dvm = None
        self._config = load_config()
        units = unit.from_config_dict(self._config['units'])
        self._utool = unit.UnitConverter(units)
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
        menu.AppendSeparator()
        Append('&Read strengthes',
                'Read magnet strengthes from the online database',
                self.read_all,
                self.has_sequence)
        Append('&Write strengthes',
                'Write magnet strengthes to the online database',
                self.write_all,
                self.has_sequence)
        menu.AppendSeparator()
        Append('&Execute changes',
                'Apply parameter written changes to magnets',
                self.execute,
                self.has_sequence)
        menu.AppendSeparator()
        Append('Read &monitors',
               'Read SD values (beam envelope/position) from monitors',
               self.read_all_sd_values,
               self.has_sequence)

    def is_connected(self):
        """Check if online control is connected."""
        return self.connected

    def is_disconnected(self):
        """Check if online control is disconnected."""
        return not self.connected

    def has_sequence(self):
        """Check if online control is connected and a sequence is loaded."""
        return self.connected and bool(self._segman)

    def connect(self):
        """Connect to online database."""
        self._dvm = self._BeamOptikDLL.load_library()
        self._dvm.GetInterfaceInstance()
        self._frame.env['dvm'] = self._dvm

    def disconnect(self):
        """Disconnect from online database."""
        del self._frame.env['dvm']
        self._dvm.FreeInterfaceInstance()

    @property
    def connected(self):
        """Check if the online control is connected."""
        return bool(self._dvm)

    @property
    def _segman(self):
        """Return the online control (:class:`madgui.component.Model`)."""
        panel = self._frame.GetActiveFigurePanel()
        if panel:
            return panel.view.segman
        return None

    def iter_dvm_params(self):
        """
        Iterate over all DVM parameters in the current sequence.

        Yields instances of type :class:`Param`.
        """
        for elem in self._segman.elements:
            for param_name in elem:
                knob = elem[param_name]
                try:
                    dvm_name = get_dvm_name(knob)
                except ValueError:
                    continue
                yield Param(elem_type=elem['type'],
                            param_type=param_name,
                            dvm_name=dvm_name,
                            madx_name=knob._expression,
                            madx_value=knob.value)

    def read_all(self):
        """Read all parameters from the online database."""
        segman = self._segman
        madx = segman.simulator.madx
        for par in self.iter_dvm_params():
            value = self.get_value(par.param_type, par.dvm_name)
            plain_value = segman.simulator.utool.strip_unit(par.param_type, value)
            madx.command(**{str(par.madx_name): plain_value})
        # TODO: update only changed segments?:
        # TODO: segment ordering
        for segment in segman.segments.values():
            segment.twiss()

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
        return self._utool.add_unit(param_type, plain_value)

    def set_value(self, param_type, dvm_name, value):
        """Set a single parameter in the online database with unit."""
        plain_value = self._utool.strip_unit(param_type, value)
        self.set_float_value(dvm_name, plain_value)

    def execute(self, options=ExecOptions.CalcDif):
        self._dvm.ExecuteChanges(options)

    def read_all_sd_values(self):
        """Read out SD values (beam position/envelope)."""
        segman = self._segman
        for elem in self.iter_sd_monitors():
            sd_values = self.get_sd_values(elem['name'])
            if not sd_values:
                continue
            twiss_initial = {}
            ex = segman.beam['ex']
            ey = segman.beam['ey']
            if 'widthx' in sd_values:
                twiss_initial['betx'] = sd_values['widthx'] ** 2 / ex
            if 'widthy' in sd_values:
                twiss_initial['bety'] = sd_values['widthy'] ** 2 / ey
            if 'posx' in sd_values:
                twiss_initial['x'] = sd_values['posx']
            if 'posy' in sd_values:
                twiss_initial['y'] = sd_values['posy']
            twiss_initial['mixin'] = True
            segman.set_twiss_initial(
                segman.get_element_info(elem['name']),
                self._utool.dict_add_unit(twiss_initial))

    def get_sd_values(self, element_name):
        """Read out one SD monitor."""
        try:
            sd_values = {
                'widthx': self._get_sd_value(element_name, 'widthx'),
                'widthy': self._get_sd_value(element_name, 'widthy'),
                'posx': self._get_sd_value(element_name, 'posx'),
                'posy': self._get_sd_value(element_name, 'posy'),
            }
        except RuntimeError:
            return {}
        # The magic number -9999.0 is used to signal that the value cannot be
        # used.
        # TODO: sometimes width=0 is returned. What is the reason/meaning of
        # this?
        if sd_values['widthx'] <= 0 or sd_values['widthy'] <= 0:
            return {}
        mm = unit.units.mm
        return {
            'widthx': sd_values['widthx'] * mm,
            'widthy': sd_values['widthy'] * mm,
            'posx': sd_values['posx'] * mm,
            'posy': sd_values['posy'] * mm,
        }

    def _get_sd_value(self, element_name, param_name):
        """Read a single SD value into a dictionary."""
        element_name = re.sub(':\d+$', '', element_name)
        element_name = strip_prefix(element_name, 'sd_')
        param_name = param_name
        sd_name = param_name + '_' + element_name
        return self._dvm.GetFloatValueSD(sd_name.upper())

    def iter_sd_monitors(self):
        for element in self._segman.elements:
            if not element['name'].lower().startswith('sd_'):
                continue
            if not element['type'].lower().endswith('monitor'):
                continue
            yield element
