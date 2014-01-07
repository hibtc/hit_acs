"""
Beam-optic control component.

The main component is the class `OnlineControl`.

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

    # Implemented by `MutableMapping`:
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
    def __init__(self, shared_library, model):
        """Initialize the online control."""
        self._shared_library = shared_library
        # TODO: init library
        self.elements = OnlineElements(shared_library)

