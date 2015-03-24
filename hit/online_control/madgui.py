"""
Plugin that integrates a beamoptikdll UI into MadGUI.
"""

from __future__ import absolute_import

from pydicti import dicti

from cpymad.types import Expression
from cpymad.util import strip_element_suffix, is_identifier
from madgui.util.symbol import SymbolicValue
from madgui.core import wx
from madgui.util import unit

from .beamoptikdll import BeamOptikDLL, ExecOptions
from .dvm_parameters import DVM_ParameterList
from .util import load_yaml_resource


# TODO: catch exceptions and display error messages


def strip_prefix(name, prefix):
    """Strip a specified prefix substring from a string."""
    if name.startswith(prefix):
        return name[len(prefix):]
    else:
        return name


def get_element_attribute(element, attr):
    """
    Return a tuple (name, value) for a given element attribute from MAD-X.

    Return value:

        name        assignable/evaluatable name of the attribute
        value       current value of the attribute

    Example:

        >>> element = madx.sequences['lebt'].elements['r1qs1:1']
        >>> get_element_attribute(element, 'k1')
        ('k1_r1qs1', -15.615323)
    """
    expr = element[attr]
    if isinstance(expr, SymbolicValue):
        name = str(expr._expression)
        value = expr.value
    elif isinstance(expr, Expression):
        name = str(expr)
        value = expr.value
    else:
        name = ''       # not a valid identifier! -> for check below
        value = expr    # shoud be float in this code branch
    if not is_identifier(name):
        name = strip_element_suffix(element['name']) + '->' + attr
    return (name, value)


def load_config():
    """Return the builtin configuration."""
    return load_yaml_resource('hit.online_control', 'config.yml')


class _MultiParamImporter(object):

    """
    Base class for DVM parameter importers corresponding to one element type.

    An element type (e.g. QUADRUPOLE) could have multiple importable
    parameters (K1), hence the name.

    Abstract properties:

        _known_param_names      List of parameters for this element type
    """

    def __init__(self, mad_elem, dvm_params):
        """
        Prepare importer object for a specific element.

        :param dict mad_elem: element data dictionary
        :param list dvm_params: list of all DVM_Parameter's for this element
        """
        self.mad_elem = mad_elem
        self.dvm_params_map = dicti((dvm_param.name, dvm_param)
                                    for dvm_param in dvm_params)

    def __iter__(self):
        """Iterate over all existing importable parameters in the element."""
        for param_name in self._known_param_names:
            param_func = getattr(self, param_name)
            try:
                yield param_func(self.mad_elem, self.dvm_params_map)
            except ValueError:
                pass


class ParamConverterBase(object):

    """
    Base class for DVM to MAD-X parameter importers/exporters.

    Members set in constructor:

        el_name         element name usable without :d suffix
        mad_elem        dict with MAD-X element info
        dvm_param       DVM parameter info (:class:`DVM_Parameter`)
        dvm_name        short for .dvm_param.name (fit for GetFloatValue/...)
        mad_name        lvalue name to assign value in MAD-X
        mad_value       current value in MAD-X

    Abstract properties:

        mad_symb        attribute name in MAD-X (e.g. 'k1')
        dvm_symb        parameter prefix in DVM (e.g. 'kL')

    Abstract methods:

        madx2dvm        convert MAD-X value to DVM value
        dvm2madx        convert DVM value to MAD-X value
    """

    def __init__(self, mad_elem, dvm_params_map):
        """
        Fill members with info about the DVM parameter/MAD-X attribute.

        :raises ValueError: if this parameter is not available in DVM
        """
        el_name = strip_element_suffix(mad_elem['name'])
        dvm_name = self.dvm_symb + '_' + el_name
        try:
            dvm_param = dvm_params_map[dvm_name]
        except KeyError:
            raise ValueError
        mad_name, mad_value = get_element_attribute(mad_elem, self.mad_symb)
        # now simply store values
        self.el_name = el_name
        self.mad_elem = mad_elem
        self.dvm_param = dvm_param
        self.dvm_name = dvm_name
        self.mad_name = mad_name
        self.mad_value = mad_value

    def madx2dvm(self, value):
        """Convert MAD-X value to DVM value [abstract method]."""
        raise NotImplementedError

    def dvm2madx(self, value):
        """Convert DVM value to MAD-X value [abstract method]."""
        raise NotImplementedError


class ParamImporter:

    """Namespace for DVM parameter importers grouped by element type."""

    class quadrupole(_MultiParamImporter):

        _known_param_names = ['k1']

        class k1(ParamConverterBase):

            mad_symb = 'k1'
            dvm_symb = 'kL'

            # TODO: these methods should be stable on edge cases, e.g. when
            # 'lrad' needs to be used instead of 'l':

            def madx2dvm(self, value):
                return value * self.mad_elem['l']

            def dvm2madx(self, value):
                return value / self.mad_elem['l']

    # TODO: more coefficients


class Plugin(object):

    """
    Plugin class for MadGUI.
    """

    _BeamOptikDLL = BeamOptikDLL
    _testing = False

    def __init__(self, frame, menubar):
        """
        Add plugin to the frame.

        Add a menu that can be used to connect to the online control. When
        connected, the plugin can be used to access parameters in the online
        database. This works only if the corresponding parameters were named
        exactly as in the database and are assigned with the ":=" operator.
        """
        # TODO: don't show menuitem if the .dll is not available?
        self._frame = frame
        self._dvm = None
        self._config = load_config()
        self._dvm_params = None
        units = unit.from_config_dict(self._config['units'])
        self._utool = unit.UnitConverter(units)
        # Create menu
        menu = wx.Menu()
        menubar.Append(menu, '&Online control')
        # Create menu items:
        def Append(label, help, action, condition):
            item = menu.Append(wx.ID_ANY, label, help)
            def on_click(event):
                if condition():
                    action()
            def on_update(event):
                event.Enable(condition())
            frame.Bind(wx.EVT_MENU, on_click, item)
            frame.Bind(wx.EVT_UPDATE_UI, on_update, item)
        Append('&Connect',
                'Connect online control interface',
                self.connect,
                self.is_disconnected)
        Append('&Disconnect',
                'Disconnect online control interface',
                self.disconnect,
                self.is_connected)
        menu.AppendSeparator()
        Append('&Read strengthes',
                'Read magnet strengthes from the online database',
                self.read_all,
                self.has_sequence)
        Append('&Write strengthes',
                'Write magnet strengthes to the online database',
                self.write_all,
                self.has_sequence)
        menu.AppendSeparator()
        Append('&Execute changes',
                'Apply parameter written changes to magnets',
                self.execute,
                self.has_sequence)
        menu.AppendSeparator()
        Append('Read &monitors',
               'Read SD values (beam envelope/position) from monitors',
               self.read_all_sd_values,
               self.has_sequence)
        menu.AppendSeparator()
        Append('&Load DVM parameter list',
               'Load list of DVM parameters',
               self.load_dvm_parameter_list,
               self.is_connected)

    def is_connected(self):
        """Check if online control is connected."""
        return self.connected

    def is_disconnected(self):
        """Check if online control is disconnected."""
        return not self.connected

    def has_sequence(self):
        """Check if online control is connected and a sequence is loaded."""
        return self.connected and bool(self._segman)

    def connect(self):
        """Connect to online database."""
        try:
            self._dvm = self._BeamOptikDLL.load_library()
        except OSError:
            # TODO: Loading the stub should be controlled via a MadGUI command
            # line option, and not be specific to linux.
            from . import stub
            logger = self._frame.getLogger('hit.online_control.stub')
            proxy = stub.BeamOptikDllProxy({}, logger)
            self._dvm = self._BeamOptikDLL(proxy)
            self._testing = True
        self._dvm.GetInterfaceInstance()
        self._frame.env['dvm'] = self._dvm

    def disconnect(self):
        """Disconnect from online database."""
        del self._frame.env['dvm']
        self._dvm.FreeInterfaceInstance()

    @property
    def connected(self):
        """Check if the online control is connected."""
        return bool(self._dvm)

    @property
    def _segman(self):
        """Return the online control (:class:`madgui.component.Model`)."""
        panel = self._frame.GetActiveFigurePanel()
        if panel:
            return panel.view.segman
        return None

    def iter_dvm_params(self):
        """
        Iterate over all known DVM parameters belonging to elements in the
        current sequence.

        Yields tuples of the form (Element, list[DVM_Parameter]).
        """
        for mad_elem in self._segman.elements:
            try:
                el_name = strip_element_suffix(mad_elem['name'])
                dvm_par = self._dvm_params[el_name]
                yield (mad_elem, dvm_par)
            except KeyError:
                continue

    def iter_importable_dvm_params(self):
        """
        Iterate over all DVM parameters that can be imported as MAD-X element
        attributes in the current sequence.

        Yields instances of type :class:`ParamConverterBase`.
        """
        for mad_elem, dvm_params in self.iter_dvm_params():
            try:
                importer = getattr(ParamImporter, mad_elem['type'])
            except AttributeError:
                continue
            for param in importer(mad_elem, dvm_params):
                if param.dvm_param.read:
                    yield param

    def read_all(self):
        """Read all parameters from the online database."""
        segman = self._segman
        madx = segman.simulator.madx
        for par in self.iter_importable_dvm_params():
            dvm_value = self.get_value(par.dvm_symb, par.dvm_name)
            mad_value = par.dvm2madx(dvm_value)
            plain_value = segman.simulator.utool.strip_unit(par.mad_symb,
                                                            mad_value)
            madx.set_value(par.mad_name, plain_value)
        # TODO: update only changed segments?:
        # TODO: segment ordering
        for segment in segman.segments.values():
            segment.twiss()

    def write_all(self):
        """Write all parameters to the online database."""
        for par in self.iter_dvm_params():
            self.set_value(par.param_type, par.dvm_name, par.madx_value)

    def get_float_value(self, dvm_name):
        """Get a single float value from the online database."""
        return self._dvm.GetFloatValue(dvm_name)

    def set_float_value(self, dvm_name, value):
        """Set a single float value in the online database."""
        self._dvm.SetFloatValue(dvm_name, value)

    def get_value(self, param_type, dvm_name):
        """Get a single value from the online database with unit."""
        plain_value = self.get_float_value(dvm_name)
        return self._utool.add_unit(param_type.lower(), plain_value)

    def set_value(self, param_type, dvm_name, value):
        """Set a single parameter in the online database with unit."""
        plain_value = self._utool.strip_unit(param_type, value)
        self.set_float_value(dvm_name, plain_value)

    def execute(self, options=ExecOptions.CalcDif):
        """Execute changes (commits prioir set_value operations)."""
        self._dvm.ExecuteChanges(options)

    def read_all_sd_values(self):
        """Read out SD values (beam position/envelope)."""
        segman = self._segman
        for elem in self.iter_sd_monitors():
            sd_values = self.get_sd_values(elem['name'])
            if not sd_values:
                continue
            twiss_initial = {}
            ex = segman.beam['ex']
            ey = segman.beam['ey']
            if 'widthx' in sd_values:
                twiss_initial['betx'] = sd_values['widthx'] ** 2 / ex
            if 'widthy' in sd_values:
                twiss_initial['bety'] = sd_values['widthy'] ** 2 / ey
            if 'posx' in sd_values:
                twiss_initial['x'] = sd_values['posx']
            if 'posy' in sd_values:
                twiss_initial['y'] = sd_values['posy']
            twiss_initial['mixin'] = True
            segman.set_twiss_initial(
                segman.get_element_info(elem['name']),
                self._utool.dict_add_unit(twiss_initial))

    def get_sd_values(self, element_name):
        """Read out one SD monitor."""
        try:
            sd_values = {
                'widthx': self._get_sd_value(element_name, 'widthx'),
                'widthy': self._get_sd_value(element_name, 'widthy'),
                'posx': self._get_sd_value(element_name, 'posx'),
                'posy': self._get_sd_value(element_name, 'posy'),
            }
        except RuntimeError:
            return {}
        # The magic number -9999.0 is used to signal that the value cannot be
        # used.
        # TODO: sometimes width=0 is returned. What is the reason/meaning of
        # this?
        if sd_values['widthx'] <= 0 or sd_values['widthy'] <= 0:
            return {}
        mm = unit.units.mm
        return {
            'widthx': sd_values['widthx'] * mm,
            'widthy': sd_values['widthy'] * mm,
            'posx': sd_values['posx'] * mm,
            'posy': sd_values['posy'] * mm,
        }

    def _get_sd_value(self, element_name, param_name):
        """Read a single SD value into a dictionary."""
        element_name = strip_element_suffix(element_name)
        element_name = strip_prefix(element_name, 'sd_')
        param_name = param_name
        sd_name = param_name + '_' + element_name
        return self._dvm.GetFloatValueSD(sd_name.upper())

    def iter_sd_monitors(self):
        """Iterate SD monitor elements (element dicts) in current sequence."""
        for element in self._segman.elements:
            if not element['name'].lower().startswith('sd_'):
                continue
            if not element['type'].lower().endswith('monitor'):
                continue
            yield element

    def load_dvm_parameter_list(self):
        """Show a FileDialog to import a new DVM parameter list."""
        dlg = wx.FileDialog(
            self._frame,
            "Load DVM-Parameter list. The CSV file must be ';' separated and 'utf-8' encoded.",
            wildcard="CSV files (*.csv)|*.csv",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() != wx.ID_OK:
            return
        filename = dlg.GetPath()
        # TODO: let user choose the correct delimiter/encoding settings
        try:
            parlist = DVM_ParameterList.from_csv(filename, 'utf-8')
            self._dvm_params = dicti(parlist._data)
        except UnicodeDecodeError:
            wx.MessageBox('I can only load UTF-8 encoded files!',
                          'UnicodeDecodeError',
                          wx.ICON_ERROR|wx.OK,
                          parent=self._frame)

        # TODO: this code should really be put in a separate function, to
        # have an API that enables reloading the DVM parameters:
        if self._testing:
            # for testing:
            from . import stub
            logger = self._frame.getLogger('hit.online_control.stub')

            merged_params = dicti()
            for group in self._dvm_params.values():
                for param in group:
                    if (param.read or param.write) and param.example is not None:
                        if param.ui_conv:
                            value = param.example / param.ui_conv
                        else:
                            value = param.example
                        merged_params[param.name] = value

            self._dvm._lib.data = {
                'control': merged_params,
            }
