# encoding: utf-8
"""
Madgui online control plugin.
"""

from __future__ import absolute_import

import os
import logging

from importlib_resources import read_binary
from pydicti import dicti

from .beamoptikdll import BeamOptikDLL, ExecOptions
from .beamoptikstub import BeamOptikStub

import madgui.util.unit as unit
import madgui.online.api as api
from madgui.util.misc import relpath as safe_relpath
from madgui.util.collections import Bool
from madgui.util.qt import SingleWindow

from .dvm_parameters import load_csv
from .offsets import find_offsets


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

MEFI_PARAMS = ('beam_energy', 'beam_focus', 'beam_intensity', 'gantry_angle')


def load_dvm_parameters():
    blob = read_binary('hit_acs', 'DVM-Parameter_v2.10.0-HIT.csv')
    parlist = load_csv(blob.splitlines(), 'utf-8')
    return dicti({p['name']: p for p in parlist})


class _HitACS(api.Backend):

    def __init__(self, lib, params, model=None, offsets=None, settings=None):
        self._lib = lib
        self._params = dicti({
            'beam_energy': dict(
                name='beam_energy',
                ui_name='beam_energy',
                ui_hint='',
                ui_prec=3,
                unit='MeV/u',
                ui_unit='MeV/u',
                ui_conv=1),
            'beam_focus': dict(
                name='beam_focus',
                ui_name='beam_focus',
                ui_hint='',
                ui_prec=3,
                unit='m',
                ui_unit='mm',
                ui_conv=1000),
            'beam_intensity': dict(
                name='beam_intensity',
                ui_name='beam_intensity',
                ui_hint='',
                ui_prec=3,
                unit='',
                ui_unit='',
                ui_conv=1),
            'gantry_angle': dict(
                name='gantry_angle',
                ui_name='gantry_angle',
                ui_hint='',
                ui_prec=3,
                unit='°',
                ui_unit='°',
                ui_conv=1),
        })
        self._params.update(params)
        self._model = model
        self._offsets = {} if offsets is None else offsets
        self.connected = Bool(False)
        self.settings = settings

    @property
    def beamoptikdll(self):
        """Python wrapper for the BeamOptikDLL exposed methods."""
        return self._lib

    # Backend API

    def connect(self):
        """Connect to online database (must be loaded)."""
        self._lib.GetInterfaceInstance()
        self.connected.set(True)
        settings = self.settings or {}
        # We should probably select VAcc/MEFI based on loaded sequence… or the
        # other way round? …anyway doing something unexpected might be even
        # more inconvienient than simply using the last selected:
        if settings.get('vacc'):
            self._lib.SelectVAcc(settings['vacc'])
        if settings.get('vacc') and settings.get('mefi'):
            self._lib.SelectMEFI(settings['vacc'], *settings['mefi'])

    def disconnect(self):
        """Disconnect from online database."""
        (self.settings or {}).update(self.export_settings())
        self._lib.FreeInterfaceInstance()
        self.connected.set(False)

    def export_settings(self):
        mefi = self._lib.GetMEFIValue()[1]
        settings = {
            'variant': self._lib._variant,
            'vacc': self._lib.GetSelectedVAcc(),
            'mefi': mefi and tuple(mefi),
        }
        if hasattr(self._lib, 'export_settings'):
            settings.update(self._lib.export_settings())
        return settings

    def execute(self, options=ExecOptions.CalcDif):
        """Execute changes (commits prior set_value operations)."""
        self._lib.ExecuteChanges(options)

    def param_info(self, knob):
        """Get parameter info for backend key."""
        data = self._params.get(knob.lower())
        return data and api.ParamInfo(**data)

    def read_monitor(self, name):
        """
        Read out one monitor, return values as dict with keys
        posx/posy/envx/envy.
        """
        # TODO: Handle usability of parameters individually
        try:
            GetFloatValueSD = self._lib.GetFloatValueSD
            posx = GetFloatValueSD('posx_' + name)
            posy = GetFloatValueSD('posy_' + name)
            envx = GetFloatValueSD('widthx_' + name)
            envy = GetFloatValueSD('widthy_' + name)
        except RuntimeError:
            return {}
        # TODO: move sanity check to later, so values will simply be
        # unchecked/grayed out, instead of removed completely
        # The magic number -9999.0 signals corrupt values.
        # FIXME: Sometimes width=0 is returned. ~ Meaning?
        if posx == -9999 or posy == -9999 or envx <= 0 or envy <= 0:
            return {}
        xoffs, yoffs = self._offsets.get(name, (0, 0))
        return {
            'posx': -(posx / 1000 + xoffs),
            'posy': +(posy / 1000 + yoffs),
            'envx': envx / 1000,
            'envy': envy / 1000,
        }

    def read_params(self, param_names=None, warn=True):
        """Read all specified params (by default all). Return dict."""
        if param_names is None:
            param_names = self._params
            warn = False
        return {
            param: value
            for param in param_names
            for value in [self.read_param(param, warn=warn)]
            if value is not None
        }

    def read_param(self, param, warn=True):
        """Read parameter. Return numeric value."""
        param = param.lower()
        if param in MEFI_PARAMS:
            return self._lib.GetMEFIValue()[0][MEFI_PARAMS.index(param)]
        try:
            return self._lib.GetFloatValue(param)
        except RuntimeError as e:
            if warn:
                logging.warning("{} for {!r}".format(e, param))

    def write_param(self, param, value):
        """Update parameter into control system."""
        param = param.lower()
        if param in MEFI_PARAMS:
            cur_value = self.read_param(param)
            if value != cur_value:
                logging.warning(
                    "Unable to set {}={} (is {}). This parameter "
                    "can only be changed by selecting the MEFI combination!"
                    .format(param, value, cur_value))
            return
        try:
            self._lib.SetFloatValue(param, value)
        except RuntimeError as e:
            logging.error("{} for {!r} = {}".format(e, param, value))

    def get_beam(self):
        units  = unit.units
        e_para = ENERGY_PARAM.get(self._model().seq_name, 'E_HEBT')
        z_num  = self._lib.GetFloatValue('Z_POSTSTRIP')
        mass   = self._lib.GetFloatValue('A_POSTSTRIP') * units.u
        charge = self._lib.GetFloatValue('Q_POSTSTRIP') * units.e
        e_kin  = (self._lib.GetFloatValue(e_para) or 1) * units.MeV / units.u
        return {
            'particle': PERIODIC_TABLE[round(z_num)],
            'charge':   unit.from_ui('charge', charge),
            'mass':     unit.from_ui('mass',   mass),
            'energy':   unit.from_ui('energy', mass * (e_kin + 1*units.c**2)),
        }


class HitACS(_HitACS):

    def __init__(self, session, settings):
        """Connect to online database."""
        params = load_dvm_parameters()
        offsets = find_offsets(settings.get('runtime_path', '.'))
        lib = session.user_ns.beamoptikdll = BeamOptikDLL(
            variant=settings.get('variant', 'HIT'))
        super().__init__(lib, params, session.model, offsets, settings)


class TestACS(_HitACS):

    def __init__(self, session, settings):
        params = load_dvm_parameters()
        offsets = find_offsets(settings.get('runtime_path', '.'))
        # Don't pass `session.model()` to the stub. It should use an
        # independent simulation, which is cloned upon connection in
        # `on_model_changed`:
        lib = session.user_ns.beamoptikdll = BeamOptikStub(
            None, offsets, settings)
        super().__init__(lib, params, session.model, offsets)
        self.menu = None
        self.window = None
        self.set_window(session.window())
        self.connected.changed.connect(self.on_connected_changed)

        self.str_file = settings.get('str_file')
        self.sd_file = settings.get('sd_file')

    def load_float_values(self, filename):
        from madgui.util.export import read_str_file
        self.str_file = filename = os.path.abspath(filename)
        self._lib.set_float_values(read_str_file(filename))

    def load_sd_values(self, filename):
        from madgui.util.yaml import load_file
        self.sd_file = filename = os.path.abspath(filename)
        data = load_file(filename)
        cols = {
            'envx': 'widthx',
            'envy': 'widthy',
            'x': 'posx',
            'y': 'posy',
        }
        self.auto_sd.set(False)
        self._lib.set_sd_values({
            cols[param]+'_'+elem: value
            for elem, values in data['monitor'].items()
            for param, value in values.items()
        })

    def set_window(self, window):
        self.window = window
        self.menu = window and window.acs_settings_menu
        if window is None:
            return
        from madgui.util.menu import extend, Item, Separator
        self.jitter = Bool(self._lib.jitter)
        self.auto_sd = Bool(self._lib.auto_sd)
        self.menu.clear()
        extend(window, self.menu, [
            Item('&Vary readouts', None,
                 'Emulate continuous readouts using gaussian jitter',
                 self._toggle_jitter,
                 checked=self.jitter),
            Item('Add &magnet aberrations', None,
                 'Add small deltas to all magnet strengths',
                 self._lib._aberrate_strengths),
            Separator,
            Item('Autoset readouts from model', None,
                 'Autoset monitor readout values from model twiss table',
                 self._toggle_auto_sd,
                 checked=self.auto_sd),
            Separator,
            Item('Load readouts from file', None,
                 'Load monitor readout values from monitor export',
                 self._open_sd_values),
            Item('Load strengths from file', None,
                 'Load magnet strengths from strength export',
                 self._open_float_values),
            Separator,
            Item('Edit backend simulation model', None,
                 'Edit initial conditions for the model used to simulate '
                 'the backend behaviour',
                 self._edit_model_initial_conditions.create),
        ])

    def export_settings(self):
        return {
            'jitter': self.jitter(),
            'shot_interval': self._lib.sd_cache.timeout,
            'auto_sd': self.auto_sd(),
            'str_file': self.str_file and safe_relpath(self.str_file, None),
            'sd_file': self.str_file and safe_relpath(self.sd_file, None),
        }

    def _toggle_jitter(self):
        self.jitter.set(not self.jitter())
        self._lib.jitter = self.jitter()

    def _toggle_auto_sd(self):
        self.auto_sd.set(not self.auto_sd())
        self._lib.auto_sd = self.auto_sd()
        self._lib.update_sd_values()

    def _open_sd_values(self):
        from madgui.widget.filedialog import getOpenFileName
        filters = [
            ("YAML files", "*.yml", "*.yaml"),
            ("All files", "*"),
        ]
        folder = self.window.str_folder or self.window.folder
        if self.sd_file:
            folder = os.path.dirname(self.sd_file)
        filename = getOpenFileName(
            self.window, 'Open monitor export', folder, filters)
        if filename:
            self.load_sd_values(filename)

    def _open_float_values(self):
        from madgui.widget.filedialog import getOpenFileName
        filters = [
            ("STR files", "*.str"),
            ("All files", "*"),
        ]
        folder = self.window.str_folder or self.window.folder
        if self.str_file:
            folder = os.path.dirname(self.str_file)
        filename = getOpenFileName(
            self.window, 'Open strength export', folder, filters)
        if filename:
            self.load_float_values(filename)

    def on_connected_changed(self, connected):
        if connected:
            self.model.changed.connect(self.on_model_changed)
            self.on_model_changed(self.model())
        else:
            self.model.changed.disconnect(self.on_model_changed)
        if self.menu:
            self.menu.setEnabled(connected)

    def on_model_changed(self, model):
        clone = model and model.load_file(model.filename, stdout=False)
        self._lib.set_model(clone)
        if clone:
            if self.str_file:
                self.load_float_values(self.str_file)
            if self.sd_file:
                self.load_sd_values(self.sd_file)

    @SingleWindow.factory
    def _edit_model_initial_conditions(self):
        from madgui.widget.params import model_params_dialog
        return model_params_dialog(
            self._lib.model, parent=self.window, folder=self.window.folder)

    @property
    def model(self):
        return self._model
