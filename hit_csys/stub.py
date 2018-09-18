"""
Fake implementation of BeamOptikDLL wrapper. Emulates the API of
:class:`~hit_csys.beamoptikdll.BeamOptikDLL`. Primarily used for
offline testing of the basic functionality.
"""

import logging
import functools
import random

from pydicti import dicti

from .beamoptikdll import DVMStatus, GetOptions, EFI
from .util import TimeoutCache


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

    def __init__(self, model=None, offsets=None, variant='HIT'):
        """Initialize new library instance with no interface instances."""
        self.params = dicti()
        self.sd_values = dicti()
        self.sd_cache = TimeoutCache(self._get_jittered_sd)
        self.model = model
        self.offsets = {} if offsets is None else offsets
        self.jitter = True
        self.auto_params = True
        self.auto_sd = True
        self._variant = variant

    def load_float_values(self, filename):
        from madgui.util.export import read_str_file
        self.set_float_values(read_str_file(filename))

    def load_sd_values(self, filename):
        import yaml
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

    def set_float_values(self, data):
        self.params = dicti(data)
        self.auto_params = False

    def set_sd_values(self, data):
        self.sd_values = dicti(data)
        self.auto_sd = False

    def on_connected_changed(self, connected):
        if connected:
            self.model.changed.connect(self.on_model_changed)
            self.on_model_changed(self.model())
        else:
            self.model.changed.disconnect(self.on_model_changed)

    def on_model_changed(self, model):
        if model:
            if self.auto_params:
                self.update_params(model)
            if self.auto_sd:
                self.update_sd_values(model)

    def update_params(self, model):
        self.params.clear()
        self.params.update(model.globals)
        if self.jitter:
            for k in self.params:
                self.params[k] *= random.uniform(0.95, 1.1)
        self.params.update(dict(
            A_POSTSTRIP = 1.007281417537080e+00,
            Q_POSTSTRIP = 1.000000000000000e+00,
            Z_POSTSTRIP = 1.000000000000000e+00,
            E_HEBT      = 2.034800000000000e+02,
            # copying HEBT settings for testing:
            E_SOURCE    = 2.034800000000000e+02,
            E_MEBT      = 2.034800000000000e+02,
        ))

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
        if self.auto_sd:
            self.update_sd_values(self.model())

    @_api_meth
    def SetNewValueCallback(self, callback):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def GetFloatValueSD(self, name, options=0):
        """Get beam diagnostic value."""
        try:
            storage = self.sd_cache if self.jitter else self.sd_values
            return storage[name] * 1000
        except KeyError:
            return -9999.0

    def _get_jittered_sd(self, name):
        value = self.sd_values[name]
        if value == -9999:
            return value
        prefix = name.lower().split('_')[0]
        jitter = random.gauss(0, 1e-4)
        if prefix in ('widthx', 'widthy') and value > 0:
            while value + jitter < 0:
                jitter = random.gauss(0, 1e-4)
        return value + jitter

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
