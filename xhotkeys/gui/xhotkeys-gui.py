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

# - TODO: Status widget (with xhotkeys pid and configfile)

ALLOWED_MASKS = [
    Xlib.X.ShiftMask, 
    Xlib.X.ControlMask, 
    Xlib.X.Mod1Mask,
    Xlib.X.Mod4Mask, 
    Xlib.X.Mod5Mask,
]

def get_params(form):
    return dict((attr, func()) for attr, func in form.iteritems())

class HotkeyWindow(gtk.Window):
    """Window with hotkey form: name, command, binding, directory.
    
    Actions: Cancel, Save.
    """     

    def __init__(self, action, hotkey, hotkeys_list, pidfile, on_save):
        gtk.Window.__init__(self)
        self.hotkey = hotkey
        self.hotkeys_list = hotkeys_list
        self.pidfile = pidfile
        self.on_save = on_save
        self.display = Xlib.display.Display()
        
        self.form = {}
        self.recording = False
        
        # Modifiers and keycode/keysyms mappings
        modifiers_name = dict((k, v) for (k, v) 
            in xhotkeysd.modifiers_name.items() if k in ALLOWED_MASKS)
        self.keycode2name = dict((keycode, modifiers_name[mask]) for (keycode, mask) 
            in xhotkeys.get_keycode_to_modifier_mask_mapping(
            modifiers_name.keys()).iteritems())
        self.keysym2string = xhotkeys.get_keysym_to_string_mapping()

        
        # Create form window
        cancel_callback = self.on_hotkey_cancel__clicked
        self.set_modal(True)
        form = self.hotkey_form(hotkey, hotkeys_list, 
            self.on_hotkey_save__clicked, cancel_callback, pidfile, action)    
        self.add(form)
        self.set_resizable(False)                    
        def on_form_window_key_press_event(window, event):
            if event.keyval == gtk.keysyms.Escape and not self.recording:
                cancel_callback(None)
        self.connect("key-press-event", on_form_window_key_press_event)
        self.set_title("Hotkey configuration")
                            
    def get_hotkey_text(self, modifiers_keycodes, keycode=None):        
        names = misc.uniq(self.keycode2name[kc] for kc in modifiers_keycodes)
        text = "".join("<%s>" % s for s in names)
        if keycode:
            keysym = self.display.keycode_to_keysym(keycode, 0)
            text += self.keysym2string.get(keysym, "#%d" % keycode)
        return text

    def start_recording(self, button, entry):        
        button.set_sensitive(False)    
        entry.set_sensitive(True)
        self.recording = True    
        entry.grab_focus()
        entry.old_text = entry.get_text()
        entry.set_text("Grabbing...")
        entry.keycodes = []

    def stop_recording(self, text, entry, button):
        entry.set_text(text)
        button.set_sensitive(True)    
        entry.set_sensitive(False)
        button.grab_focus()
        self.recording = False    

    def on_binding_entry__button_press_event(self, entry, event, button):
        if not entry.keycodes:
            return
        text = self.get_hotkey_text(entry.keycodes) + "Button%d" % event.button        
        self.stop_recording(text, entry, button)
        entry.stop_emission("button-press-event")
                
    def on_binding_entry__key_press_event(self, entry, event, button):    
        keycode = event.hardware_keycode
        keysym = event.keyval
        if event.keyval == gtk.keysyms.Escape:
            self.stop_recording(entry.old_text, entry, button)        
        elif keycode in self.keycode2name:
            if keycode not in entry.keycodes:
                entry.keycodes.append(keycode)
            text = self.get_hotkey_text(entry.keycodes)
            entry.set_text(text)    
        else:
            text = ("" if keysym == Xlib.XK.XK_BackSpace else
                self.get_hotkey_text(entry.keycodes, keycode))
            self.stop_recording(text, entry, button)
        entry.stop_emission("key-press-event")

    def on_binding_entry__key_release_event(self, entry, event):    
        keycode = event.hardware_keycode
        keysym = event.keyval
        if keycode in entry.keycodes:
            entry.keycodes.remove(keycode)
        text = self.get_hotkey_text(entry.keycodes)
        entry.set_text(text)
        entry.stop_emission("key-release-event")

    def on_binding_button__clicked(self, button, entry):
        self.start_recording(button, entry)    
        entry.connect("key-press-event", self.on_binding_entry__key_press_event, 
            button)
        entry.connect("key-release-event", self.on_binding_entry__key_release_event)
        entry.connect("button-press-event", self.on_binding_entry__button_press_event, button)


    def hotkey_form(self, hotkey, hotkeys_list,  
            save_callback, cancel_callback, pidfile, action):    
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
        cancel_button.connect("clicked", cancel_callback)    
        save_button = gtk.Button(stock=gtk.STOCK_SAVE)
        def on_save_button__clicked(button):
            save_callback(get_params(self.form), action)
        save_button.connect("clicked", on_save_button__clicked)        
        box = gtk.VBox(spacing=2)
        box.set_border_width(5)
        
        binding_button = gtk.Button(stock=gtk.STOCK_MEDIA_RECORD)
        browse_directory_button = gtk.Button(stock=gtk.STOCK_OPEN)
        
        attributes_view = [
            ("name", gtk.Entry, {}),
            ("command", gtk.Entry, {}),
            ("binding", gtk.Entry, {"sensitive": False, 
                                    "action": binding_button}),
            ("directory", gtk.Entry, {"action": browse_directory_button}),
        ]
        widgets = {}
        for name, widget_class, options in attributes_view:
            abox, widget, getter = attribute(name, widget_class)
            self.form[name] = getter
            if "sensitive" in options:
                widget.set_sensitive(options["sensitive"])
            if "action" in options:
                abox.pack_start(options["action"], expand=False)
            if widget_class is gtk.Entry:
                widget.connect("activate", on_save_button__clicked)
            def on_form_widget__changed(entry):
                params = get_params(self.form)
                save_button.set_sensitive(hotkey.valid(params))
            widget.connect("changed", on_form_widget__changed)
            box.pack_start(abox)
            widgets[name] = widget
        widgets["name"].set_width_chars(40)
        binding_button.connect("clicked", self.on_binding_button__clicked, 
            widgets["binding"])
        browse_directory_button.connect("clicked", 
            self.on_browse_directory__clicked, widgets["directory"])
                        
        buttons_box.pack_start(cancel_button, padding=5)
        buttons_box.pack_start(save_button, padding=5)
        box.pack_start(buttons_box)
        params = get_params(self.form)
        save_button.set_sensitive(hotkey.valid(params))            
        return box

    def save_hotkey(self, hotkey, params):
        hotkey.update(params)
        hotkey.save()
        self.destroy()
                    
    def on_hotkey_save__clicked(self, params, action):
        if self.hotkey.valid(params):        
            self.save_hotkey(self.hotkey, params)
            self.on_save(self.hotkey, action)

    def on_hotkey_cancel__clicked(self, button):
        self.destroy()    
                

    def on_browse_directory__clicked(self, button, entry):
        directory = os.path.expanduser(entry.get_text())
        if not os.path.isdir(directory):
            directory = os.path.expanduser("~")                         
        action_info = (gtk.STOCK_OPEN, gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, 
            "Select directory where the command will start")            
        dialog = gtkext.EasyFileChooserDialog(action_info, directory)
        if dialog.run() == gtk.RESPONSE_ACCEPT:
            directory = dialog.get_filename()
            entry.set_text(directory)
        dialog.destroy()
           
###

class HotkeyListWindow(gtk.Window):
    """Hotkey table listing.
    
    Actions: Edit, Delete, Add and Exit.
    """
    def __init__(self, configfile, pidfile, icon):
        self.configfile = configfile
        self.pidfile = pidfile
        
        gtk.Window.__init__(self)        
        columns = [
            gtkext.Column("name", sorted=True, tooltip="Name of hotkey", width=100),
            gtkext.Column("command", tooltip="Command to run", width=200),
            gtkext.Column("binding", tooltip="Hotkey binding", width=200),
        ]

        box = gtk.VBox()
        Hotkey.init(configfile)
        hotkeys = Hotkey.items()        
        hotkeys_list_box = gtkext.ObjectListBox(columns, hotkeys, 
            selection_mode=gtk.SELECTION_MULTIPLE)
        box.pack_start(hotkeys_list_box)
        self.add(box)
        self.connect("destroy", lambda window: gtk.main_quit())
        hotkeys_list = hotkeys_list_box.object_list
        edit_button = gtk.Button(stock=gtk.STOCK_EDIT)
        edit_button.connect("clicked", self.on_edit__clicked, hotkeys_list)
        hotkeys_list_box.actions_box.pack_start(edit_button, expand=False, fill=False)

        delete_button = gtk.Button(stock=gtk.STOCK_DELETE)
        delete_button.connect("clicked", self.on_delete__clicked, hotkeys_list)
        hotkeys_list_box.actions_box.pack_start(delete_button, expand=False, fill=False)

        add_button = gtk.Button(stock=gtk.STOCK_ADD)
        add_button.connect("clicked", self.on_add__clicked, hotkeys_list)
        hotkeys_list_box.actions_box.pack_start(add_button, expand=False, fill=False)
        hotkeys_list_box.actions_box.set_spacing(5)

        button = gtk.Button(stock=gtk.STOCK_QUIT)
        button.connect("clicked", self.on_quit__clicked)
        hotkeys_list_box.actions_box.pack_end(button, expand=False, fill=False)

        def on_window_key_press_event(window, event):
            if event.keyval == gtk.keysyms.Delete:
                self.on_delete__clicked(None, hotkeys_list)
        self.connect("key-press-event", on_window_key_press_event)

        hotkeys_list.connect('selection-changed', self.on_hotkey_list__selected, 
            delete_button, edit_button)
        hotkeys_list.connect('row-activated', self.on_hotkey_list__selection_changed, 
            self)
        self.set_icon(gtk.gdk.pixbuf_new_from_file(icon))
        self.set_title("Xhotkeys configuration")
            
    def on_save(self, hotkeys_list, hotkey, action):
        if action == "new":
            hotkeys_list.append(hotkey)
        self.reload_server(self.pidfile)

    def reload_server(self, pidfile):
        if pidfile:
            if os.path.isfile(pidfile):
                pid = int(open(pidfile).read())
                os.kill(pid, signal.SIGHUP)
            else:
                logging.warning("pidfile not found: %s" % pidfile)
                    
    def on_hotkey_list__selected(self, hotkeys_list, hotkey, delete_button, edit_button):
        for button in [edit_button, delete_button]:
            button.set_sensitive(bool(hotkey))    
       
    def on_hotkey_list__selection_changed(self, hotkeys_list, hotkey, window):
        self.open_hotkey_window(hotkeys_list, hotkey)

    def on_edit__clicked(self, button, hotkeys_list):
        hotkeys = hotkeys_list.get_selected_rows()
        if not hotkeys:
            return
        self.open_hotkey_window(hotkeys_list, hotkeys[0])

    def open_hotkey_window(self, hotkeys_list, hotkey):        
        window = HotkeyWindow("edit", hotkey, hotkeys_list, self.pidfile,
            misc.partial_function(self.on_save, hotkeys_list))
        window.show_all()

    def on_add__clicked(self, button, hotkeys_list):
        hotkey = Hotkey(None, dict(name="name"))
        window = HotkeyWindow("new", hotkey, hotkeys_list, self.pidfile,
            misc.partial_function(self.on_save, hotkeys_list))
        window.show_all()
        
    def on_delete__clicked(self, button, hotkeys_list):
        hotkeys = hotkeys_list.get_selected_rows()
        if not hotkeys:
            return
        warning = "Are you sure you want to delete these hotkey(s)?\n%s" % \
            ", ".join(x.name for x in hotkeys)
        response = yesno(warning, parent=self, default=gtk.RESPONSE_NO)        
        if response == gtk.RESPONSE_YES:
            for hotkey in hotkeys:
                hotkey.delete()
                hotkeys_list.remove(hotkey)
            self.reload_server(self.pidfile)

    def on_quit__clicked(self, button):
        gtk.main_quit()
           
###
                 
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
    pidfile = os.path.abspath(os.path.expanduser(options.pidfile or PIDFILE))
    directory = ("/usr/share/xhotkeys" if __file__.startswith("/") else "pics")
    icon = os.path.join(directory, "xhotkeys.xpm")
    window = HotkeyListWindow(configfile, pidfile, icon)    
    window.show_all()
    window.resize(700, 300)
    gtk.main()
        
        
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
