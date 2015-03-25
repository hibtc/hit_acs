"""
Dialog for selecting DVM parameters to be synchronized.
"""

from __future__ import absolute_import

from functools import partial

from cpymad.util import strip_element_suffix

from madgui.core import wx
from madgui.widget.listview import ManagedListCtrl, ColumnInfo
from madgui.widget.input import ModalDialog
from madgui.util.unit import format_quantity, tounit


class SelectDialog(ModalDialog):

    """
    Dialog for selecting from an immutable list of items.
    """

    _min_size = wx.Size(400, 300)
    _headline = 'Select desired items:'

    # TODO: allow to customize initial selection
    # FIXME: select-all looks ugly, check/uncheck-each is tedious...

    def SetData(self, data):
        self.data = data
        self.selected_indices = list(range(len(data)))
        self.selected = data

    def CreateContentArea(self):
        """Create sizer with content area, i.e. input fields."""
        grid = ManagedListCtrl(self, self.GetColumns(), style=0)
        grid.SetMinSize(self._min_size)
        self._grid = grid
        # create columns
        # other layout
        headline = wx.StaticText(self, label=self._headline)
        inner = wx.BoxSizer(wx.HORIZONTAL)
        inner.Add(grid, 1, flag=wx.ALL|wx.EXPAND, border=5)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(headline, flag=wx.ALL|wx.ALIGN_LEFT, border=5)
        outer.Add(inner, 1, flag=wx.ALL|wx.EXPAND, border=5)
        return outer

    def TransferDataToWindow(self):
        self._grid.items = self.data
        for idx in range(len(self.data)):
            self._grid.Select(idx)

    def TransferDataFromWindow(self):
        self.selected_indices = list(self._grid.selected_indices)
        self.selected = list(self._grid.selected_items)


def format_dvm_value(param, value):
    value = tounit(value, param.dvm_param.ui_unit)
    fmt_code = '.{}f'.format(param.dvm_param.ui_prec)
    return format_quantity(value, fmt_code)


class SyncParamDialog(SelectDialog):

    """
    Dialog for selecting DVM parameters to be synchronized.
    """

    def __init__(self, *args, **kwargs):
        self._headline = kwargs.pop('headline')
        super(SyncParamDialog, self).__init__(*args, **kwargs)

    def GetColumns(self):
        return [
            ColumnInfo(
                "Param",
                self._format_param,
                wx.LIST_FORMAT_LEFT,
                wx.LIST_AUTOSIZE),
            ColumnInfo(
                "DVM value",
                self._format_dvm_value,
                wx.LIST_FORMAT_RIGHT,
                wx.LIST_AUTOSIZE),
            ColumnInfo(
                "MAD-X value",
                self._format_madx_value,
                wx.LIST_FORMAT_RIGHT,
                wx.LIST_AUTOSIZE),
        ]

    def _format_param(self, index, item):
        param, dvm_value = item
        return param.dvm_name

    def _format_dvm_value(self, index, item):
        param, dvm_value = item
        return format_dvm_value(param, dvm_value)

    def _format_madx_value(self, index, item):
        param, dvm_value = item
        mad_value = param.madx2dvm(param.mad_value)
        return format_dvm_value(param, mad_value)


class MonitorDialog(SelectDialog):

    """
    Dialog for selecting SD monitor values to be imported.
    """

    _headline = "Import selected monitor measurements:"

    def GetColumns(self):
        return [
            ColumnInfo(
                "Monitor",
                self._format_monitor_name,
                wx.LIST_FORMAT_LEFT,
                wx.LIST_AUTOSIZE),
            ColumnInfo(
                "x",
                partial(self._format_sd_value, 'posx'),
                wx.LIST_FORMAT_RIGHT,
                wx.LIST_AUTOSIZE),
            ColumnInfo(
                "y",
                partial(self._format_sd_value, 'posy'),
                wx.LIST_FORMAT_RIGHT,
                wx.LIST_AUTOSIZE),
            ColumnInfo(
                "x width",
                partial(self._format_sd_value, 'widthx'),
                wx.LIST_FORMAT_RIGHT,
                wx.LIST_AUTOSIZE),
            ColumnInfo(
                "y width",
                partial(self._format_sd_value, 'widthy'),
                wx.LIST_FORMAT_RIGHT,
                wx.LIST_AUTOSIZE),
        ]

    def _format_monitor_name(self, index, item):
        elem, values = item
        return strip_element_suffix(elem['name'])

    def _format_sd_value(self, name, index, item):
        elem, values = item
        value = values.get(name)
        if value is None:
            return ''
        return format_quantity(value)
