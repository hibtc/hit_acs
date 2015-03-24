"""
Stub class for BeamOptikDLL.dll ctypes proxy objects as used by
:class:`~hit.online_control.beamoptikdll.BeamOptikDLL`.
"""

import functools
from ctypes import c_char_p

from . import beamoptikdll


def _unbox(param):
    """Unbox a call parameter created by ctypes.byref."""
    return param.value if isinstance(param, c_char_p) else param._obj


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
        unboxed_args = map(_unbox, args)
        if self.logger:
            self.logger.info('{}{}'.format(func.__name__, tuple(unboxed_args)))
        ret = func(self, *unboxed_args)
        if ret is not None:
            done.value = ret

    return wrapper


class BeamOptikDllProxy(object):

    """A fake implementation for a ctypes proxy of the BeamOptikDLL."""

    def __init__(self, data, logger=None):
        """Initialize new library instance with no interface instances."""
        self.data = data
        self.instances = {}
        self.logger = logger
        self.next_iid = 0

    @_api_meth
    def DisableMessageBoxes(self):
        """Do nothing. There are no message boxes anyway."""
        pass

    @_api_meth
    def GetInterfaceInstance(self, iid):
        """Create a new interface instance."""
        iid.value = self.next_iid
        self.instances[iid.value] = {
            'VAcc': None,
            'EFIA': (None, None, None, None),
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
        status.value = beamoptikdll.DVMStatus.Ready

    @_api_meth
    def SelectVAcc(self, iid, vaccnum):
        """Set virtual accelerator number."""
        assert self.instances[iid.value]
        self.instances[iid.value]['VAcc'] = vaccnum.value

    @_api_meth
    def SelectMEFI(self, iid, vaccnum,
                   energy, focus, intensity, gantry_angle,
                   energy_val, focus_val, intensity_val, angle_angle_val):
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
        value.value = self.data['control'][name]

    @_api_meth
    def SetFloatValue(self, iid, name, value, options):
        """Store a float value to the "database"."""
        assert self.instances[iid.value]
        self.data['control'][name] = value.value

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
        value.value = self.data['diagnostic'][name]

    @_api_meth
    def GetLastFloatValueSD(self, iid,
                            name, value, vaccnum, options,
                            energy, focus, intensity, gantry_angle):
        """Get beam diagnostic value."""
        # behave exactly like GetFloatValueSD and ignore further parameters
        # for now
        assert self.instances[iid.value]
        value.value = self.data['diagnostic'][name]

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
                     energy_chn, focus_chn, intensity_chn, gantry_angle_chn,
                     energy_val, focus_val, intensity_val, gantry_angle_val):
        """Get current MEFI combination."""
        e, f, i, a = self.instances[iid.value]['EFIA']
        energy.value = e
        focus.value = f
        intensity.value = i
        gantry_angle.value = a
        energy_val.value = float(energy.value)
        focus_val.value = float(focus.value)
        intensity_val.value = float(intensity.value)
        gantry_angle_val.value = float(gantry_angle.value)
