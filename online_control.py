"""
Beam-optic control component.

The main component is the class `OnlineControl`. This class is responsible
for managing the interaction between model and online control.

There is also `load_shared_library` to load a runtime library (.dll/.so).

Finally, `OnlineElements` is used for dictionary-like access of online
element parameters.

"""
import ctypes
from ctypes import c_double as Double, c_char_p as Str, c_int as Int

from collections import MutableMapping


def load_shared_library(shared_library_name = 'BeamOptikDLL'):
    """
    Load the shared library.

    Currently you must not pass the full file name. It will be autocompleted
    at runtime.

    """
    try:
        # load a stdcall library (winapi calling convention)
        loader = ctypes.windll.LoadLibrary
        suffix = '.dll'
    except AttributeError:
        # load a cdecl library (c++ standard calling convention)
        loader = ctypes.cdll.LoadLibrary
        suffix = '.so'
    try:
        return loader(shared_library_name + suffix)
    except OSError:
        # file not found
        return None

class BeamOptikDLL(object):
    """
    Thin wrapper around the BeamOptikDLL API.

    It abstracts the ctypes data types and automates InterfaceId as well as
    iDone. Nothing else.

    """
    def __init__(self, library):
        self.lib = library
        self.iid = None

    def _check_return(self, done):
        if done == 0:
            return
        errors = [
            None,
            "Invalid Interface ID.",
            "Parameter not found in internal DVM list.",
            "GetValue failed.",
            "SetValue failed.",
            "Unknown option.",
            "Memory error.",
            "General runtime error.",
            "Ramp event not supported.",
            "Ramp data not available.",
            "Invalid offset for ramp function."]
        if done < len(errors):
            raise RuntimeError(errors[done])
        else:
            raise RuntimeError("Unknown error: %i" % done)

    def __call__(self, function, *params):
        """
        Call the specified method.

        This is a low-level function that should only be used internally.

        The params must neither include piInstance nor piDone. If an error
        is returned from the library a RuntimeError will be raised.

        """
        done = Int()
        params = list(params)
        if function != 'DisableMessageBoxes':
            params.insert(0, self.iid)
        if function == 'SelectMEFI':
            params.insert(5, done)
        else:
            params.append(done)

        self.lib[function](*(ctypes.byref(param) for param in params))
        self._check_return(done.value)

    def GetInterfaceInstance(self):
        """Call GetInterfaceInstance(). Returns instance_id."""
        if self.iid.value is None:
            self.iid = Int()
            try:
                self('GetInterfaceInstance')
            except RuntimeError:
                self.iid = None
                raise
        return self.iid.value

    def FreeInterfaceInstance(self):
        """Call FreeInterfaceInstance()."""
        if self.iid is not None:
            self('FreeInterfaceInstance')
            self.iid = None

    def DisableMessageBoxes(self):
        """Call DisableMessageBoxes()."""
        self('DisableMessageBoxes')

    def GetDVMStatus(self):
        """Call GetDVMStatus(). Returns status."""
        status = Int()
        self('GetDVMStatus', status)
        return status.value

    def SelectVAcc(self, vaccnum):
        """Call SelectVAcc()."""
        self('SelectVAcc', Int(vaccnum))

    MEFIValue = namedtuple('MEFIValue', [
        'EnergyChannel', 'FocusChannel',
        'IntensityChannel', 'GantryAngleChannel',
        'EnergyValue', 'FocusValue',
        'IntensityValue', 'GantryAngleValue'])

    def SelectMEFI(self, vaccnum,
            energy_channel, focus_channel,
            intensity_channel, gantry_angle_channel):
        """Call SelectMEFI()."""
        energy_value = Double()
        focus_value = Double(),
        intensity_value = Double()
        gantry_angle_value = Double()
        self('SelectMEFI', vaccnum,
             energy_channel, focus_channel,
             intensity_channel, gantry_angle_channel,
             energy_value, focus_value,
             intensity_value, gantry_angle_value)
        return self.MEFIValue(
            EnergyChannel=energy_channel,
            FocusChannel=focus_channel,
            IntensityChannel=intensity_channel,
            GantryAngleChannel=gantry_angle_channel,
            EnergyValue=energy_value.value,
            FocusValue=focus_value.value,
            IntensityValue=intensity_value.value,
            GantryAngleValue=gantry_angle_value.value)

    def GetSelectedVAcc(self):
        """Call GetSelectedVAcc(). Returns vaccnum."""
        vaccnum = Int()
        self('GetSelectedVAcc', vaccnum)
        return vaccnum.value

    def GetFloatValue(self, name):
        """Call GetFloatValue(). Returns value."""
        # TODO: doc does not describe what options are possible and
        # whether options is input or output
        options = Int()
        value = Double()
        self('GetFloatValue', Str(name), value, options)
        return value.value

    def SetFloatValue(self, name, value):
        """Call SetFloatValue()."""
        # TODO: doc does not describe what options are possible and
        # whether options is input or output
        options = Int()
        self('SetFloatValue', Str(name), Double(value), options)

    def ExecuteChanges(self, options):
        """Call ExecuteChanges()."""
        self('ExecuteChanges', Int(options))

    def SetNewValueCallback(self, callback):
        """Call SetNewValueCallback(). Not implemented!"""
        # TODO: docs do not specify when this is actually called
        # TODO: howto create a python callback? Use Cython?
        raise NotImplementedError

    def GetFloatValueSD(self, name):
        """Call GetFloatValueSD(). Retuns value."""
        # TODO: doc does not specify valid values for options
        options = Int()
        value = Double()
        self('GetFloatValueSD', Str(name), value, options)
        return value.value

    def GetLastFloatValueSD(self, name):
        """Call GetLastFloatValueSD(). Retuns value."""
        # TODO: doc does not specify valid values for options
        options = Int()
        value = Double()
        self('GetLastFloatValueSD', Str(name), value, options)
        return value.value

    def StartRampDataGeneration(self, name):
        """Call StartRampDataGeneration(). Not implemented!"""
        # TODO: doc cannot be more unclear.
        raise NotImplementedError

    def GetRampDataValue(self, name):
        """Call GetRampDataValue(). Not implemented!"""
        # TODO: doc cannot be more unclear.
        raise NotImplementedError

    def SetIPC_DVM_ID(self, name):
        """Call SetIPC_DVM_ID(). Not implemented!"""
        # TODO: doc cannot be more unclear.
        raise NotImplementedError

    def GetMEFIValue(self)
        """Call SelectMEFI(). Returns double(E,F,I,Angle), channel(E,F,I,Angle)."""
        # TODO: why are channels here after values as opposed to SelectMEFI
        # TODO: why is here no vaccnum argument
        # TODO: is all output?
        energy_value, = Double()
        focus_value = Dobule()
        intensity_value = Double()
        gantry_angle_value = Double()
        energy_channel = Int()
        focus_channel = Int()
        intensity_channel = Int()
        gantry_angle_channel = Int()
        self('SelectMEFI',
             energy_value, focus_value,
             intensity_value, gantry_angle_value,
             energy_channel, focus_channel,
             intensity_channel, gantry_angle_channel)
        return self.MEFIValue(
            EnergyChannel=energy_channel.value,
            FocusChannel=focus_channel.value,
            IntensityChannel=intensity_channel.value,
            GantryAngleChannel=gantry_angle_channel.value,
            EnergyValue=energy_value.value,
            FocusValue=focus_value.value,
            IntensityValue=intensity_value.value,
            GantryAngleValue=gantry_angle_value)


class OnlineElements(MutableMapping):
    """
    Utility for accessing optics parameters online.
    """
    def __init__(self, library):
        """Initialize instance."""
        self.lib = library

    def __getattr__(self, name):
        """Get the online parameter. Alias for __getitem__."""
        return self.getitem(name)

    def __setattr__(self, name, value):
        """Set the online parameter. Alias for __setitem__."""
        return self.setitem(name, value)

    def __getitem__(self, name):
        """
        Get the online parameter.

        TODO

        """
        self.lib.GetFloatValue(name)

    def __setitem__(self, name, value):
        """
        Set the online parameter.

        TODO

        """
        self.lib.SetFloatValue(name, value)

    def __iter__(self):
        """
        Iterate all elements.
        """
        pass

    def __len__(self):
        """Number of elements."""
        pass

    # `MutableMapping` mixins:
    get          = MutableMapping.get
    __contains__ = MutableMapping.__contains__
    keys         = MutableMapping.keys
    items        = MutableMapping.items
    values       = MutableMapping.values
    clear        = MutableMapping.clear
    update       = MutableMapping.update
    setdefault   = MutableMapping.setdefault

    # Unsupported operations
    def __delitem__(self, name):
        """Invalid operation!"""
        raise RuntimeError("Go downstairs and remove it yourself!")

    pop          = __delitem__
    popitem      = __delitem__



class OnlineControl(object):
    """
    Beam-optic control component.

    This component encapsulates the interface to the online functionality of
    madgui. Specifically at this point it talks to the shared library
    'BeamOptikDLL.dll'.

    """
    lib = None

    def __init__(self, model, shared_library=None):
        """Initialize the online control."""
        self.startup(shared_library)

    def startup(self, library):
        """Run the library's initialization routines and store the object."""
        self.uninit()
        if shared_library:
            # TODO...
            self.lib = shared_library
            self.instance_id = self.lib.GetInterfaceInstance(0, 0)
            self.elements = OnlineElements(shared_library)

    @property
    def mefi(self):
        """Access to the MEFI parameters."""
        pass

    @mefi.setter
    def mefi(self, value):
        """Access to the MEFI parameters."""
        pass

    def cleanup():
        """
        Run the library's cleanup routines and remove the object.

        Return value is the library object. This can be used to perform
        further cleanup tasks.

        """
        if self.lib:
            self.lib, lib = None, self.lib
            self.elements = None
            # TODO...
            return lib
        return None

    def changed_elements(self):
        """
        Iterate over all elements with inconsistent model/online parameters.
        """
        for el in self.elements:
            # TODO...
            pass

    def update_model(self):
        """Update the model to fit the online parameters."""
        pass

    def update_online(self):
        """Update all online parameters from the model values."""
        pass

