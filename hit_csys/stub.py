"""
Fake implementation of BeamOptikDLL wrapper. Emulates the API of
:class:`~hit_csys.beamoptikdll.BeamOptikDLL`. Primarily used for
offline testing of the basic functionality.
"""

import os
import logging
import functools
from random import gauss, gammavariate as gamma

from pydicti import dicti

from .beamoptikdll import DVMStatus, GetOptions, EFI
from .util import TimeoutCache, LightBox


__all__ = [
    'BImpostikDLL',
]


def _api_meth(func):
    """Decorator for tracing calls to BeamOptikDLL API methods."""
    @functools.wraps(func)
    def wrapper(self, *args):
        logging.debug('{}{}'.format(func.__name__, args))
        return func(self, *args)
    return wrapper


class BImpostikDLL(object):

    """A fake implementation of the BeamOptikDLL wrapper."""

    # TODO: Support read-only/write-only parameters
    # TODO: Prevent writing unknown parameters by default

    def __init__(self, model=None, offsets=None, settings=None, variant='HIT'):
        """Initialize new library instance with no interface instances."""
        if settings is None:
            settings = {}
        self.params = dicti()
        self.sd_values = dicti()
        self.sd_cache = TimeoutCache(
            self._get_jittered_sd,
            timeout=settings.get('shot_interval', 1.0))
        self.model = model
        self.offsets = {} if offsets is None else offsets
        self.settings = settings
        self.jitter = LightBox(settings.get('jitter', True))
        self.auto_params = LightBox(settings.get('auto_params', True))
        self.auto_sd = LightBox(settings.get('auto_sd', True))
        self.menu = None
        self.window = None
        self._variant = variant
        self.str_file = str_file = settings.get('str_file')
        self.sd_file = sd_file = settings.get('sd_file')
        if str_file:
            self.load_float_values(self.str_file)
        if sd_file:
            self.load_sd_values(self.sd_file)

    def load_float_values(self, filename):
        from madgui.util.export import read_str_file
        self.str_file = filename = os.path.abspath(filename)
        self.set_float_values(read_str_file(filename))

    def load_sd_values(self, filename):
        import yaml
        self.sd_file = filename = os.path.abspath(filename)
        with open(filename) as f:
            data = yaml.safe_load(f)
        cols = {
            'envx': 'widthx',
            'envy': 'widthy',
            'x': 'posx',
            'y': 'posy',
        }
        self.set_sd_values({
            cols[param]+'_'+elem: value
            for elem, values in data['monitor'].items()
            for param, value in values.items()
        })

    def set_window(self, window):
        self.window = window
        self.menu = window and window.csys_settings_menu
        if window is None:
            return
        from madgui.util.collections import Bool
        from madgui.util.menu import extend, Item, Separator
        self.jitter = Bool(self.jitter())
        self.auto_params = Bool(self.auto_params())
        self.auto_sd = Bool(self.auto_sd())
        self.menu.clear()
        extend(window, self.menu, [
            Item('&Vary readouts', None,
                 'Emulate continuous readouts using gaussian jitter',
                 self._toggle_jitter,
                 checked=self.jitter),
            Item('Add &magnet aberrations', None,
                 'Add small deltas to all magnet strengths',
                 self._aberrate_strengths),
            Separator,
            Item('Autoset readouts from model', None,
                 'Autoset monitor readout values from model twiss table',
                 self._toggle_auto_sd,
                 checked=self.auto_sd),
            Item('Autoset strengths from model', None,
                 'Autoset magnet strengths from model values',
                 self._toggle_auto_params,
                 checked=self.auto_params),
            Separator,
            Item('Load readouts from file', None,
                 'Load monitor readout values from monitor export',
                 self._open_sd_values),
            Item('Load strengths from file', None,
                 'Load magnet strengths from strength export',
                 self._open_float_values),
        ])

    def export_settings(self):
        return {
            'jitter': self.jitter(),
            'shot_interval': self.sd_cache.timeout,
            'auto_sd': self.auto_sd(),
            'auto_params': self.auto_params(),
            'str_file': safe_relpath(self.str_file),
            'sd_file': safe_relpath(self.sd_file),
        }

    def _toggle_jitter(self):
        self.jitter.set(not self.jitter())

    def _toggle_auto_sd(self):
        self.auto_sd.set(not self.auto_sd())
        if self.auto_sd() and self.model():
            self.update_sd_values(self.model())

    def _toggle_auto_params(self):
        self.auto_params.set(not self.auto_params())
        if self.auto_params() and self.model():
            self.update_params(self.model())

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

    _aberration_magnitude = {
        'ax':  1e-4,    # 0.1 mrad
        'ay':  1e-4,
        'dax': 1e-4,
        'day': 1e-4,
        'kl':  5e-3,    # 0.005
    }

    def _aberrate_strengths(self):
        for k in self.params:
            prefix = k.lower().split('_')[0]
            sigma = self._aberration_magnitude.get(prefix)
            if sigma is not None:
                self.params[k] += gauss(0, sigma)

    def set_float_values(self, data):
        self.params = dicti(data)
        self.auto_params.set(False)

    def set_sd_values(self, data):
        self.sd_values = dicti(data)
        self.auto_sd.set(False)

    def on_connected_changed(self, connected):
        if connected:
            self.model.changed.connect(self.on_model_changed)
            self.on_model_changed(self.model())
        else:
            self.model.changed.disconnect(self.on_model_changed)
        if self.menu:
            self.menu.setEnabled(connected)

    def on_model_changed(self, model):
        if model:
            if self.auto_params():
                self.update_params(model)
            if self.auto_sd():
                self.update_sd_values(model)

    def update_params(self, model):
        self.params.clear()
        self.params.update(model.globals)
        self.params.update({
            'A_POSTSTRIP':  1.007281417537080e+00,
            'Q_POSTSTRIP':  1.000000000000000e+00,
            'Z_POSTSTRIP':  1.000000000000000e+00,
            'E_HEBT':       2.034800000000000e+02,
            # copying HEBT settings for testing:
            'E_SOURCE':     2.034800000000000e+02,
            'E_MEBT':       2.034800000000000e+02,
        })

    @_api_meth
    def DisableMessageBoxes(self):
        """Do nothing. There are no message boxes anyway."""
        pass

    @_api_meth
    def GetInterfaceInstance(self):
        """Create a new interface instance."""
        self.vacc = 1
        self.EFIA = (1, 1, 1, 1)
        return 1337

    @_api_meth
    def FreeInterfaceInstance(self):
        """Destroy a previously created interface instance."""
        del self.vacc
        del self.EFIA

    @_api_meth
    def GetDVMStatus(self, status):
        """Get DVM ready status."""
        # The test lib has no advanced status right now.
        return DVMStatus.Ready

    @_api_meth
    def SelectVAcc(self, vaccnum):
        """Set virtual accelerator number."""
        self.vacc = vaccnum

    @_api_meth
    def SelectMEFI(self, vaccnum, energy, focus, intensity, gantry_angle=0):
        """Set MEFI in current VAcc."""
        # The real DLL requires SelectVAcc to be called in advance, so we
        # enforce this constraint here as well:
        assert self.vacc == vaccnum
        self.EFIA = (energy, focus, intensity, gantry_angle)
        return EFI(
            float(energy),
            float(focus),
            float(intensity),
            float(self.params.get('gantry_angle', gantry_angle)))

    @_api_meth
    def GetSelectedVAcc(self):
        """Get currently selected VAcc."""
        return self.vacc

    @_api_meth
    def GetFloatValue(self, name, options=GetOptions.Current):
        """Get a float value from the "database"."""
        return float(self.params.get(name, 0))

    @_api_meth
    def SetFloatValue(self, name, value, options=0):
        """Store a float value to the "database"."""
        self.params[name] = value

    @_api_meth
    def ExecuteChanges(self, options):
        """Compute new measurements based on current model."""
        if self.auto_sd():
            self.update_sd_values(self.model())

    @_api_meth
    def SetNewValueCallback(self, callback):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def GetFloatValueSD(self, name, options=0):
        """Get beam diagnostic value."""
        try:
            storage = self.sd_cache if self.jitter() else self.sd_values
            return storage[name] * 1000
        except KeyError:
            return -9999.0

    def _get_jittered_sd(self, name):
        value = self.sd_values[name]
        prefix = name.lower().split('_')[0]
        if value != -9999:
            mean, stddev = value, 1e-4      # 0.1 mm
            if prefix in ('posx', 'posy'):
                return gauss(mean, stddev)
            if prefix in ('widthx', 'widthy'):
                return gamma(mean**2/stddev**2, stddev**2/mean)
        return value

    def update_sd_values(self, model):
        """Compute new measurements based on current model."""
        model.twiss()
        for elem in model.elements:
            if elem.base_name.endswith('monitor'):
                dx, dy = self.offsets.get(elem.name, (0, 0))
                twiss = model.get_elem_twiss(elem.name)
                values = {
                    'widthx': twiss.envx,
                    'widthy': twiss.envy,
                    'posx': -twiss.x - dx,
                    'posy': twiss.y - dy,
                }
                self.sd_values.update({
                    key + '_' + elem.name: val
                    for key, val in values.items()
                })

    @_api_meth
    def GetLastFloatValueSD(self, name, vaccnum,
                            energy, focus, intensity, gantry_angle=0,
                            options=0):
        """Get beam diagnostic value."""
        # behave exactly like GetFloatValueSD and ignore further parameters
        # for now
        return self.GetFloatValueSD(name, options)

    @_api_meth
    def StartRampDataGeneration(self, vaccnum, energy, focus, intensity):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def GetRampDataValue(self, order_num, event_num, delay,
                         parameter_name, device_name):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def SetIPC_DVM_ID(self, name):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def GetMEFIValue(self):
        """Get current MEFI combination."""
        channels = EFI(*self.EFIA)
        values = EFI(
            float(channels.energy),
            float(channels.focus),
            float(channels.intensity),
            float(self.params.get('gantry_angle', channels.gantry_angle)))
        return (values, channels)


def safe_relpath(path, start=None):
    try:
        return path and os.path.relpath(path, start)
    except ValueError:  # e.g. different drive on windows
        return path
