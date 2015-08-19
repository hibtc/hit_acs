# encoding: utf-8
"""
Madgui online control plugin.
"""

from __future__ import absolute_import

from pydicti import dicti

from .util import load_yaml_resource

from .beamoptikdll import BeamOptikDLL, ExecOptions
from .stub import BeamOptikDllProxy

from madgui.core.plugin import HookCollection
from madgui.core import wx
from madgui.util import unit
from madgui.online import api

from .dvm_parameters import DVM_ParameterList


class StubLoader(api.PluginLoader):

    title = '&test stub'
    descr = 'a stub version (for offline testing)'

    @classmethod
    def check_avail(cls):
        return True

    @classmethod
    def load(cls, frame):
        logger = frame.getLogger('hit.online_control.stub')
        proxy = BeamOptikDllProxy({}, logger)
        dvm = BeamOptikDLL(proxy)
        mgr = DVM_Param_Manager(dvm, frame)
        mgr.hook.on_loaded_dvm_params.connect(
            proxy._use_dvm_parameter_examples)
        return HitOnlineControl(dvm, mgr)


class DllLoader(api.PluginLoader):

    title = '&online control'
    descr = 'the online control'

    @classmethod
    def check_avail(cls):
        return BeamOptikDLL.check_library()

    @classmethod
    def load(cls, frame):
        """Connect to online database."""
        dvm = BeamOptikDLL.load_library()
        mgr = DVM_Param_Manager(dvm, frame)
        return HitOnlineControl(dvm, mgr)


class DVM_Param_Manager(object):

    def __init__(self, dvm, frame=None):
        self._dvm = dvm
        self._frame = frame
        self._cache = {}
        self.hook = HookCollection(
            on_loaded_dvm_params=None)

    def get(self, segment):
        if segment not in self._cache:
            self._cache[segment] = dvm_params = self._load(segment)
            self.hook.on_loaded_dvm_params(dvm_params)
        return self._cache[segment]

    def _elem_param_dict(self, el_name, parlist):
        ret = dicti((p.name, p) for p in parlist)
        # NOTE: the following is an ugly hack to correct for missing suffixes
        # for some of the DB parameters. It would better to find a solution
        # that is not hard-coded.
        el_name = el_name.lower()
        if el_name.endswith('h') or el_name.endswith('v'):
            update = {}
            el_prefix = el_name[:-1]
            el_suffix = el_name[-1]
            for k, v in ret.items():
                if k.lower().endswith('_' + el_prefix):
                    update[k+el_suffix] = v
            ret.update(update)
        return ret

    def _load(self, segment):
        try:
            repo = segment.model._repo
            data = repo.yaml('dvm.yml')
            parlist = DVM_ParameterList.from_yaml_data(data)
        # TODO: catch IOError or similar
        except AttributeError:
            parlist = self._load_from_disc()
        return dicti(
            (k, self._elem_param_dict(k, l))
            for k, l in parlist._data.items())

    def _load_from_disc(self):
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
            return DVM_ParameterList.from_csv(filename, 'utf-8')
        except UnicodeDecodeError:
            wx.MessageBox('I can only load UTF-8 encoded files!',
                          'UnicodeDecodeError',
                          wx.ICON_ERROR|wx.OK,
                          parent=self._frame)


def _get_value(dvm, utool, param_type, dvm_name):
    """Get a single value from the online database with unit."""
    plain_value = dvm.GetFloatValue(dvm_name)
    return utool.add_unit(param_type.lower(), plain_value)


def _set_value(dvm, utool, param_type, dvm_name, value):
    """Set a single parameter in the online database with unit."""
    plain_value = utool.strip_unit(param_type, value)
    dvm.SetFloatValue(dvm_name, plain_value)


def _get_sd_value(dvm, el_name, param_name):
    """Return a single SD value (with unit)."""
    sd_name = param_name + '_' + el_name
    plain_value = dvm.GetFloatValueSD(sd_name.upper())
    return plain_value * unit.units.mm


class HitOnlineControl(api.OnlinePlugin):

    def __init__(self, dvm, mgr):
        self._dvm = dvm
        self._mgr = mgr
        self._config = load_yaml_resource('hit.online_control', 'config.yml')
        self._utool = unit.UnitConverter(
            unit.from_config_dict(self._config['units']))
        self._connect()

    def _connect(self):
        """Connect to online database (must be loaded)."""
        self._dvm.GetInterfaceInstance()

    # OnlinePlugin API

    def disconnect(self):
        """Disconnect from online database."""
        self._dvm.FreeInterfaceInstance()

    def execute(self, options=ExecOptions.CalcDif):
        """Execute changes (commits prior set_value operations)."""
        self._dvm.ExecuteChanges(options)

    def param_info(self, segment, element, key):
        """Get parameter info for backend key."""
        el_name = element['name']
        return self._mgr.get(segment)[el_name][key + '_' + el_name]

    def get_monitor(self, segment, elements):
        """
        Get a (:class:`ElementBackendConverter`, :class:`ElementBackend`)
        tuple for a monitor.
        """
        conv = MonitorConv()
        back = DBMonitorBackend(self._dvm, elements[0]['name'])
        return conv, back

    def get_dipole(self, segment, elements, skew):
        """
        Get a (:class:`ElementBackendConverter`, :class:`ElementBackend`)
        tuple for a dipole.
        """
        el_name = elements[0]['name']
        geom_symb = 'a' + ('y' if skew else 'x') + 'geo'
        geom_parm = geom_symb + '_' + el_name
        if geom_parm in self._mgr.get(segment).get(el_name, {}):
            ageo = _get_value(self._dvm, self._utool, geom_symb, geom_parm)
            conv = (DipoleVBigConv if skew else DipoleHBigConv)(ageo)
        else:
            conv = (DipoleVConv if skew else DipoleHConv)()
        return self._construct(segment, elements, conv)

    def get_quadrupole(self, segment, elements):
        """
        Get a (:class:`ElementBackendConverter`, :class:`ElementBackend`)
        tuple for a quadrupole.
        """
        return self._construct(segment, elements, QuadrupoleConv())

    def get_solenoid(self, segment, elements):
        """
        Get a (:class:`ElementBackendConverter`, :class:`ElementBackend`)
        tuple for a solenoid.
        """
        return self._construct(segment, elements, SolenoidConv())

    def _construct(self, segment, elements, conv):
        name = elements[0]['name']
        lval = {key: key + '_' + name for key in conv.backend_keys}
        back = DBElementBackend(self._dvm, self._utool, lval)
        try:
            conv.param_info = {
                key: self.param_info(segment, elements[0], key)
                for key in conv.backend_keys
            }
        except KeyError:
            raise api.UnknownElement
        return conv, back


class DBElementBackend(api.ElementBackend):

    """Mitigates r/w access to the properties of an element."""

    def __init__(self, dvm, utool, lval):
        self._dvm = dvm
        self._utool = utool
        self._lval = lval

    def get(self):
        """Get dict of values from the DB."""
        return {key: _get_value(self._dvm, self._utool, key, lval)
                for key, lval in self._lval.items()}

    def set(self, values):
        """Store values to DB."""
        for key, val in values.items():
            _set_value(self._dvm, self._utool, key, self._lval[key], val)


class DBMonitorBackend(api.ElementBackend):

    """Mitigates read access to a monitor."""

    def __init__(self, dvm, el_name):
        self._dvm = dvm
        self._el_name = el_name

    def get(self):
        """Read out one SD monitor."""
        values = {}
        for feature in ('widthx', 'widthy', 'posx', 'posy'):
            # TODO: Handle usability of parameters individually
            try:
                val = _get_sd_value(self._dvm, self._el_name, feature)
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

    def set(self, values):
        raise NotImplementedError("Can't set TWISS: monitors are read-only!")


#----------------------------------------
# Converters:
#----------------------------------------

# TODO: handle more complicated elements (see HICAT bible)

class MonitorConv(api.NoConversion):
    standard_keys = ['posx', 'posy', 'envx', 'envy']
    backend_keys = ['posx', 'posy', 'widthx', 'widthy']


class DipoleHConv(api.NoConversion):
    standard_keys = ['angle']
    backend_keys = ['ax']


class DipoleVConv(api.NoConversion):
    standard_keys = ['angle']
    backend_keys = ['ay']


class _DipoleBigConv(api.ElementBackendConverter):

    # The total angle is the sum of correction angle (dax) and
    # geometric angle (axgeo):
    #
    #   angle = axgeo + dax
    #
    # Only the correction angle is to be modified.

    standard_keys = ['angle']

    @property
    def backend_keys(self):
        return [self._key]

    def __init__(self, ageo):
        self._ageo = ageo

    def to_standard(self, values):
        return {'angle': values[self._key] + self._ageo}

    def to_backend(self, values):
        return {self._key: values['angle'] - self._ageo}


class DipoleHBigConv(_DipoleBigConv):
    _key = 'dax'


class DipoleVBigConv(_DipoleBigConv):
    _key = 'day'


class QuadrupoleConv(api.NoConversion):
    standard_keys = backend_keys = ['kL']


class SolenoidConv(api.NoConversion):
    standard_keys = backend_keys = ['ks']
