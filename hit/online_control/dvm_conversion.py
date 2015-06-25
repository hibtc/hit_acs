"""
Conversion layer for DVM to MAD-X parameter conversions and vice versa.
"""

from __future__ import absolute_import

from pydicti import dicti

from cpymad.types import Expression
from cpymad.util import strip_element_suffix, is_identifier
from madgui.util.symbol import SymbolicValue


__all__ = [
    'get_element_attribute',
    'ParamImporter',
]


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


class _MultiParamImporter(object):

    """
    Base class for DVM parameter importers corresponding to one element type.

    An element type (e.g. QUADRUPOLE) could have multiple importable
    parameters (K1), hence the name.

    Abstract properties:

        _known_param_names      List of parameters for this element type
    """

    def __init__(self, mad_elem, dvm_params, _dvm):
        """
        Prepare importer object for a specific element.

        :param dict mad_elem: element data dictionary
        :param list dvm_params: list of all DVM_Parameter's for this element
        """
        self.mad_elem = mad_elem
        self.dvm_params_map = dicti((dvm_param.name, dvm_param)
                                    for dvm_param in dvm_params)
        # TODO: rename plugin // store dedicated object (with more pure API)
        self._dvm = _dvm

    def __iter__(self):
        """Iterate over all existing importable parameters in the element."""
        for param_name in self._known_param_names:
            param_func = getattr(self, param_name)
            try:
                yield param_func(self.mad_elem, self.dvm_params_map, self._dvm)
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

    # TODO: improve API of this class...
    # - rename set_value(), get_value()
    # - handle mad_value differently?
    # - common display name

    def __init__(self, mad_elem, dvm_params_map, _dvm):
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
        self._mad_value = mad_value
        self._dvm = _dvm

    def madx2dvm(self, value):
        """Convert MAD-X value to DVM value [abstract method]."""
        raise NotImplementedError

    def dvm2madx(self, value):
        """Convert DVM value to MAD-X value [abstract method]."""
        raise NotImplementedError

    def set_value(self):
        return self._dvm.set_value(
            self.param_type,
            self.dvm_name,
            self.madx_value)

    def get_value(self):
        return self._dvm.get_value(
            self.dvm_symb,
            self.dvm_name)

    @property
    def mad_value(self):
        return self._mad_value


class ParamImporter:

    """Namespace for DVM parameter importers grouped by element type."""

    class quadrupole(_MultiParamImporter):

        _known_param_names = ['k1']

        class k1(ParamConverterBase):

            mad_symb = 'k1'
            dvm_symb = 'kL'

            # TODO: make these methods should be stable on edge cases, e.g.
            # when 'lrad' needs to be used instead of 'l':
            # TODO: read and write use different parameters, but which...?

            def madx2dvm(self, value):
                return value * self.mad_elem['l']

            def dvm2madx(self, value):
                return value / self.mad_elem['l']


    class sbend(_MultiParamImporter):

        _known_param_names = ['angle']

        class angle(ParamConverterBase):

            # The total angle is the sum of correction angle (dax) and
            # geometric angle (axgeo):
            #
            #   angle = axgeo + dax
            #
            # Only the correction angle is to be modified.

            mad_symb = 'angle'
            dvm_symb = 'dax'

            def madx2dvm(self, value):
                return value - self.axgeo

            def dvm2madx(self, value):
                return value + self.axgeo

            @property
            def axgeo(self):
                dvm_symb = 'axgeo'
                dvm_name = dvm_symb + '_' + self.el_name
                return self._dvm.get_value(dvm_symb, dvm_name)


            # k1s?

    # TODO: more coefficients:
    # - multipole:  KNL/KSL
    # - sbend:      ANGLE/dax
    #               dipedge?
    # - solenoid:   KS/?
