"""
Low level wrapper for the HIT accelerator control software.

Wraps the API of the 'BeamOptikDLL.dll' library to a more pythonic
interface.

"""
from collections import namedtuple
from ctypes import c_double as Double, c_char_p as Str, c_int as Int
import ctypes

EFI = namedtuple('EFI', ['energy', 'focus', 'intensity', 'gantry_angle'])

def enum(*sequential):
    class Enum(int):
        def __str__(self):
            return sequential[int(self)]
        def __repr__(self):
            return '%s(%s=%d)' % (self.__class__.__name__, self, int(self))
    for i,v in enumerate(sequential):
        setattr(Enum, v, i)
    return Enum

DVMStatus = enum('Stop', 'Idle', 'Init', 'Ready', 'Busy', 'Finish', 'Error')
GetOptions = enum('Current', 'Saved')
ExecOptions = enum('CalcAll', 'CalcDif', 'SimplyStore')
GetSDOptions = enum('Current', 'Database', 'Test')


class BeamOptikDLL(object):
    """
    Thin wrapper around the BeamOptikDLL API.

    It abstracts the ctypes data types and automates InterfaceId as well as
    iDone. Nothing else.

    """
    try:
        lib = ctypes.windll.LoadLibrary('BeamOptikDLL.dll')
    except AttributeError:
        # On linux (for testing)
        lib = None

    #----------------------------------------
    # internal methods
    #----------------------------------------

    error_messages = [
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

    @classmethod
    def check_return(cls, done):
        """
        Check DLL-API exit code for errors and raise exception.

        :param int done: exit code of an DLL function
        :raises RuntimeError: if the exit code is a known error code != 0
        :raises ValueError: if the exit code is unknown

        """
        if 0 < done and done < len(cls.error_messages):
            raise RuntimeError(cls.error_messages[done])
        elif done != 0:
            raise ValueError("Unknown error: %i" % done)

    @classmethod
    def call(cls, function, *params):
        """
        Call the specified DLL function.

        :param str function: name of the function to call
        :param params: ctype function parameters except for piInstance and piDone.
        :raises RuntimeError: if the exit code indicates any error

        For internal use only!

        """
        done = Int()
        params = list(params)
        if function == 'SelectMEFI':
            params.insert(6, done)
        else:
            params.append(done)
        def param(p):
            return p if isinstance(p, Str) else ctypes.byref(p)
        getattr(cls.lib, function)(*map(param, params))
        cls.check_return(done.value)

    #----------------------------------------
    # class level API
    #----------------------------------------

    @classmethod
    def DisableMessageBoxes(cls):
        """
        Prevent creation of certain message boxes.

        :raises RuntimeError: if the exit code indicates any error

        """
        cls.call('DisableMessageBoxes')

    @classmethod
    def GetInterfaceInstance(cls):
        """
        Create a BeamOptikDLL instance (connects DB and initialize DLL).

        :return: new instance id
        :rtype: int
        :raises RuntimeError: if the exit code indicates any error

        """
        iid = Int()
        cls.call('GetInterfaceInstance', iid)
        return cls(iid)

    #----------------------------------------
    # object API
    #----------------------------------------

    def __init__(self, iid):
        """
        The constructur should not be invoked directly (except for testing).

        Rather use the BeamOptikDLL.GetInterfaceInstance() classmethod.

        :param ctypes.Int iid: InterfaceId

        """
        self.iid = iid

    def FreeInterfaceInstance(self):
        """
        Free resources.

        :raises RuntimeError: if the exit code indicates any error

        """
        self.call('FreeInterfaceInstance', self.iid)
        self.iid = None

    def GetDVMStatus(self):
        """
        Get current status of selected virtual accelerator.

        :return: DVM status
        :rtype: DVMStatus
        :raises RuntimeError: if the exit code indicates any error

        """
        status = Int()
        self.call('GetDVMStatus', self.iid, status)
        return DVMStatus(status.value)

    def SelectVAcc(self, vaccnum):
        """
        Select the virtual accelerator.

        :param int vaccnum: virtual accelerator number (0-255)
        :raises RuntimeError: if the exit code indicates any error

        """
        self.call('SelectVAcc', self.iid, Int(vaccnum))

    def SelectMEFI(self, vaccnum, energy, focus, intensity, gantry_angle=0):
        """
        Select EFI combination for the currently selected VAcc.

        :param int vaccnum: virtual accelerator number (0-255)
        :param int energy: energy channel (1-255)
        :param int focus: focus channel (1-6)
        :param int intensity: intensity channel (1-15)
        :param int gantry_angle: gantry angle index (1-36)
        :return: physical EFI values
        :rtype: EFI
        :raises RuntimeError: if the exit code indicates any error

        CAUTION: SelectVAcc must be called before invoking this function!

        """
        values = [Double(), Double(), Double(), Double()]
        self.call('SelectMEFI', self.iid, Int(vaccnum),
                  Int(energy), Int(focus), Int(intensity), Int(gantry_angle),
                  *values)
        return EFI(*[v.value for v in values])

    def GetSelectedVAcc(self):
        """
        Get selected virtual accelerator.

        :return: virtual accelerator number
        :rtype: int
        :raises RuntimeError: if the exit code indicates any error

        """
        vaccnum = Int()
        self.call('GetSelectedVAcc', self.iid, vaccnum)
        return vaccnum.value

    def GetFloatValue(self, name, options=GetOptions.Current):
        """
        Get parameter value.

        :param str name: parameter name
        :param GetOptions options: options
        :return: parameter value
        :rtype: float
        :raises RuntimeError: if the exit code indicates any error

        """
        value = Double()
        self.call('GetFloatValue', self.iid, Str(name), value, Int(options))
        return value.value

    def SetFloatValue(self, name, value, options=0):
        """
        Set parameter value.

        :param str name: parameter name
        :param float value: parameter value
        :param options: not used currently
        :raises RuntimeError: if the exit code indicates any error

        Changes take effect after calling :func:`ExecuteChanges`.

        """
        self.call('SetFloatValue', self.iid, Str(name), Double(value), Int(options))

    def ExecuteChanges(self, options):
        """
        Apply parameter changes.

        :param ExecOptions options: what to do exactly
        :raises RuntimeError: if the exit code indicates any error

        """
        self.call('ExecuteChanges', self.iid, Int(options))

    def SetNewValueCallback(self, callback):
        """Call SetNewValueCallback(). Not implemented!"""
        # TODO: docs do not specify when this is actually called
        # TODO: howto create a python callback? Use Cython?
        raise NotImplementedError

    def GetFloatValueSD(self, name, options=0):
        """
        Get current beam measurement at specific element.

        :param str name: parameter name (<observable>_<element name>)
        :param GetSDOptions options: options
        :return: index of observable
        :rtype: int?
        :raises RuntimeError: if the exit code indicates any error

        """
        # TODO: either docs are still bad or this function is weird
        value = Double()
        self.call('GetFloatValueSD', self.iid, Str(name), value, Int(options))
        return value.value

    def GetLastFloatValueSD(self, name, options=0):
        """
        Get previous beam measurement at specific element.

        :param str name: parameter name (<observable>_<element name>)
        :param GetSDOptions options: options
        :return: index of observable
        :rtype: int?
        :raises RuntimeError: if the exit code indicates any error

        """
        # TODO: either docs are still bad or this function is weird
        value = Double()
        self.call('GetLastFloatValueSD', self.iid, Str(name), value, Int(options))
        return value.value

    def StartRampDataGeneration(self, name):
        """Call StartRampDataGeneration(). Not implemented!"""
        raise NotImplementedError # TODO

    def GetRampDataValue(self, name):
        """Call GetRampDataValue(). Not implemented!"""
        raise NotImplementedError # TODO

    def SetIPC_DVM_ID(self, name):
        """Call SetIPC_DVM_ID(). Not implemented!"""
        raise NotImplementedError # TODO

    def GetMEFIValue(self):
        """
        Retrieve EFI values for current selection.

        :return: physical EFI values, EFI channel numbers
        :rtype: tuple(EFI, EFI)
        :raises RuntimeError: if the exit code indicates any error

        """
        values = [Double(), Double(), Double(), Double()]
        channels = [Int(), Int(), Int(), Int()]
        self.call('GetMEFIValue', self.iid, *(values + channels))
        return (EFI(*[v.value for v in values]),
                EFI(*[c.value for c in channels]))


