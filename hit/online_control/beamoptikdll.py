"""
Low level wrapper for the HIT accelerator control software.

Wraps the API of the 'BeamOptikDLL.dll' library to a more pythonic
interface.

"""
from collections import namedtuple
from ctypes import windll, c_double as Double, c_char_p as Str, c_int as Int

EFI = namedtuple('EFI', ['energy', 'focus', 'intensity', 'gantry_angle'])

def enum(*sequential):
    class Enum(int):
        def __str__(self):
            return sequential[int(self)]
        def __repr__(self):
            return '%s(%s=%d)' % (self.__class__.__name, self, int(self))
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
    def __init__(self, library):
        self.lib = library
        self.iid = None

    #----------------------------------------
    # internal methods
    #----------------------------------------

    def _check_return(self, done):
        """
        Check DLL-API exit code for errors and raise exception.

        :param int done: exit code of an DLL function
        :raises RuntimeError: if ``done != 0``

        For internal use only!

        """
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
        Call the specified DLL function.

        :param str function: name of the function to call
        :param params: ctype function parameters except for piInstance and piDone.
        :raises RuntimeError: if the exit code indicates any error

        For internal use only!

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

    #----------------------------------------
    # public API
    #----------------------------------------

    def GetInterfaceInstance(self):
        """
        Connect to database and initialize DLL.

        :return: new instance id
        :rtype: int
        :raises RuntimeError: if the exit code indicates any error

        """
        self.iid = Int()
        try:
            self('GetInterfaceInstance')
        except RuntimeError:
            self.iid = None
            raise
        return self.iid.value

    def FreeInterfaceInstance(self):
        """
        Free resources.

        :raises RuntimeError: if the exit code indicates any error

        """
        self('FreeInterfaceInstance')
        self.iid = None

    def DisableMessageBoxes(self):
        """
        Prevent creation of certain message boxes.

        :raises RuntimeError: if the exit code indicates any error

        """
        self('DisableMessageBoxes')

    def GetDVMStatus(self):
        """
        Get current status of selected virtual accelerator.

        :return: DVM status
        :rtype: DVMStatus
        :raises RuntimeError: if the exit code indicates any error

        """
        status = Int()
        self('GetDVMStatus', status)
        return DVMStatus(status.value)

    def SelectVAcc(self, vaccnum):
        """
        Select the virtual accelerator.

        :param int vaccnum: virtual accelerator number (0-255)
        :raises RuntimeError: if the exit code indicates any error

        """
        self('SelectVAcc', Int(vaccnum))

    def SelectMEFI(self, vaccnum, channels):
        """
        Select MEFI combination.

        :param int vaccnum: virtual accelerator number (0-255)
        :param EFI channels: EFI channel numbers
        :return: physical EFI values
        :rtype: EFI
        :raises RuntimeError: if the exit code indicates any error

        """
        channels = [Int(c) for c in channels]
        values = [Double(), Double(), Double(), Double()]
        self('SelectMEFI', vaccnum, *(channels + values))
        return EFI(*[v.value for v in values])

    def GetSelectedVAcc(self):
        """
        Get selected virtual accelerator.

        :return: virtual accelerator number
        :rtype: int
        :raises RuntimeError: if the exit code indicates any error

        """
        vaccnum = Int()
        self('GetSelectedVAcc', vaccnum)
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
        self('GetFloatValue', Str(name), value, Int(options))
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
        self('SetFloatValue', Str(name), Double(value), Int(options))

    def ExecuteChanges(self, options):
        """
        Apply parameter changes.

        :param ExecOptions options: what to do exactly
        :raises RuntimeError: if the exit code indicates any error

        """
        self('ExecuteChanges', Int(options))

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
        self('GetFloatValueSD', Str(name), value, Int(options))
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
        self('GetLastFloatValueSD', Str(name), value, Int(options))
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

    def GetMEFIValue(self)
        """
        Retrieve EFI values for current selection.

        :return: physical EFI values, EFI channel numbers
        :rtype: tuple(EFI, EFI)
        :raises RuntimeError: if the exit code indicates any error

        """
        values = EFI(Double(), Double(), Double(), Double())
        channels = EFI(Int(), Int(), Int(), Int())
        self('SelectMEFI', *(list(values) + list(channels)))
        return (EFI(*[v.value for v in values]),
                EFI(*[c.value for c in channels]))

