"""
Dialog for selecting DVM parameters to be synchronized.
"""

from __future__ import absolute_import

from functools import partial

from cpymad.util import strip_element_suffix

from madgui.core import wx
from madgui.widget.listview import ListCtrl, ColumnInfo
from madgui.widget.input import Widget
from madgui.widget.element import ElementWidget
from madgui.util.unit import format_quantity, tounit


def el_name(el):
    return strip_element_suffix(el['name'])


class ListSelectWidget(Widget):

    """
    Widget for selecting from an immutable list of items.
    """

    _min_size = wx.Size(400, 300)
    _headline = 'Select desired items:'

    # TODO: allow to customize initial selection
    # FIXME: select-all looks ugly, check/uncheck-each is tedious...

    def CreateControls(self, window):
        """Create sizer with content area, i.e. input fields."""
        grid = ListCtrl(window, self.GetColumns(), style=0)
        grid.SetMinSize(self._min_size)
        self._grid = grid
        # create columns
        # other layout
        headline = wx.StaticText(window, label=self._headline)
        inner = wx.BoxSizer(wx.HORIZONTAL)
        inner.Add(grid, 1, flag=wx.ALL|wx.EXPAND, border=5)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(headline, flag=wx.ALL|wx.ALIGN_LEFT, border=5)
        outer.Add(inner, 1, flag=wx.ALL|wx.EXPAND, border=5)
        return outer

    def SetData(self, data):
        self._grid.items = data
        # TODO: replace SELECT(ALL) by SELECT(SELECTED)
        for idx in range(len(data)):
            self._grid.Select(idx)

    def GetData(self):
        return list(self._grid.selected_items)


def format_dvm_value(param, value):
    value = tounit(value, param.dvm_param.ui_unit)
    fmt_code = '.{}f'.format(param.dvm_param.ui_prec)
    return format_quantity(value, fmt_code)


class SyncParamWidget(ListSelectWidget):

    """
    Dialog for selecting DVM parameters to be synchronized.
    """

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


class ImportParamWidget(SyncParamWidget):
    Title = 'Import parameters from DVM'
    headline = 'Import selected DVM parameters.'


class ExportParamWidget(SyncParamWidget):
    Title = 'Set values in DVM from current sequence'
    headline = 'Overwrite selected DVM parameters.'


class MonitorWidget(ListSelectWidget):

    """
    Dialog for selecting SD monitor values to be imported.
    """

    Title = 'Set values in DVM from current sequence'

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


class NumberInputWidget(Widget):

    label = 'Enter number:'

    def CreateControls(self, window):
        self.ctrl_label = wx.StaticText(window, label=self.label)
        self.ctrl_input = wx.TextCtrl(window, style=wx.TE_RIGHT)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.ctrl_label, flag=wx.ALL|wx.ALIGN_CENTER, border=5)
        sizer.AddSpacer(5)
        sizer.Add(self.ctrl_input, 1, flag=wx.ALL|wx.ALIGN_CENTER, border=5)
        return sizer

    def GetData(self):
        return float(ctrl_input.GetValue())

    def SetData(self, number, label=None):
        if label is not None:
            self.label = label
            self.ctrl_label.SetLabel(label)
        self.ctrl_input.SetValue(str(number))


def NumericInputCtrl(window):
    return wx.TextCtrl(window, style=wx.TE_RIGHT)


class OptikVarianzWidget(Widget):

    def CreateControls(self, window):
        sizer = wx.FlexGridSizer(4, 3)
        sizer.AddGrowableCol(1)
        def _Add(label, ctrl):
            sizer.Add(wx.StaticText(window, label=label), border=5,
                      flag=wx.ALL|wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL)
            sizer.AddSpacer(10)
            sizer.Add(ctrl, border=5,
                      flag=wx.ALL|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL)
            return ctrl
        self.ctrl_mon = _Add("Monitor:", wx.Choice(window))
        self.ctrl_qps = _Add("Quadrupole:", wx.Choice(window))
        self.ctrl_kl_0 = _Add("KL (1st):", NumericInputCtrl(window))
        self.ctrl_kl_1 = _Add("KL (2nd):", NumericInputCtrl(window))
        self.ctrl_mon.Bind(wx.EVT_CHOICE, self.OnChangeMonitor)
        self.ctrl_qps.Bind(wx.EVT_CHOICE, self.OnChangeQuadrupole)
        return sizer

    def OnChangeMonitor(self, event=None):
        mon = self.elem_mon[self.ctrl_mon.GetSelection()]
        qps = self.ctrl_qps
        sel = qps.GetSelection()
        qps.SetItems([el_name(el) for el in self.elem_qps
                      if el['at'] < mon['at']])
        if sel < qps.GetCount() and sel != wx.NOT_FOUND:
            qps.SetSelection(sel)
        else:
            qps.SetSelection(qps.GetCount() - 1)
            self.OnChangeQuadrupole()

    def OnChangeQuadrupole(self, event=None):
        elem = self.elem_qps[self.ctrl_qps.GetSelection()]
        self.ctrl_kl_0.SetValue(str(float(elem['k1'])))

    def GetData(self):
        mon = self.ctrl_mon.GetStringSelection()
        qp = self.ctrl_qps.GetStringSelection()
        kl_0 = float(self.ctrl_kl_0.GetValue())
        kl_1 = float(self.ctrl_kl_1.GetValue())
        return mon, qp, kl_0, kl_1

    def SetData(self, elements):
        self.elem_mon = [el for el in elements if el['type'] == 'monitor']
        self.elem_qps = [el for el in elements if el['type'] == 'quadrupole']
        self.ctrl_mon.SetItems([el_name(el) for el in self.elem_mon])
        self.ctrl_mon.SetSelection(len(self.elem_mon)-1)
        self.OnChangeMonitor()

    def Validate(self, window):
        try:
            float(self.ctrl_kl_0.GetValue())
        except ValueError:
            return False
        try:
            float(self.ctrl_kl_1.GetValue())
        except ValueError:
            return False
        sel_mon = self.ctrl_mon.GetSelection()
        sel_qps = self.ctrl_qps.GetSelection()
        if sel_mon == wx.NOT_FOUND or sel_qps == wx.NOT_FOUND:
            return False
        if self.elem_mon[sel_mon]['at'] < self.elem_qps[sel_qps]['at']:
            return False
        return True
