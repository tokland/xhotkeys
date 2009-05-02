#!/usr/bin/python
import os
import re
import sys
import signal
import optparse
import subprocess

# Third-party mdoules
import Xlib.X 
import configobj

# Application modules
import xhotkeys
from xhotkeys import misc
from xhotkeys import gtkext

# Default values
CONFIGURATION_FILE = "~/.xhotkeysrc"
PIDFILE = "~/.xhotkeys.pid"
ERROR, INFO, DEBUG = range(3)

import gtk
from kiwi.ui.objectlist import Column

      
def news_selected(object_list, item, delete_button, edit_button):
    for button in (edit_button, delete_button):
        button.set_sensitive(bool(item))    
    if item:
        print "selected:", item.title

def double_click(object_list, item):
    print "double click:", item.title

def on_delete__clicked(button, window, object_list):    
    items = object_list.get_selected_rows()
    if not items:
        return
    warning = "Are you sure you want to delete these %d item(s)?" % len(items)
    response = yesno(warning, parent=window, default=gtk.RESPONSE_NO)
    if response == gtk.RESPONSE_YES:
        for item in items:
            object_list.remove(item)

class NewsItem:
    def __init__(self, title, author, url):
        self.title, self.author, self.url = title, author, url
        
news = [
    NewsItem("Smallpox Vaccinations for EVERYONE", "JRoyale",
        "http://www.pigdog.org/auto/Power_Corrupts/link/2700.html"),
    NewsItem("Is that uranium in your pocket or are you just happy to see me?",
        "Baron Earl", "http://www.pigdog.org/auto/bad_people/link/2699.html"),
    NewsItem("Cut 'n Paste", "Baron Earl",
        "http://www.pigdog.org/auto/ArtFux/link/2690.html"),
    NewsItem("A Slippery Exit", "Reverend CyberSatan",
        "http://www.pigdog.org/auto/TheCorporateFuck/link/2683.html"),
    NewsItem("Those Crazy Dutch Have Resurrected Elvis", "Miss Conduct",
        "http://www.pigdog.org/auto/viva_la_musica/link/2678.html"),
]

my_columns = [
    Column("title", sorted=False, tooltip="Title of article", width=150),
    Column("author", tooltip="Author of article"),
    Column("url", title="Address", visible=False, tooltip="Address of article"),
]

window = gtk.Window()
box = gtk.VBox()
object_list_box = gtkext.ObjectListBox(my_columns, news)
box.pack_start(object_list_box)
window.add(box)
window.connect("destroy", lambda w: gtk.main_quit())
object_list = object_list_box.object_list

edit_button = gtk.Button(stock=gtk.STOCK_EDIT)
object_list_box.actions_box.pack_start(edit_button, expand=False, fill=False)

delete_button = gtk.Button(stock=gtk.STOCK_DELETE)
delete_button.connect("clicked", on_delete__clicked, window, object_list)
object_list_box.actions_box.pack_start(delete_button, expand=False, fill=False)

button = gtk.Button(stock=gtk.STOCK_ADD)
object_list_box.actions_box.pack_start(button, expand=False, fill=False)

button = gtk.Button(stock=gtk.STOCK_QUIT)
object_list_box.actions_box.pack_end(button, expand=False, fill=False)

button = gtk.Button(stock=gtk.STOCK_SAVE)
object_list_box.actions_box.pack_end(button, expand=False, fill=False)

button = gtk.Button(stock=gtk.STOCK_REVERT_TO_SAVED)
object_list_box.actions_box.pack_end(button, expand=False, fill=False)

object_list.connect('selection-changed', news_selected, delete_button, edit_button)
object_list.connect('double-click', double_click)

window.show_all()
window.resize(400, 300)
gtk.main()
sys.exit()

def get_config(configfile):
    """Load configfile and return a ConfigObj object."""
    debug(INFO, "load configuration: %s" % configfile)
    config = configobj.ConfigObj(configfile)
    return config     

def write_pidfile(path):
    """Write a pidfile with current process PID."""
    debug(DEBUG, "creating pidfile: %s" % path)
    open(path, "w").write("%d\n" % os.getpid())
                 
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
    misc.verbose_level = options.verbose_level
        
    # Use misc.debug as debug function for all this module
    global debug
    debug = misc.debug
    # Get absolute path for the files as current directory is likely to change
    configfile = os.path.expanduser(options.cfile or CONFIGURATION_FILE)
    if not configfile or not os.path.isfile(configfile):
        debug(ERROR, "configuration file not found: %s" % configfile)
        return 1
    pidfile = os.path.abspath(os.path.expanduser(options.pidfile or PIDFILE))
    print configfile, pidfile
    #return start_server(misc.partial_function(get_config, configfile), pidfile)
        
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
