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
global variable ``dvm``.
"""

import sys
import signal
import logging

from spyderlib.widgets.internalshell import InternalShell
from PyQt4 import QtCore, QtGui

from hit.online_control.beamoptikdll import BeamOptikDLL
from hit.online_control.stub import BeamOptikDllProxy


class MainWindow(QtGui.QMainWindow):

    def __init__(self, namespace):
        QtGui.QMainWindow.__init__(self)
        self.shell = InternalShell(self, namespace=namespace)
        # self.shell.interpreter.restore_stds()
        self.shell.set_codecompletion_auto(True)
        self.shell.set_codecompletion_enter(True)
        self.shell.set_calltips(True)
        self.setCentralWidget(self.shell)

    def closeEvent(self, event):
        self.shell.exit_interpreter()
        event.accept()


def main():
    """Invoke GUI application."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QtGui.QApplication(sys.argv)
    ns = {}
    ns['exit'] = sys.exit
    window = MainWindow(ns)

    ns['window'] = window
    # ns['dvm'] = BeamOptikDLL.load_library()
    proxy = BeamOptikDllProxy({})
    ns['dvm'] = BeamOptikDLL(proxy)
    ns['dvm'].GetInterfaceInstance()

    logging.basicConfig(level=logging.INFO)

    window.show()
    app.exec_()


if __name__ == '__main__':
    main()
