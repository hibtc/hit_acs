# encoding: utf-8
"""
Madgui online control plugin.
"""

from __future__ import absolute_import

import logging
try:
    from importlib.resources import resource_stream     # faster import
except ImportError:
    from pkg_resources import resource_stream

from pydicti import dicti

from .util import load_yaml_resource

from .beamoptikdll import BeamOptikDLL, ExecOptions
from .stub import BeamOptikDllProxy

from madqt.core.base import Object, Signal
from madqt.qt import QtGui
from madqt.core import unit
from madqt.online import api

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
        dvm.on_workspace_changed = proxy.on_workspace_changed
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
    def elem_param_dict(el_name, parlist):
        ret = dicti((p.name, p) for p in parlist)
        # NOTE: the following is an ugly hack to correct for missing suffixes
        # for some of the DB parameters. It would better to find a solution
        # that is not hard-coded.
        el_name = el_name.lower()
        if el_name.endswith('h') or el_name.endswith('v'):
            update = {}
            el_prefix = el_name[:-1]
            el_suffix = el_name[-1]
            for k, v in ret.items():
                if k.lower().endswith('_' + el_prefix):
                    update[k+el_suffix] = v
            ret.update(update)
        return ret
    return dicti(
        (k, elem_param_dict(k, l))
        for k, l in parlist.items())


def _get_sd_value(dvm, el_name, param_name):
    """Return a single SD value (with unit)."""
    sd_name = param_name + '_' + el_name
    plain_value = dvm.GetFloatValueSD(sd_name.upper())
    return plain_value * unit.units.mm


class HitOnlineControl(api.OnlinePlugin):

    def __init__(self, dvm, params, frame):
        self._dvm = dvm
        self._params = params
        self._frame = frame
        self._config = load_yaml_resource('hit_csys', 'config.yml')
        self._utool = unit.UnitConverter.from_config_dict(
            self._config['units'])

    # OnlinePlugin API

    def connect(self):
        """Connect to online database (must be loaded)."""
        self._dvm.GetInterfaceInstance()
        self._frame.workspace_changed.connect(self.on_workspace_changed)
        self.on_workspace_changed()

    def disconnect(self):
        """Disconnect from online database."""
        self._dvm.FreeInterfaceInstance()
        self._frame.workspace_changed.disconnect(self.on_workspace_changed)

    def on_workspace_changed(self):
        if hasattr(self._dvm, 'on_workspace_changed'):
            self._dvm.on_workspace_changed()

    @property
    def _segment(self):
        return self._frame.workspace.segment

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
            if src.startswith('width') and val.magnitude <= 0:
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
        el_pars = self._params.get(el_name, {})
        el_expr = getattr(elem[attr], '_expression', '').lower()
        prefixes = [el_expr.split('_')[0]] if el_expr else []
        prefixes += PREFIXES.get((el_type, attr), [])
        for prefix in prefixes:
            param = el_pars.get(prefix + '_' + el_name)
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
                unit='°',
                ui_unit='°',
                ui_conv=1,
                example=0,
            )
            return MEFI_Param(self, elem, 'gantry', param, 3)


    def read_param(self, param):
        """Read parameter. Return numeric value. No units!"""
        return self._dvm.GetFloatValue(param)

    def write_param(self, param, value):
        """Update parameter into control system. No units!"""
        self._dvm.SetFloatValue(param, value)

    def get_beam(self):
        units       = unit.units
        vacc        = self._dvm.GetSelectedVAcc()
        particle    = ('C', 'p', 'He')[vacc // 5]
        charge      = (  6,   1,    2)[vacc // 5]      # hebt, TODO: He?
        nucl_num    = ( 12,   1,    3)[vacc // 5]      # hebt, TODO: He?
        e_kin_per_u = self._dvm.GetMEFIValue()[0][0] * units.MeV / units.u
        return {
            'particle': particle,
            'charge':   charge   *  units.e,
            'mass':     nucl_num * units.u,
            'energy':   nucl_num * units.u * (1*units.c**2 + e_kin_per_u),
        }


# NOTE: order is important, so keep 'dax' before 'ax', etc:
PREFIXES = {
    ('sbend',   'angle'):  ['ax'],
    ('quadrupole', 'k1'):  ['kl'],
    ('hkicker',  'kick'):  ['dax', 'ax'],
    ('vkicker',  'kick'):  ['day', 'ay'],
    ('solenoid',   'ks'):  ['ks'],
    ('multipole', 'knl[0]'):  ['dax', 'ax'],
    ('multipole', 'ksl[0]'):  ['day', 'ay'],
}

CSYS_ATTR = { 'k1': 'kl' }


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
        return self.plug._dvm.GetMEFIValue()[0][self.idx]

    def write(self, value):
        pass
        #raise NotImplementedError(
        #    "Must change MEFI parameters via BeamOptikDLL GUI")
