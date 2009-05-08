#!/usr/bin/python
import os
import re
import sys
import signal
import logging
import optparse
import subprocess

# Third-party modules
import Xlib.X 
import configobj
import gtk
from kiwi.ui.dialogs import yesno

# Application modules
import xhotkeys
from xhotkeys import xhotkeysd
from xhotkeys import misc
from xhotkeys.gui import gtkext
from xhotkeys.hotkey import Hotkey

# Default values
CONFIGURATION_FILE = "~/.xhotkeysrc"
PIDFILE = "~/.xhotkeys.pid"
ERROR, INFO, DEBUG = range(3)

import Xlib.X
import Xlib.display

# TODO:
#
# - add browse button to command and directory
# - tests for GUI
# - use classes for windows

allowed_masks = (Xlib.X.ShiftMask, Xlib.X.ControlMask, Xlib.X.Mod1Mask,
        Xlib.X.Mod4Mask, Xlib.X.Mod5Mask)
        
modifiers_name = dict((k, v) for (k, v) in xhotkeysd.modifiers_name.items()
    if k in allowed_masks)

keycode2name = dict((keycode, modifiers_name[mask]) for (keycode, mask) 
    in xhotkeys.get_keycode_to_modifier_mask_mapping(
    modifiers_name.keys()).iteritems())

keysym2string = xhotkeys.get_keysym_to_string_mapping()

###
        
def get_hotkey_text(modifiers_keycodes, keycode=None):
    display = Xlib.display.Display()    
    names = misc.uniq(keycode2name[kc] for kc in modifiers_keycodes)
    text = "".join("<%s>" % s for s in names)
    if keycode:
        keysym = display.keycode_to_keysym(keycode, 0)
        text += keysym2string.get(keysym, "#%d" % keycode)
    return text
    
def on_binding_entry__key_press_event(entry, event, form_window, button):    
    keycode = event.hardware_keycode
    keysym = event.keyval
    if event.keyval == gtk.keysyms.Escape:
        entry.set_text(entry.old_text)
        button.set_sensitive(True)    
        entry.set_sensitive(False)
        form_window.recording = False    
        button.grab_focus()        
    elif keycode in keycode2name:
        if keycode not in entry.keycodes:
            entry.keycodes.append(keycode)
        text = get_hotkey_text(entry.keycodes)
        entry.set_text(text)    
    else:
        if keysym == Xlib.XK.XK_BackSpace:
            text = ""
        else:
            text = get_hotkey_text(entry.keycodes, keycode)
        entry.set_text(text)
        button.set_sensitive(True)    
        entry.set_sensitive(False)
        form_window.recording = False    
        button.grab_focus()
    entry.stop_emission("key-press-event")

def on_binding_entry__key_release_event(entry, event):    
    keycode = event.hardware_keycode
    keysym = event.keyval
    if keycode in entry.keycodes:
        entry.keycodes.remove(keycode)
    text = get_hotkey_text(entry.keycodes)
    entry.set_text(text)
    entry.stop_emission("key-release-event")

def on_binding_button__clicked(button, form_window, entry):
    button.set_sensitive(False)    
    entry.set_sensitive(True)
    form_window.recording = True    
    entry.grab_focus()
    entry.keycodes = []
    entry.old_text = entry.get_text()
    entry.connect("key-press-event", on_binding_entry__key_press_event, form_window, button)
    entry.connect("key-release-event", on_binding_entry__key_release_event)
     
def hotkey_form(hotkey, hotkeys_list, form_window, save_callback, pidfile):    
    def string2bool(s):
        if isinstance(s, bool):
            return s
        return (s.lower() in ("true", "yes", "on", "1"))
    def bool2string(state):
        return ("on" if state else "off")    
    def attribute(name, widget_class=gtk.Entry):
        functions = {
            gtk.Entry: [gtk.Entry.set_text, gtk.Entry.get_text],
            gtk.CheckButton: [
                lambda widget, s: widget.set_active(string2bool(s)),
                lambda widget: bool2string(widget.get_active()),
            ]                
        }
        hbox = gtk.HBox()
        label = gtk.Label(name.title()+":")
        label.set_width_chars(10)
        label.set_alignment(0.0, 0.5)
        value = getattr(hotkey, name)
        widget = widget_class()
        setter, getter = functions[widget_class]        
        setter(widget, value)            
        hbox.pack_start(label, expand=False)
        hbox.pack_start(widget)
        getter = misc.partial_function(getter, widget)
        return hbox, widget, getter

    buttons_box = gtk.HBox()    
    cancel_button = gtk.Button(stock=gtk.STOCK_CANCEL)
    cancel_button.connect("clicked", on_hotkey_cancel__clicked, form_window)    
    save_button = gtk.Button(stock=gtk.STOCK_SAVE)    
    save_button.connect("clicked", save_callback, 
        form_window, hotkeys_list, hotkey, pidfile)
    
    box = gtk.VBox(spacing=2)
    box.set_border_width(5)
    
    binding_button = gtk.Button(stock=gtk.STOCK_MEDIA_RECORD)
    attributes_view = [
        ("name", gtk.Entry, {}),
        ("command", gtk.Entry, {}),
        ("binding", gtk.Entry, {"sensitive": False, 
                                "action": binding_button}),
        ("directory", gtk.Entry, {}),
    ]
    form_window.form = {}
    form_window.recording = False 
    widgets = {}
    for name, widget_class, options in attributes_view:
        abox, widget, getter = attribute(name, widget_class)
        form_window.form[name] = getter
        if "sensitive" in options:
            widget.set_sensitive(options["sensitive"])
        if "action" in options:
            abox.pack_start(options["action"], expand=False)
        if widget_class is gtk.Entry:
            widget.connect("activate", save_callback, 
                form_window, hotkeys_list, hotkey, pidfile)
        def on_form_widget__changed(entry):
            params = get_params(form_window.form)
            save_button.set_sensitive(hotkey.valid(params))
        widget.connect("changed", on_form_widget__changed)
        box.pack_start(abox)
        widgets[name] = widget
    binding_button.connect("clicked", on_binding_button__clicked, 
        form_window, widgets["binding"])
                    
    buttons_box.pack_start(cancel_button, padding=5)    
    buttons_box.pack_start(save_button, padding=5)
    box.pack_start(buttons_box)
    params = get_params(form_window.form)
    save_button.set_sensitive(hotkey.valid(params))
        
    box.show_all()
    return box

###

def get_params(form):
    return dict((attr, func()) for attr, func in form.iteritems())

def save_hotkey(hotkey, form_window):
    hotkey.update(get_params(form_window.form))
    hotkey.save()
    form_window.destroy()
         
def open_form_window(hotkey, hotkeys_list, save_callback, pidfile):
    form_window = gtk.Window()
    form_window.set_modal(True)
    form = hotkey_form(hotkey, hotkeys_list, form_window, save_callback, pidfile)    
    form_window.add(form)
    form_window.set_resizable(False)
    form_window.show_all()

    def on_form_window_key_press_event(window, event):
        if event.keyval == gtk.keysyms.Escape and not form_window.recording:
            on_hotkey_cancel__clicked(None, form_window)
    form_window.connect("key-press-event", on_form_window_key_press_event)
    return form_window

###

def reload_server(pidfile):
    if pidfile:
        if os.path.isfile(pidfile):
            pid = int(open(pidfile).read())
            os.kill(pid, signal.SIGHUP)
        else:
            logging.warning("pidfile not found: %s" % pidfile)    
    
def on_hotkey_edit_save__clicked(button, form_window, hotkeys_list, hotkey, pidfile):
    if hotkey.valid(get_params(form_window.form)):        
        save_hotkey(hotkey, form_window)
        reload_server(pidfile)

def on_hotkey_add_save__clicked(button, form_window, hotkeys_list, hotkey, pidfile):
    if hotkey.valid(get_params(form_window.form)):
        save_hotkey(hotkey, form_window)
        hotkeys_list.append(hotkey)
        reload_server(pidfile)

def on_hotkey_cancel__clicked(button, form_window):
    form_window.destroy()    

###

def on_hotkey_list__selected(hotkeys_list, hotkey, delete_button, edit_button):
    for button in (edit_button, delete_button):
        button.set_sensitive(bool(hotkey))    

def on_hotkey_list__selection_changed(hotkeys_list, hotkey, window, pidfile):
    open_form_window(hotkey, hotkeys_list, on_hotkey_edit_save__clicked, pidfile)

def on_edit__clicked(button, hotkeys_list, pidfile):
    hotkeys = hotkeys_list.get_selected_rows()
    if len(hotkeys) != 1:
        return
    open_form_window(hotkeys[0], hotkeys_list, on_hotkey_edit_save__clicked, pidfile)

def on_add__clicked(button, hotkeys_list, pidfile):
    hotkey = Hotkey(None, dict(name="name"))
    open_form_window(hotkey, hotkeys_list, on_hotkey_add_save__clicked, pidfile)

def on_delete__clicked(button, window, hotkeys_list, pidfile):
    hotkeys = hotkeys_list.get_selected_rows()
    if not hotkeys:
        return
    warning = "Are you sure you want to delete these hotkey(s)? %s" % \
        ", ".join(x.name for x in hotkeys)
    response = yesno(warning, parent=window, default=gtk.RESPONSE_NO)
    if response == gtk.RESPONSE_YES:
        for hotkey in hotkeys:
            hotkey.delete()
            hotkeys_list.remove(hotkey)
        reload_server(pidfile)

def on_quit__clicked(button):
    gtk.main_quit()
   
###
            
def run(configfile, pidfile):        
    columns = [
        gtkext.Column("name", sorted=True, tooltip="Name of hotkey", width=100),
        gtkext.Column("command", tooltip="Command to run", width=200),
        gtkext.Column("binding", tooltip="Hotkey binding", width=200),
    ]

    window = gtk.Window()
    box = gtk.VBox()
    Hotkey.init(configfile)
    hotkeys = Hotkey.items()        
    hotkeys_list_box = gtkext.ObjectListBox(columns, hotkeys, 
        selection_mode=gtk.SELECTION_MULTIPLE)
    box.pack_start(hotkeys_list_box)
    window.add(box)
    window.connect("destroy", lambda window: gtk.main_quit())
    hotkeys_list = hotkeys_list_box.object_list
    edit_button = gtk.Button(stock=gtk.STOCK_EDIT)
    edit_button.connect("clicked", on_edit__clicked, hotkeys_list, pidfile)
    hotkeys_list_box.actions_box.pack_start(edit_button, expand=False, fill=False)

    delete_button = gtk.Button(stock=gtk.STOCK_DELETE)
    delete_button.connect("clicked", on_delete__clicked, window, hotkeys_list, pidfile)
    hotkeys_list_box.actions_box.pack_start(delete_button, expand=False, fill=False)

    add_button = gtk.Button(stock=gtk.STOCK_ADD)
    add_button.connect("clicked", on_add__clicked, hotkeys_list, pidfile)
    hotkeys_list_box.actions_box.pack_start(add_button, expand=False, fill=False)
    hotkeys_list_box.actions_box.set_spacing(5)

    button = gtk.Button(stock=gtk.STOCK_QUIT)
    button.connect("clicked", on_quit__clicked)
    hotkeys_list_box.actions_box.pack_end(button, expand=False, fill=False)

    def on_window_key_press_event(window, event):
        if event.keyval == gtk.keysyms.Delete:
            on_delete__clicked(None, window, hotkeys_list, pidfile)
    window.connect("key-press-event", on_window_key_press_event)

    hotkeys_list.connect('selection-changed', on_hotkey_list__selected, 
        delete_button, edit_button)
    hotkeys_list.connect('row-activated', on_hotkey_list__selection_changed, 
        window, pidfile)

    window.show_all()
    window.resize(700, 300)
    gtk.main()
                 
def main(args):
    """Open the xhotkeys GUI configurator utility"""
    usage = """usage: xhotkeys-gui [options]
    
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
        
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
