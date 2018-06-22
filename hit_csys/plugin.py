# encoding: utf-8
"""
Madgui online control plugin.
"""

from __future__ import absolute_import

from functools import partial
try:
    from importlib_resources import open_binary as resource_stream
except ImportError:
    from pkg_resources import resource_stream

from pydicti import dicti

from .beamoptikdll import BeamOptikDLL, ExecOptions
from .stub import BeamOptikDllProxy

from madgui.core import unit
from madgui.online import api
from madgui.util.collections import Bool

from .dvm_parameters import load_csv
from .offsets import find_offsets


class StubLoader(api.PluginLoader):

    title = '&test stub'
    descr = 'a stub version (for offline testing)'
    hotkey = 'Ctrl+C'

    @classmethod
    def check_avail(cls):
        return True

    @classmethod
    def load(cls, frame):
        offsets = find_offsets(frame.config.get('runtime_path', '.'))
        model = frame.model
        proxy = BeamOptikDllProxy(model, offsets)
        if frame.config.get('str_file'):
            proxy.load_float_values(frame.config.str_file)
        if frame.config.get('sd_file'):
            proxy.load_sd_values(frame.config.sd_file)
        dvm = BeamOptikDLL(proxy)
        params = load_dvm_parameters()
        plugin = HitOnlineControl(dvm, params, frame.model, offsets)
        plugin.connected.changed.connect(partial(update_ns, frame, dvm))
        plugin.connected.changed.connect(proxy.on_connected_changed)
        return plugin


class DllLoader(api.PluginLoader):

    title = '&online control'
    descr = 'the online control'
    hotkey = None

    @classmethod
    def check_avail(cls):
        return BeamOptikDLL.check_library()

    @classmethod
    def load(cls, frame):
        """Connect to online database."""
        dvm = BeamOptikDLL.load_library()
        params = load_dvm_parameters()
        offsets = find_offsets(frame.config.get('runtime_path', '.'))
        plugin = HitOnlineControl(dvm, params, frame.model, offsets)
        plugin.connected.changed.connect(partial(update_ns, frame, dvm))
        return plugin


def update_ns(frame, dll, connected):
    if connected:
        frame.context['dll'] = dll
    else:
        frame.context.pop('dll', None)


def load_dvm_parameters():
    with resource_stream('hit_csys', 'DVM-Parameter_v2.10.0-HIT.csv') as f:
        parlist = load_csv(f, 'utf-8')
    return dicti(
        (p.name, p)
        for el_name, params in parlist
        for p in params)


def _get_sd_value(dvm, el_name, param_name):
    """Return a single SD value (with unit)."""
    sd_name = param_name + '_' + el_name
    plain_value = dvm.GetFloatValueSD(sd_name.upper())
    return plain_value / 1000       # mm to m


class HitOnlineControl(api.OnlinePlugin):

    def __init__(self, dvm, params, model=None, offsets=None):
        self._dvm = dvm
        self._params = params
        self._params.update({
            'gantry_angle': api.ParamInfo(
                name='gantry_angle',
                ui_name='gantry_angle',
                ui_hint='',
                ui_prec=3,
                unit=1*unit.units.degree,
                ui_unit=1*unit.units.degree,
                ui_conv=1),
        })
        self._model = model
        self._offsets = {} if offsets is None else offsets
        self.connected = Bool(False)

    # OnlinePlugin API

    def connect(self):
        """Connect to online database (must be loaded)."""
        self._dvm.GetInterfaceInstance()
        self.connected.set(True)

    def disconnect(self):
        """Disconnect from online database."""
        self._dvm.FreeInterfaceInstance()
        self.connected.set(False)

    def execute(self, options=ExecOptions.CalcDif):
        """Execute changes (commits prior set_value operations)."""
        self._dvm.ExecuteChanges(options)

    def param_info(self, knob):
        """Get parameter info for backend key."""
        return self._params.get(knob.lower())

    def read_monitor(self, name):
        """
        Read out one monitor, return values as dict with keys:

            widthx:     Beam x width
            widthy:     Beam y width
            posx:       Beam x position
            posy:       Beam y position
        """
        keys_backend = ('posx', 'posy', 'widthx', 'widthy')
        keys_internal = ('posx', 'posy', 'envx', 'envy')
        values = {}
        for src, dst in zip(keys_backend, keys_internal):
            # TODO: Handle usability of parameters individually
            try:
                val = _get_sd_value(self._dvm, name, src)
            except RuntimeError:
                return {}
            # TODO: move sanity check to later, so values will simply be
            # unchecked/grayed out, instead of removed completely
            # The magic number -9999.0 signals corrupt values.
            # FIXME: Sometimes width=0 is returned. ~ Meaning?
            if val == -9999 or src.startswith('width') and val <= 0:
                return {}
            values[dst] = val
        xoffs, yoffs = self._offsets.get(name, (0, 0))
        values['posx'] += xoffs
        values['posy'] += yoffs
        values['posx'] = -values['posx']
        return values

    def read_param(self, param):
        """Read parameter. Return numeric value."""
        if param == 'gantry_angle':
            return self._dvm.GetMEFIValue()[0][3]
        return self._dvm.GetFloatValue(param)

    def write_param(self, param, value):
        """Update parameter into control system."""
        self._dvm.SetFloatValue(param, value)

    def get_beam(self):
        units  = unit.units
        e_para = ENERGY_PARAM.get(self._model().seq_name, 'E_HEBT')
        z_num  = self._dvm.GetFloatValue('Z_POSTSTRIP')
        mass   = self._dvm.GetFloatValue('A_POSTSTRIP') * units.u
        charge = self._dvm.GetFloatValue('Q_POSTSTRIP') * units.e
        e_kin  = (self._dvm.GetFloatValue(e_para) or 1) * units.MeV / units.u
        return {
            'particle': PERIODIC_TABLE[round(z_num)],
            'charge':   unit.from_ui('charge', charge),
            'mass':     unit.from_ui('mass',   mass),
            'energy':   unit.from_ui('energy', mass * (e_kin + 1*units.c**2)),
        }


ENERGY_PARAM = {
    'lebt': 'E_SOURCE',
    'mebt': 'E_MEBT',
}

PERIODIC_TABLE = {
    1: 'p',
    2: 'He',
    6: 'C',
    8: 'O',
}
