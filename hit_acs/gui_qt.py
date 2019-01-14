"""
Start an interactive testing console for the BeamOptikDLL wrapper.

Note that this cannot equivalently be done without the GUI: The
'BeamOptikDLL.dll' library creates an application window and therefore
requires a main loop to process window messages. This module uses PyQt4_
to create the main loop and spyderlib_ to provide an interactive python
console.

.. _PyQt4: https://riverbankcomputing.com/software/pyqt/intro
.. _spyderlib: https://github.com/spyder-ide/spyder

The DLL is connected on startup and the wrapper object is stored in the
global variable ``dll``.
"""

from __future__ import absolute_import

import sys
import signal
import logging

from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.qt import QtCore, QtGui

from .beamoptikdll import BeamOptikDLL


def create(user_ns):
    """Create an in-process kernel."""
    manager = QtInProcessKernelManager()
    manager.start_kernel(show_banner=False)
    kernel = manager.kernel
    kernel.gui = 'qt4'
    kernel.user_ns = user_ns

    client = manager.client()
    client.start_channels()

    widget = RichJupyterWidget()
    widget.kernel_manager = manager
    widget.kernel_client = client
    return widget


class MainWindow(QtGui.QMainWindow):

    def __init__(self, namespace):
        QtGui.QMainWindow.__init__(self)
        self.ns = namespace
        self.shell = create(namespace)
        # self.shell.interpreter.restore_stds()
        self.setCentralWidget(self.shell)
        QtCore.QTimer.singleShot(0, self.load_dll)

    def closeEvent(self, event):
        event.accept()

    def load_dll(self):
        ns = self.ns
        ns['window'] = self
        ns['dll'] = BeamOptikDLL()
        ns['dll'].GetInterfaceInstance()


def main():
    """Invoke GUI application."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtGui.QApplication(sys.argv)
    ns = {}
    ns['exit'] = sys.exit
    window = MainWindow(ns)

    logging.basicConfig(level=logging.INFO)

    window.show()
    app.exec_()


if __name__ == '__main__':
    main()
