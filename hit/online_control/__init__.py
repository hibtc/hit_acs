"""
Beam-optic control component.

The main component is the class `OnlineControl`. This class is responsible
for managing the interaction between model and online control.

Finally, `OnlineElements` is used for dictionary-like access of online
element parameters.

"""
from collections import MutableMapping

from .beamoptikdll import BeamOptikDLL

class OnlineElements(MutableMapping):
    """
    Utility for accessing optics parameters online.
    """
    def __init__(self, library):
        """Initialize instance."""
        self.lib = library

    def __getitem__(self, name):
        """
        Get the online parameter.

        :param str name: parameter name
        :return: parameter value
        :rtype: float
        :raises RuntimeError: if the exit code indicates any error

        """
        return self.lib.GetFloatValue(name)

    def __setitem__(self, name, value):
        """
        Set the online parameter.

        :param str name: parameter name
        :param float value: new parameter value
        :raises RuntimeError: if the exit code indicates any error

        """
        self.lib.SetFloatValue(name, value)

    def __iter__(self):
        """Iterate all elements."""
        raise NotImplementedError # TODO

    def __len__(self):
        """Number of elements."""
        raise NotImplementedError # TODO

    # `MutableMapping` mixins:
    get          = MutableMapping.get
    __contains__ = MutableMapping.__contains__
    keys         = MutableMapping.keys
    items        = MutableMapping.items
    values       = MutableMapping.values
    clear        = MutableMapping.clear
    update       = MutableMapping.update
    setdefault   = MutableMapping.setdefault

    # Convenience aliases
    __getattr__ = __getitem__
    __setattr__ = __setitem__

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

    def __init__(self, model, lib=None):
        """Initialize the online control."""
        self.startup(lib)

    @classmethod
    def create(cls, model):
        """
        Load the shared library and return an OnlineControl handle to it.

        If the library is not found an OSError is raised. On linux an
        AttributeError is raised.

        """
        return cls(model, BeamOptikDLL.GetInterfaceInstance())

    def startup(self, library):
        """Run the library's initialization routines and store the object."""
        self.uninit()
        if lib:
            # TODO...
            self.lib = lib
            self.instance_id = self.lib.GetInterfaceInstance(0, 0)
            self.elements = OnlineElements(lib)

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

