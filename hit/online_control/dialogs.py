"""
Dialog for selecting DVM parameters to be synchronized.
"""

from __future__ import absolute_import

from madgui.core import wx
from madgui.widget.listview import CheckListCtrl
from madgui.widget.input import ModalDialog
from madgui.util.unit import format_quantity, tounit


class SyncParamDialog(ModalDialog):

    """
    Dialog for selecting DVM parameters to be synchronized.
    """

    def SetData(self, data):
        self.data = data
        self._rows = []
        self._inserting = False
        self.selected = []

    def CreateContentArea(self):

        """Create sizer with content area, i.e. input fields."""

        grid = CheckListCtrl(self, style=wx.LC_REPORT|wx.LC_SINGLE_SEL)
        grid._OnCheckItem = self.OnChangeActive
        grid.SetMinSize(wx.Size(400, 300))
        self._grid = grid

        grid.InsertColumn(
            0, "Param",
            format=wx.LIST_FORMAT_LEFT,
            width=wx.LIST_AUTOSIZE)
        grid.InsertColumn(
            1, "DVM value",
            format=wx.LIST_FORMAT_RIGHT,
            width=wx.LIST_AUTOSIZE)
        grid.InsertColumn(
            2, "MAD-X value",
            format=wx.LIST_FORMAT_RIGHT,
            width=wx.LIST_AUTOSIZE)

        headline = wx.StaticText(self, label="DVM parameters:")

        inner = wx.BoxSizer(wx.HORIZONTAL)
        inner.Add(grid, 1, flag=wx.ALL|wx.EXPAND, border=5)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(headline, flag=wx.ALL|wx.ALIGN_LEFT, border=5)
        outer.Add(inner, 1, flag=wx.ALL|wx.EXPAND, border=5)

        return outer

    def OnChangeActive(self, row, active):
        if self._inserting:
            return
        _, param, dvm_value = self._rows[row]
        self._rows[row] = active, param, dvm_value

    def TransferDataToWindow(self):
        for active, param, dvm_value in self.data:
            self.AddRow(active, param, dvm_value)

    def TransferDataFromWindow(self):
        self.data = list(self._rows)
        self.selected = [
            (param, dvm_value)
            for active, param, dvm_value in self.data
            if active
        ]

    def format_value(self, param, value):
        value = tounit(value, param.dvm_param.ui_unit)
        fmt_code = '.{}f'.format(param.dvm_param.ui_prec)
        return format_quantity(value, fmt_code)

    def AddRow(self, active, param, dvm_value):

        """
        Add one row to the list of TWISS initial conditions.
        """

        grid = self._grid

        # insert elements
        self._inserting = True
        index = grid.GetItemCount()

        mad_value = param.madx2dvm(param.mad_value)

        grid.InsertStringItem(index, param.dvm_name)
        grid.SetStringItem(index, 1, self.format_value(param, dvm_value))
        grid.SetStringItem(index, 2, self.format_value(param, mad_value))
        grid.CheckItem(index, active)

        grid.SetColumnWidth(0, wx.LIST_AUTOSIZE)
        grid.SetColumnWidth(1, wx.LIST_AUTOSIZE)
        grid.SetColumnWidth(2, wx.LIST_AUTOSIZE)

        # update stored data
        self._rows.insert(index, (active, param, dvm_value))
        self._inserting = False

        return index
