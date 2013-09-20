"""
Beam-optic control component.

The main component is the class `OnlineControl`. This class is responsible
for managing the interaction between model and online control.

There is also `load_shared_library` to load a runtime library (.dll/.so).

Finally, `OnlineElements` is used for dictionary-like access of online
element parameters.

"""
import ctypes
import collections


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


class OnlineElements(collections.MutableMapping):
    """
    Utility for accessing optics parameters online.
    """
    def __init__(self, library):
        """Initialize instance."""
        self._library = library

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
        pass

    def __setitem__(self, name, value):
        """
        Set the online parameter.

        TODO

        """
        pass

    def __iter__(self):
        """
        Iterate all elements.
        """
        pass

    def __len__(self):
        """Number of elements."""
        pass

    # `MutableMapping` mixins:
    get          = collections.MutableMapping.get
    __contains__ = collections.MutableMapping.__contains__
    keys         = collections.MutableMapping.keys
    items        = collections.MutableMapping.items
    values       = collections.MutableMapping.values
    clear        = collections.MutableMapping.clear
    update       = collections.MutableMapping.update
    setdefault   = collections.MutableMapping.setdefault

    # Unsupported operations
    def __delitem__(self, name):
        """Invalid operation!"""
        raise RuntimeError("Go downstairs and remove it yourself!")

    pop          = __delitem__
    popitem      = __delitem__



class OnlineControl:
    """
    Beam-optic control component.

    This component encapsulates the interface to the online functionality of
    madgui. Specifically at this point it talks to the shared library
    'BeamOptikDLL.dll'.

    """
    _shared_library = None

    def __init__(self, model, shared_library=None):
        """Initialize the online control."""
        self.startup(shared_library)

    def startup(self, library):
        """Run the library's initialization routines and store the object."""
        self.uninit()
        if shared_library:
            # TODO...
            self._shared_library = shared_library
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
        if self._shared_library:
            self._shared_library, lib = None, self._shared_library
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

