# encoding: utf-8
"""
Madgui online control plugin.
"""

from __future__ import absolute_import

import logging
import itertools
try:
    from importlib.resources import resource_stream     # faster import
except ImportError:
    from pkg_resources import resource_stream

from pydicti import dicti

from .util import load_yaml_resource

from .beamoptikdll import BeamOptikDLL, ExecOptions
from .stub import BeamOptikDllProxy

from madgui.core.base import Object, Signal
from madgui.qt import QtGui
from madgui.core import unit
from madgui.online import api

from .dvm_parameters import load_csv, DVM_Parameter


class StubLoader(api.PluginLoader):

    title = '&test stub'
    descr = 'a stub version (for offline testing)'
    hotkey = 'Ctrl+C'

    @classmethod
    def check_avail(cls):
        return True

    @classmethod
    def load(cls, frame):
        # logger = frame.getLogger('hit_csys.stub')
        logger = logging.getLogger('hit_csys.stub')
        proxy = BeamOptikDllProxy(frame, logger)
        dvm = BeamOptikDLL(proxy)
        dvm.on_model_changed = proxy.on_model_changed
        params = load_dvm_parameters()
        return HitOnlineControl(dvm, params, frame)


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
        return HitOnlineControl(dvm, params, frame)


def load_dvm_parameters():
    with resource_stream('hit_csys', 'DVM-Parameter_v2.10.0-HIT.csv') as f:
        parlist = load_csv(f, 'utf-8')
    return dicti(
        (el_name, dicti((p.name, p) for p in params))
        for el_name, params in parlist)


def _get_sd_value(dvm, el_name, param_name):
    """Return a single SD value (with unit)."""
    sd_name = param_name + '_' + el_name
    plain_value = dvm.GetFloatValueSD(sd_name.upper())
    return plain_value / 1000       # mm to m


class HitOnlineControl(api.OnlinePlugin):

    def __init__(self, dvm, params, frame):
        self._dvm = dvm
        self._params = params
        self._frame = frame
        self._config = load_yaml_resource('hit_csys', 'config.yml')

    # OnlinePlugin API

    def connect(self):
        """Connect to online database (must be loaded)."""
        self._dvm.GetInterfaceInstance()
        self._frame.model_changed.connect(self.on_model_changed)
        self.on_model_changed()

    def disconnect(self):
        """Disconnect from online database."""
        self._dvm.FreeInterfaceInstance()
        self._frame.model_changed.disconnect(self.on_model_changed)

    def on_model_changed(self):
        if hasattr(self._dvm, 'on_model_changed'):
            self._dvm.on_model_changed()

    @property
    def _model(self):
        return self._frame.model

    def execute(self, options=ExecOptions.CalcDif):
        """Execute changes (commits prior set_value operations)."""
        self._dvm.ExecuteChanges(options)

    def param_info(self, knob):
        """Get parameter info for backend key."""
        if isinstance(knob, Knob):
            return knob.info
        el_name = knob.split('_', 1)[1]
        try:
            return self._params[el_name][knob]
        except KeyError:
            return None

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
            if src.startswith('width') and val <= 0:
                return {}
            values[dst] = val
        return values

    def get_knob(self, elem, attr):
        """Return a :class:`Knob` belonging to the given attribute."""
        attr = attr.lower()
        el_name = elem['name'].lower()
        el_type = elem['type'].lower()
        if '_' in el_name:
            body, suffix = el_name.rsplit('_', 1)
            if suffix == 'corr' and attr == 'kick':
                el_name = body
        # Sometimes the parameter name does not include the element H/V
        # suffix, e.g.: R1MS1H -> ax_R1MS1, R1MS1V -> ay_R1MS1
        if el_name[-1:] in 'hv':
            suffixes = [el_name, el_name[:-1]]
        else:
            suffixes = [el_name]
        el_pars = self._params.get(el_name, {})
        el_expr = getattr(elem[attr], '_expression', '').lower()
        prefixes = PREFIXES.get((el_type, attr), [])
        # Prefer the parameter name defined by the expression; otherwise use
        # the element name plus known prefixes, such as 'ax_', 'ay_':
        par_names = [el_expr] + [
            prefix + '_' + suffix
            for prefix, suffix in itertools.product(prefixes, suffixes)
        ]
        for param in map(el_pars.get, par_names):
            if param:
                return Knob(self, elem, attr, param)
        if  (el_name.startswith('gant') and
             el_type == 'srotation' and
             attr =='angle'):
            param = DVM_Parameter(
                name='gantry_angle',
                ui_name='gantry_angle',
                ui_hint='',
                ui_prec=3,
                unit=1*unit.units.degree,
                ui_unit=1*unit.units.degree,
                ui_conv=1,
            )
            return MEFI_Param(self, elem, 'gantry', param, 3)

    def read_param(self, param):
        """Read parameter. Return numeric value."""
        return self._dvm.GetFloatValue(param)

    def write_param(self, param, value):
        """Update parameter into control system."""
        self._dvm.SetFloatValue(param, value)

    def get_beam(self):
        units  = unit.units
        e_para = ENERGY_PARAM.get(self._model.seq_name, 'E_HEBT')
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

# NOTE: order is important, so keep 'dax' before 'ax', etc:
PREFIXES = {
    ('sbend',   'angle'):  ['ax'],
    ('quadrupole', 'k1'):  ['kl_efg', 'kl'],
    ('quadrupole', 'k1s'):  ['kl_efg', 'kl'],
    ('hkicker',  'kick'):  ['dax', 'ax'],
    ('vkicker',  'kick'):  ['day', 'ay'],
    ('solenoid',   'ks'):  ['ks'],
    ('multipole', 'knl[0]'):  ['dax', 'ax'],
    ('multipole', 'ksl[0]'):  ['day', 'ay'],
}

CSYS_ATTR = { 'k1': 'kl', 'k1s': 'kl' }


class Knob(api.Knob):

    def __init__(self, plug, elem, attr, param):
        super().__init__(plug, elem, CSYS_ATTR.get(attr, attr),
                         param.name, param.unit)
        self.info = param


class MEFI_Param(Knob):

    def __init__(self, plug, elem, attr, param, idx):
        super().__init__(plug, elem, attr, param)
        self.idx = idx

    def read(self):
        return unit.madx_units.strip_unit(
            self.attr, unit.add_unit(
                self.plug._dvm.GetMEFIValue()[0][self.idx],
                self.info.unit))

    def write(self, value):
        pass
        #raise NotImplementedError(
        #    "Must change MEFI parameters via BeamOptikDLL GUI")
