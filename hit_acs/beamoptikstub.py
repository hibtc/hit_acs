"""
Fake implementation of BeamOptikDLL wrapper. Emulates the API of
:class:`~hit_acs.beamoptikdll.BeamOptikDLL`. Primarily used for
offline testing of the basic functionality.
"""

import logging
import functools
from random import gauss, gammavariate as gamma

from pydicti import dicti

from .beamoptikdll import DVMStatus, GetOptions, ExecOptions, GetSDOptions, EFI
from .util import TimeoutCache


__all__ = [
    'BeamOptikStub',
]


def _api_meth(func):
    """Decorator for tracing calls to BeamOptikDLL API methods."""
    @functools.wraps(func)
    def wrapper(self, *args):
        if func.__name__ != 'GetFloatValueSD':
            logging.debug('{}{}'.format(func.__name__, args))
        return func(self, *args)
    return wrapper


class BeamOptikStub(object):

    """
    A fake implementation of the BeamOptikDLL python wrapper for offline
    testing. It does not use the actual DLL but is just a thin simulation
    layer that can partially mimick actual behaviour and provide BPM readings
    based on a provided MAD-X model.
    """

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
        self.jitter = settings.get('jitter', True)
        self.auto_sd = settings.get('auto_sd', True)
        self._variant = variant

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
        self.ExecuteChanges()

    def set_sd_values(self, data):
        self.sd_values = dicti(data)
        self.auto_sd = False

    def set_model(self, model):
        self.model = model
        if model:
            self.set_float_values(model.globals)
            self.update_sd_values()

    def set_float_values(self, data):
        self.params.clear()
        self.params.update({
            'A_POSTSTRIP':  1.007281417537080e+00,
            'Q_POSTSTRIP':  1.000000000000000e+00,
            'Z_POSTSTRIP':  1.000000000000000e+00,
            'E_HEBT':       2.034800000000000e+02,
            # copying HEBT settings for testing:
            'E_SOURCE':     2.034800000000000e+02,
            'E_MEBT':       2.034800000000000e+02,
        })
        self.params.update(data)
        self.ExecuteChanges()

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
    def ExecuteChanges(self, options=ExecOptions.CalcDif):
        """Compute new measurements based on current model."""
        if self.model:
            self.model.update_globals(self.params)
            self.update_sd_values()

    @_api_meth
    def SetNewValueCallback(self, callback):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def GetFloatValueSD(self, name, options=GetSDOptions.Current):
        """Get beam diagnostic value."""
        try:
            storage = self.sd_cache if self.jitter else self.sd_values
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

    def update_sd_values(self):
        """Compute new measurements based on current model."""
        model = self.model
        if not model or not self.auto_sd:
            return
        model.twiss()
        for elem in self._monitors():
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
                            options=GetSDOptions.Current):
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

    def _monitors(self):
        return [elem for elem in self.model.elements
                if elem.base_name.endswith('monitor')]
