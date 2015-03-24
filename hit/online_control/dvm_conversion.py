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
