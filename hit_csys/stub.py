"""
Stub class for BeamOptikDLL.dll ctypes proxy objects as used by
:class:`~hit_csys.beamoptikdll.BeamOptikDLL`. Primarily used for
offline testing of the basic functionality.
"""

import logging
import functools
import ctypes
import random

from pydicti import dicti

from .beamoptikdll import DVMStatus, _decode


c_str = ctypes.c_char_p, ctypes.c_wchar_p


__all__ = [
    'BeamOptikDllProxy',
]


def _unbox(param):
    """Unbox a call parameter created by ctypes.byref."""
    return _decode(param.value) if isinstance(param, c_str) else param._obj


def _api_meth(func):

    """
    Decorator for methods conforming to the BeamOptikDLL API.

    Unboxes parameter references and sets the ``done`` from the function's
    return value.
    """

    @functools.wraps(func)
    def wrapper(self, *args):
        idone = 6 if func.__name__ == 'SelectMEFI' else len(args) - 1
        done = _unbox(args[idone])
        args = args[:idone] + args[idone+1:]
        done.value = 0
        unboxed_args = tuple(map(_unbox, args))
        logging.debug('{}{}'.format(func.__name__, unboxed_args))
        ret = func(self, *unboxed_args)
        if ret is not None:
            done.value = ret

    return wrapper


class BeamOptikDllProxy(object):

    """A fake implementation for a ctypes proxy of the BeamOptikDLL."""

    # TODO: Support read-only/write-only parameters
    # TODO: Prevent writing unknown parameters by default

    def __init__(self, model=None, offsets=None):
        """Initialize new library instance with no interface instances."""
        self.params = dicti()
        self.sd_values = dicti()
        self.model = model
        self.offsets = {} if offsets is None else offsets
        self.jitter = True
        self.auto_params = True
        self.auto_sd = True

    def load_float_values(self, filename):
        from madgui.core.model import read_strengths
        self.set_float_values(read_strengths(filename))

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
    def GetInterfaceInstance(self, iid):
        """Create a new interface instance."""
        iid.value = 1337
        self.vacc = 1
        self.EFIA = (1, 1, 1, 1)

    @_api_meth
    def FreeInterfaceInstance(self, iid):
        """Destroy a previously created interface instance."""
        del self.vacc
        del self.EFIA

    @_api_meth
    def GetDVMStatus(self, iid, status):
        """Get DVM ready status."""
        # The test lib has no advanced status right now.
        status.value = DVMStatus.Ready

    @_api_meth
    def SelectVAcc(self, iid, vaccnum):
        """Set virtual accelerator number."""
        self.vacc = vaccnum.value

    @_api_meth
    def SelectMEFI(self, iid, vaccnum,
                   energy, focus, intensity, gantry_angle,
                   energy_val, focus_val, intensity_val, gantry_angle_val):
        """Set MEFI in current VAcc."""
        # The real DLL requires SelectVAcc to be called in advance, so we
        # enforce this constraint here as well:
        assert self.vacc == vaccnum.value
        self.EFIA = (
            energy.value,
            focus.value,
            intensity.value,
            gantry_angle.value,
        )
        energy_val.value = float(energy.value)
        focus_val.value = float(focus.value)
        intensity_val.value = float(intensity.value)
        gantry_angle_val.value = float(gantry_angle.value)

    @_api_meth
    def GetSelectedVAcc(self, iid, vaccnum):
        """Get currently selected VAcc."""
        vaccnum.value = self.vacc

    @_api_meth
    def GetFloatValue(self, iid, name, value, options):
        """Get a float value from the "database"."""
        value.value = float(self.params.get(name, 0))

    @_api_meth
    def SetFloatValue(self, iid, name, value, options):
        """Store a float value to the "database"."""
        self.params[name] = value.value

    @_api_meth
    def ExecuteChanges(self, iid, options):
        """Compute new measurements based on current model."""
        if self.auto_sd:
            self.update_sd_values(self.model())

    @_api_meth
    def SetNewValueCallback(self, iid, callback):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def GetFloatValueSD(self, iid, name, value, options):
        """Get beam diagnostic value."""
        try:
            value.value = self.sd_values[name] * 1000
        except KeyError:
            value.value = -9999.0

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
                if self.jitter:
                    values['widthx'] *= random.uniform(0.95, 1.1)
                    values['widthy'] *= random.uniform(0.95, 1.1)
                    values['posx'] += random.uniform(-0.0005, 0.0005)
                    values['posy'] += random.uniform(-0.0005, 0.0005)
                self.sd_values.update({
                    key + '_' + elem.name: val
                    for key, val in values.items()
                })

    @_api_meth
    def GetLastFloatValueSD(self, iid,
                            name, value, vaccnum, options,
                            energy, focus, intensity, gantry_angle):
        """Get beam diagnostic value."""
        # behave exactly like GetFloatValueSD and ignore further parameters
        # for now
        self.GetFloatValueSD.__wrapped__(self, iid, name, value, options)

    @_api_meth
    def StartRampDataGeneration(self, iid,
                                vaccnum, energy, focus, intensity, order_num):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def GetRampDataValue(self, iid, order_num, event_num, delay,
                         parameter_name, device_name, value):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def SetIPC_DVM_ID(self, iid, name):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def GetMEFIValue(self, iid,
                     energy_val, focus_val, intensity_val, gantry_angle_val,
                     energy_chn, focus_chn, intensity_chn, gantry_angle_chn):
        """Get current MEFI combination."""
        e, f, i, a = self.EFIA
        energy_chn.value = e
        focus_chn.value = f
        intensity_chn.value = i
        gantry_angle_chn.value = a
        energy_val.value = float(energy_chn.value)
        focus_val.value = float(focus_chn.value)
        intensity_val.value = float(intensity_chn.value)
        gantry_angle_val.value = float(gantry_angle_chn.value)
