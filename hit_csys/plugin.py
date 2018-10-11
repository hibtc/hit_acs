# encoding: utf-8
"""
Madgui online control plugin.
"""

from __future__ import absolute_import

import logging
from functools import partial
try:
    from importlib_resources import open_binary as resource_stream
except ImportError:
    from pkg_resources import resource_stream

from pydicti import dicti

from .beamoptikdll import BeamOptikDLL, ExecOptions
from .stub import BImpostikDLL

import madgui.util.unit as unit
import madgui.online.api as api
from madgui.util.collections import Bool

from .dvm_parameters import load_csv
from .offsets import find_offsets


def update_ns(ns, dll, connected):
    ns.dll = dll if connected else None


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


class _HitBackend(api.Backend):

    def __init__(self, dvm, params, model=None, offsets=None, settings=None):
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
        self.settings = settings

    # Backend API

    def connect(self):
        """Connect to online database (must be loaded)."""
        self._dvm.GetInterfaceInstance()
        self.connected.set(True)
        settings = self.settings or {}
        # We should probably select VAcc/MEFI based on loaded sequence… or the
        # other way round? …anyway doing something unexpected might be even
        # more inconvienient than simply using the last selected:
        if settings.get('vacc'):
            self._dvm.SelectVAcc(settings['vacc'])
        if settings.get('mefi'):
            self._dvm.SelectMEFI(settings['vacc'], *settings['mefi'])

    def disconnect(self):
        """Disconnect from online database."""
        (self.settings or {}).update(self.export_settings())
        self._dvm.FreeInterfaceInstance()
        self.connected.set(False)

    def export_settings(self):
        mefi = self._dvm.GetMEFIValue()[1]
        settings = {
            'variant': self._dvm._variant,
            'vacc': self._dvm.GetSelectedVAcc(),
            'mefi': mefi and tuple(mefi),
        }
        if hasattr(self._dvm, 'export_settings'):
            settings.update(self._dvm.export_settings())
        return settings

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
        try:
            return self._dvm.GetFloatValue(param)
        except RuntimeError as e:
            logging.error("{} for {!r}".format(e, param))

    def write_param(self, param, value):
        """Update parameter into control system."""
        try:
            self._dvm.SetFloatValue(param, value)
        except RuntimeError as e:
            logging.error("{} for {!r} = {}".format(e, param, value))

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


class OnlineBackend(_HitBackend):

    def __init__(self, session, settings):
        """Connect to online database."""
        dvm = BeamOptikDLL.load_library(
            variant=settings.get('variant', 'HIT'))
        params = load_dvm_parameters()
        offsets = find_offsets(settings.get('runtime_path', '.'))
        super.__init__(dvm, params, session.model, offsets, settings)
        self.connected.changed.connect(
            partial(update_ns, session.user_ns, dvm))


class TestBackend(_HitBackend):

    def __init__(self, session, settings):
        offsets = find_offsets(settings.get('runtime_path', '.'))
        model = session.model
        proxy = BImpostikDLL(model, offsets, settings)
        proxy.set_window(session.window())
        params = load_dvm_parameters()
        super().__init__(proxy, params, session.model, offsets)
        self.connected.changed.connect(proxy.on_connected_changed)
        self.connected.changed.connect(
            partial(update_ns, session.user_ns, proxy))


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
