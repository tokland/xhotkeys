#!/usr/bin/python2
import unittest
import subprocess
import signal
import tempfile
import mocks
import sys
import os
import StringIO
import gtk
import time

import xhotkeys
from xhotkeys.gui import main as maingui

config_contents = """
    [calculator]
        binding = <Control><Alt>1
        directory = ~
        command = xcalc

    [abiword]
        binding = <Control><Alt>Button2
        directory = ~/mydocs/
        command = abiword ~/mydocs/readme.txt
"""


def refresh_gui(delay=0):
  while gtk.events_pending():
      gtk.main_iteration_do(block=False)
  time.sleep(delay)       
            
class XhotkeysGUITest(unittest.TestCase):
        
    def setUp(self):
        #configfile = StringIO.StringIO(config_contents)
        configfile = tempfile.NamedTemporaryFile()
        configfile.write(config_contents)
        configfile.flush()
        pidfile = tempfile.NamedTemporaryFile()
        pidfile.close()
        self.gui = maingui.HotkeyListWindow(configfile.name, pidfile.name)
        
    def test_quit_button(self):
        gtk.main_quit = mocks.MockCallable()
        self.gui.widgets["quit_button"].clicked()

    def test_add_button(self):
        maingui.HotkeyWindow.show_all = mocks.MockCallable()
        self.gui.widgets["add_button"].clicked()

    def test_edit_button(self):
        refresh_gui()
        hotkeys_list = self.gui.widgets["hotkeys_list"]
        selection = hotkeys_list.get_treeview().get_selection()
        selection.unselect_all()
        selection.select_path(1)
        self.gui.widgets["edit_button"].clicked()
                                                        
def suite():
    return unittest.TestLoader().loadTestsFromTestCase(XhotkeysGUITest)
 
if __name__ == '__main__':
    unittest.main()
