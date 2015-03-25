"""
Plugin that integrates a beamoptikdll UI into MadGUI.
"""

from __future__ import absolute_import

import sys
import traceback

from pydicti import dicti

from cpymad.util import strip_element_suffix
from madgui.core import wx
from madgui.core.plugin import HookCollection
from madgui.util import unit
from madgui.widget import menu

from .beamoptikdll import BeamOptikDLL, ExecOptions
from .dvm_parameters import DVM_ParameterList
from .dvm_conversion import ParamImporter
from .util import load_yaml_resource
from .dialogs import SyncParamDialog, MonitorDialog
from .stub import BeamOptikDllProxy


# TODO: catch exceptions and display error messages
# TODO: automate loading DVM parameters via model and/or named hook


def strip_prefix(name, prefix):
    """Strip a specified prefix substring from a string."""
    if name.startswith(prefix):
        return name[len(prefix):]
    else:
        return name


def load_config():
    """Return the builtin configuration."""
    return load_yaml_resource('hit.online_control', 'config.yml')


class Plugin(object):

    """
    Plugin class for MadGUI.
    """

    _BeamOptikDLL = BeamOptikDLL

    def __init__(self, frame, menubar):
        """
        Add plugin to the frame.

        Add a menu that can be used to connect to the online control. When
        connected, the plugin can be used to access parameters in the online
        database. This works only if the corresponding parameters were named
        exactly as in the database and are assigned with the ":=" operator.
        """
        if not (self._check_dll() or self._check_stub()):
            # Can't connect, so no point in showing anything.
            return
        self.hook = HookCollection(
            on_loaded_dvm_params=None)
        self._frame = frame
        self._dvm = None
        self._config = load_config()
        self._dvm_params = None
        units = unit.from_config_dict(self._config['units'])
        self._utool = unit.UnitConverter(units)
        submenu = self.create_menu()
        menu.extend(frame, menubar, [submenu])

    def _check_dll(self):
        """Check if the 'Connect' menu item should be shown."""
        return self._BeamOptikDLL.check_library()

    def _check_stub(self):
        """Check if the 'Connect &test stub' menu item should be shown."""
        # TODO: check for debug mode?
        return True

    def create_menu(self):
        """Create menu."""
        Item = menu.CondItem
        Separator = menu.Separator
        items = []
        if self._check_dll():
            items += [
                Item('&Connect',
                     'Connect online control interface',
                     self.load_and_connect,
                     self.is_disconnected),
            ]
        if self._check_stub():
            items += [
                Item('Connect &test stub',
                     'Connect a stub version (for offline testing)',
                     self.load_and_connect_stub,
                     self.is_disconnected),
            ]
        items += [
            Item('&Disconnect',
                 'Disconnect online control interface',
                 self.disconnect,
                 self.is_connected),
            Separator,
            Item('&Read strengthes',
                 'Read magnet strengthes from the online database',
                 self.read_all,
                 self.has_sequence),
            Item('&Write strengthes',
                 'Write magnet strengthes to the online database',
                 self.write_all,
                 self.has_sequence),
            Separator,
            Item('&Execute changes',
                 'Apply parameter written changes to magnets',
                 self.execute,
                 self.has_sequence),
            Separator,
            Item('Read &monitors',
                 'Read SD values (beam envelope/position) from monitors',
                 self.read_all_sd_values,
                 self.has_sequence),
            Separator,
            Item('&Load DVM parameter list',
                 'Load list of DVM parameters',
                 self.load_dvm_parameter_list,
                 self.is_connected),
        ]
        return menu.Menu('&Online control', items)

    def is_connected(self):
        """Check if online control is connected."""
        return self.connected

    def is_disconnected(self):
        """Check if online control is disconnected."""
        return not self.connected

    def has_sequence(self):
        """Check if online control is connected and a sequence is loaded."""
        return self.connected and bool(self._segman)

    def load_and_connect(self):
        """Connect to online database."""
        try:
            self._dvm = self._BeamOptikDLL.load_library()
        except OSError:
            exc_str = traceback.format_exception_only(*sys.exc_info()[:2])
            wx.MessageBox("".join(exc_str),
                          'Failed to load DVM module',
                          wx.ICON_ERROR|wx.OK,
                          parent=self._frame)
            return
        self._connect()

    def load_and_connect_stub(self):
        """Connect a stub BeamOptikDLL (for offline testing)."""
        logger = self._frame.getLogger('hit.online_control.stub')
        proxy = BeamOptikDllProxy({}, logger)
        self.hook.on_loaded_dvm_params.connect(
            proxy._use_dvm_parameter_examples)
        self._dvm = self._BeamOptikDLL(proxy)
        self._connect()

    def _connect(self):
        """Connect to online database (must be loaded)."""
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

    def iter_convertible_dvm_params(self):
        """
        Iterate over all DVM parameters that can be converted to/from MAD-X
        element attributes in the current sequence.

        Yields instances of type :class:`ParamConverterBase`.
        """
        for mad_elem, dvm_params in self.iter_dvm_params():
            try:
                importer = getattr(ParamImporter, mad_elem['type'])
            except AttributeError:
                continue
            for param in importer(mad_elem, dvm_params):
                yield param

    def iter_readable_dvm_params(self):
        """
        Iterate over all DVM parameters that can be imported as MAD-X element
        attributes in the current sequence.

        Yields instances of type :class:`ParamConverterBase`.
        """
        return (p for p in self.iter_convertible_dvm_params()
                if p.dvm_param.read)

    def iter_writable_dvm_params(self):
        """
        Iterate over all DVM parameters that can be set from  MAD-X element
        attributes in the current sequence.

        Yields instances of type :class:`ParamConverterBase`.
        """
        return (p for p in self.iter_convertible_dvm_params()
                if p.dvm_param.write)

    def read_all(self):
        """Read all parameters from the online database."""
        # TODO: cache and reuse 'active' flag for each parameter
        rows = [(True, param, self.get_value(param.dvm_symb, param.dvm_name))
                for param in self.iter_readable_dvm_params()]
        if not rows:
            wx.MessageBox('There are no readable DVM parameters in the current sequence. Note that this operation requires a list of DVM parameters to be loaded.',
                          'No readable parameters available',
                          wx.ICON_ERROR|wx.OK,
                          parent=self._frame)
            return
        dlg = SyncParamDialog(self._frame,
                              'Import parameters from DVM',
                              data=rows)
        if dlg.ShowModal() == wx.ID_OK:
            self.read_these(dlg.selected)

    def read_these(self, params):
        """
        Import list of DVM parameters to MAD-X.

        :param list params: List of tuples (ParamConverterBase, dvm_value)
        """
        segman = self._segman
        madx = segman.simulator.madx
        strip_unit = segman.simulator.utool.strip_unit
        for param, dvm_value in params:
            mad_value = param.dvm2madx(dvm_value)
            plain_value = strip_unit(param.mad_symb, mad_value)
            madx.set_value(param.mad_name, plain_value)
        # TODO: update only changed segments?:
        # TODO: segment ordering
        for segment in segman.segments.values():
            segment.twiss()

    def write_all(self):
        """Write all parameters to the online database."""
        rows = [(True, param, self.get_value(param.dvm_symb, param.dvm_name))
                for param in self.iter_writable_dvm_params()]
        if not rows:
            wx.MessageBox('There are no writable DVM parameters in the current sequence. Note that this operation requires a list of DVM parameters to be loaded.',
                          'No writable parameters available',
                          wx.ICON_ERROR|wx.OK,
                          parent=self._frame)
            return
        dlg = SyncParamDialog(self._frame,
                              'Set values in DVM from current sequence',
                              data=rows)
        if dlg.ShowModal() == wx.ID_OK:
            self.write_these(par for par, _ in dlg.selected)

    def write_these(self, params):
        """
        Set parameter values in DVM from a list of parameters.

        :param list params: List of ParamConverterBase
        """
        for par in params:
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

    def iter_sd_values(self):
        """Yields (element, values) tuples for usable monitors."""
        for elem in self.iter_monitors():
            values = self.get_sd_values(elem['name'])
            if values:
                yield (elem, values)

    def read_all_sd_values(self):
        """Read out SD values (beam position/envelope)."""
        # TODO: cache list of used SD monitors
        rows = [(True, elem, values)
                for elem, values in self.iter_sd_values()]
        if not rows:
            wx.MessageBox('There are no usable SD monitors in the current sequence.',
                          'No usable monitors available',
                          wx.ICON_ERROR|wx.OK,
                          parent=self._frame)
            return
        dlg = MonitorDialog(self._frame,
                            'Set values in DVM from current sequence',
                            data=rows)
        if dlg.ShowModal() == wx.ID_OK:
            self.use_these_sd_values(dlg.selected)

    def use_these_sd_values(self, monitor_values):
        segman = self._segman
        utool = segman.simulator.utool
        all_twiss = segman.twiss_initial.copy()
        for elem, values in monitor_values:
            twiss_initial = {}
            ex = segman.beam['ex']
            ey = segman.beam['ey']
            if 'widthx' in values:
                twiss_initial['betx'] = values['widthx'] ** 2 / ex
            if 'widthy' in values:
                twiss_initial['bety'] = values['widthy'] ** 2 / ey
            if 'posx' in values:
                twiss_initial['x'] = values['posx']
            if 'posy' in values:
                twiss_initial['y'] = values['posy']
            twiss_initial['mixin'] = True
            twiss_initial = utool.dict_normalize_unit(twiss_initial)
            element_info = segman.get_element_info(elem['name'])
            all_twiss[element_info.index] = twiss_initial
        segman.set_all(all_twiss)

    def get_sd_values(self, element_name):
        """Read out one SD monitor."""
        values = {}
        for feature in ('widthx', 'widthy', 'posx', 'posy'):
            # TODO: Handle usability of parameters individually
            try:
                val = self._get_sd_value(element_name, feature)
            except RuntimeError:
                return {}
            # TODO: move sanity check to later, so values will simply be
            # unchecked/grayed out, instead of removed completely
            # The magic number -9999.0 signals corrupt values.
            # FIXME: Sometimes width=0 is returned. ~ Meaning?
            if feature.startswith('width') and val.magnitude <= 0:
                return {}
            values[feature] = val
        return values

    def _get_sd_value(self, element_name, param_name):
        """Return a single SD value (with unit)."""
        element_name = strip_element_suffix(element_name)
        element_name = strip_prefix(element_name, 'sd_')
        param_name = param_name
        sd_name = param_name + '_' + element_name
        plain_value = self._dvm.GetFloatValueSD(sd_name.upper())
        # NOTE: Values returned by SD monitors are in millimeter:
        return plain_value * unit.units.mm

    def iter_monitors(self):
        """Iterate SD monitor elements (element dicts) in current sequence."""
        for element in self._segman.elements:
            if element['type'].lower().endswith('monitor'):
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
        except UnicodeDecodeError:
            wx.MessageBox('I can only load UTF-8 encoded files!',
                          'UnicodeDecodeError',
                          wx.ICON_ERROR|wx.OK,
                          parent=self._frame)
        else:
            self.set_dvm_parameter_list(parlist)

    def set_dvm_parameter_list(self, parlist):
        """Use specified DVM_ParameterList."""
        self._dvm_params = dicti(parlist._data)
        self.hook.on_loaded_dvm_params(self._dvm_params)
