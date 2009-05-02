#!/usr/bin/python
import os
import re
import sys
import signal
import logging
import optparse
import subprocess

# Third-party mdoules
import Xlib.X 
import configobj
import gtk
from kiwi.ui.dialogs import yesno


# Application modules
import xhotkeys
from xhotkeys import xhotkeysd
from xhotkeys import misc
from xhotkeys.gui import gtkext

# Default values
CONFIGURATION_FILE = "~/.xhotkeysrc"
PIDFILE = "~/.xhotkeys.pid"
ERROR, INFO, DEBUG = range(3)

class Hotkey:
    """Model for hotkey"""
    def __init__(self, config, name, opts):
        self._config = config
        self.name = name
        self.command = opts["command"]
        self.binding = opts["binding"]
        self.directory = opts["directory"]
        self.shell = opts["shell"]

    def delete(self):
        del self._config[self.name]
        self._config.write()
     
def hotkey_selected(object_list, hotkey, delete_button, edit_button):
    for button in (edit_button, delete_button):
        button.set_sensitive(bool(hotkey))    
    if hotkey:
        print "selected:", hotkey.name

def double_click(object_list, hotkey):
    print "double click:", hotkey.name

def on_delete__clicked(button, window, object_list):
    hotkeys = object_list.get_selected_rows()
    if not hotkeys:
        return
    warning = "Are you sure you want to delete these %d hotkey(s)?" % len(hotkeys)
    response = yesno(warning, parent=window, default=gtk.RESPONSE_NO)
    if response == gtk.RESPONSE_YES:
        for hotkey in hotkeys:
            hotkey.delete()
            object_list.remove(hotkey)

def on_quit__clicked(button):
    gtk.main_quit()
            
def run(configfile, pidfile):        
    columns = [
        gtkext.Column("name", sorted=True, tooltip="Name of hotkey", width=100),
        gtkext.Column("command", sorted=False, tooltip="Command to run", width=200),
        gtkext.Column("binding", sorted=False, tooltip="Hotkey binding", width=200),
    ]

    window = gtk.Window()
    box = gtk.VBox()
    config = xhotkeysd.get_config(configfile)
    hotkeys = [Hotkey(config, name, opts) for (name, opts) in config.items()]
    object_list_box = gtkext.ObjectListBox(columns, hotkeys)
    box.pack_start(object_list_box)
    window.add(box)
    window.connect("destroy", lambda window: gtk.main_quit())
    object_list = object_list_box.object_list

    edit_button = gtk.Button(stock=gtk.STOCK_EDIT)
    object_list_box.actions_box.pack_start(edit_button, expand=False, fill=False)

    delete_button = gtk.Button(stock=gtk.STOCK_DELETE)
    delete_button.connect("clicked", on_delete__clicked, window, object_list)
    object_list_box.actions_box.pack_start(delete_button, expand=False, fill=False)

    button = gtk.Button(stock=gtk.STOCK_ADD)
    object_list_box.actions_box.pack_start(button, expand=False, fill=False)

    button = gtk.Button(stock=gtk.STOCK_QUIT)
    button.connect("clicked", on_quit__clicked)
    object_list_box.actions_box.pack_end(button, expand=False, fill=False)

    object_list.connect('selection-changed', hotkey_selected, delete_button, edit_button)
    object_list.connect('double-click', double_click)

    window.show_all()
    window.resize(700, 300)
    gtk.main()
                 
def main(args):
    """Parse arguments and start a xhotkeys server reading a given 
    configuration file."""
    usage = """usage: xhotkeys-gui [options]\n
    Bind keys and mouse combinations to commands for X-Windows""" 
    parser = optparse.OptionParser(usage)  
    parser.add_option('-v', '--verbose', default=0, dest='verbose_level', 
        action="count", help='Increase verbose level (maximum: 3)')
    parser.add_option('-c', '--config-file', dest='cfile', default=None, 
        metavar='FILE', type='string', help='Alternative configuration file')        
    parser.add_option('-p', '--pid-file', dest='pidfile', default=None, 
        metavar='FILE', type='string', help='Alternative pidfile')
                
    options, args = parser.parse_args(args)
    misc.set_verbose_level(options.verbose_level) 
           
    # Get absolute path for the files as current directory is likely to change
    configfile = os.path.expanduser(options.cfile or CONFIGURATION_FILE)
    if not configfile or not os.path.isfile(configfile):
        logging.critical("configuration file not found: %s" % configfile)
        return 1
    pidfile = os.path.abspath(os.path.expanduser(options.pidfile or PIDFILE))
    run(configfile, pidfile)
    #return start_server(misc.partial_function(get_config, configfile), pidfile)
        
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
