"""
Stub class for BeamOptikDLL.dll ctypes proxy objects as used by
:class:`~hit_csys.beamoptikdll.BeamOptikDLL`. Primarily used for
offline testing of the basic functionality.
"""

import logging
import functools
import ctypes

from madgui.core.unit import madx_units

from .beamoptikdll import DVMStatus, _decode

import random

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

    def __init__(self, frame):
        """Initialize new library instance with no interface instances."""
        self.params = {}
        self.instances = {}
        self.next_iid = 0
        self.frame = frame
        self.jitter = True

    def on_model_changed(self):
        self.model = self.frame.model
        self.params.clear()
        self.frame.control.write_all()
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
        iid.value = self.next_iid
        self.instances[iid.value] = {
            'VAcc': 1,
            'EFIA': (1, 1, 1, 1),
        }
        self.next_iid += 1

    @_api_meth
    def FreeInterfaceInstance(self, iid):
        """Destroy a previously created interface instance."""
        assert self.instances[iid.value]
        self.instances[iid.value] = None

    @_api_meth
    def GetDVMStatus(self, iid, status):
        """Get DVM ready status."""
        assert self.instances[iid.value]
        # The test lib has no advanced status right now.
        status.value = DVMStatus.Ready

    @_api_meth
    def SelectVAcc(self, iid, vaccnum):
        """Set virtual accelerator number."""
        assert self.instances[iid.value]
        self.instances[iid.value]['VAcc'] = vaccnum.value

    @_api_meth
    def SelectMEFI(self, iid, vaccnum,
                   energy, focus, intensity, gantry_angle,
                   energy_val, focus_val, intensity_val, gantry_angle_val):
        """Set MEFI in current VAcc."""
        # The real DLL requires SelectVAcc to be called in advance, so we
        # enforce this constraint here as well:
        assert self.instances[iid.value]['VAcc'] == vaccnum.value
        self.instances[iid.value]['EFIA'] = (
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
        vaccnum.value = self.instances[iid.value]['VAcc']

    @_api_meth
    def GetFloatValue(self, iid, name, value, options):
        """Get a float value from the "database"."""
        assert self.instances[iid.value]
        value.value = float(self.params.get(name, 0))

    @_api_meth
    def SetFloatValue(self, iid, name, value, options):
        """Store a float value to the "database"."""
        assert self.instances[iid.value]
        self.params[name] = value.value

    @_api_meth
    def ExecuteChanges(self, iid, options):
        """Do nothing: our "database" is currently non-transactional."""
        assert self.instances[iid.value]

    @_api_meth
    def SetNewValueCallback(self, iid, callback):
        """Not implemented."""
        raise NotImplementedError

    @_api_meth
    def GetFloatValueSD(self, iid, name, value, options):
        """Get beam diagnostic value."""
        assert self.instances[iid.value]

        par_name, el_name = name.lower().split('_', 1)
        index = self.model.elements.index(el_name)
        index = self.model.indices[index].stop

        cols = {
            'widthx': 'envx',
            'widthy': 'envy',
            'posx': 'posx',
            'posy': 'posy',
        }
        col = cols[par_name]
        twiss = self.model.get_twiss_column(col)
        v = madx_units.strip_unit(col, twiss[index])
        if par_name == 'posx':
            v = -v
        v -= self.frame.control._plugin._offsets.get(el_name, (0, 0))[
            par_name == 'posy']
        if self.jitter:
            if par_name in ('widthx', 'widthy'):
                v *= random.uniform(0.95, 1.1)
            elif par_name in ('posx', 'posy'):
                v += random.uniform(-0.0005, 0.0005)

        value.value = v * 1000

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
        e, f, i, a = self.instances[iid.value]['EFIA']
        energy_chn.value = e
        focus_chn.value = f
        intensity_chn.value = i
        gantry_angle_chn.value = a
        energy_val.value = float(energy_chn.value)
        focus_val.value = float(focus_chn.value)
        intensity_val.value = float(intensity_chn.value)
        gantry_angle_val.value = float(gantry_angle_chn.value)
