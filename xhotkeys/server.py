#!/usr/bin/python
"""
Start a xhotkeys server and bind key combinations to commands.

Configuration file (similar to INI-files) should look like this:

    # xhotkeys.conf

    [calculator]
        binding = <ControlMask><Mod1Mask>C
        command = /usr/bin/xcalc
        directory = ~

    [abiword]
        binding = <ControlMask><Mod1Mask>Button2
        command = abiword ~/mydocs/readme.txt
        directory = ~/mydocs/
    
And the daemon can be started from the shell this way:

$ xhotkeysd -f xhotkeys.conf

If the configuration file is not specified, ~/.xhotkeysrc or 
/etc/xhotkeys.conf files will be used. 

Pidfile is stored at ~/.xhotkeys.pid by default.
"""
import os
import re
import sys
import shlex
import signal
import logging
import optparse
import subprocess
import inspect

# Third-party mdoules
import Xlib.X 

# Application modules
from xhotkeys import misc
from xhotkeys.hotkey import Hotkey
import xhotkeys

# Global values
VERSION = "0.1.1"
CONFIGURATION_FILES = ["~/.xhotkeysrc", "/etc/xhotkeys.conf"]
PIDFILE = "~/.xhotkeys.pid"

modifiers_name = {
    Xlib.X.ShiftMask: "Shift",
    Xlib.X.LockMask: "CapsLock", 
    Xlib.X.ControlMask: "Control",
    Xlib.X.Mod1Mask: "Alt",
    Xlib.X.Mod2Mask: "NumLock",
    Xlib.X.Mod3Mask: "ScrollLock",
    Xlib.X.Mod4Mask: "WinKey", 
    Xlib.X.Mod5Mask: "AltGr",
}

modifiers_masks = dict((v.lower(), k) for (k, v) in modifiers_name.items())

class XhotkeysServerReload(Exception):
    """Raised when the configuration must be reload."""
    pass
        
def on_terminate(server, pidfile, signum, frame):
    """Called when the process is asked to terminate."""
    logging.debug("on_terminate: signum=%s, frame=%s" % (signum, frame))
    if pidfile and os.path.isfile(pidfile):
        logging.info("deleting pidfile: %s" % pidfile)
        os.remove(pidfile)
    logging.info("clearing all X grabs")        
    server.clear_grabs()
    logging.info("exiting...")
    sys.exit()
        
def on_sigchild(signum, frame):
    """Called when a child process ends."""
    logging.debug("on_sigchild: signum=%s, frame=%s" % (signum, frame))    
    pid, returncode = os.wait()
    logging.info("process %d terminated (return code %s)" % (pid, returncode))

def on_sighup(signum, frame):
    """Called when a SIGHUP signal is received. Reload configuration"""
    logging.debug("on_sighup: signum=%s, frame=%s" % (signum, frame))
    logging.info("reload exception raised")
    raise XhotkeysServerReload
            
def on_hotkey(command, shell=True, directory=None, **popen_kwargs):
    """
    Called when a configured key binding is detected. Run a command
    with (an optional) shell and setting the current directory if necessary.
    """    
    logging.debug("on_hotkey: %s" % command)
    if directory:
        directory2 = os.path.expanduser(directory)
        logging.info("setting current directory: %s" % directory2)
        os.chdir(directory2)
    try:
        popen = subprocess.Popen(command, shell=shell, **popen_kwargs)
        logging.info("process started with pid %s: %s" % (popen.pid, command))
    except OSError, details:
        logging.error("error on subprocess.Popen: %s" % details)
        return
    return popen
    
def set_signal_handlers(server, pidfile):
    """Set signal handlers."""
    logging.debug("setting signal handlers")
    signal.signal(signal.SIGCHLD, on_sigchild)
    signal.signal(signal.SIGHUP, on_sighup) 
    terminate_callback = misc.partial_function(on_terminate, server, pidfile)
    signal.signal(signal.SIGTERM, terminate_callback)
    signal.signal(signal.SIGINT, terminate_callback)

def configure_server(server, hotkeys):
    """Configure xhotkeys server from config object."""
    for hotkey in hotkeys:
        logging.debug("configuring: %s (%s)" % (hotkey.name, hotkey.get_attributes()))
        if not hotkey.binding:
            logging.warning("empty binding for hotkey: %s" % hotkey.name)
            continue        
        smodifiers, skey = re.search("(<.*>)?(.*)$", hotkey.binding).groups()
        match = re.match("button(\d+)$", skey.lower())
        if match:
            binding_type = "mouse"
            button = int(match.group(1))
        else:
            binding_type = "keyboard"
            if skey.startswith("#"):
                keycode = int(skey[1:])
            else:
                keycode = xhotkeys.get_keycode(skey)
        if smodifiers: 
            modifiers = re.findall("<(.*?)>", smodifiers)
        else: modifiers = []        
        mask = sum(modifiers_masks[modifier.lower()] for modifier in modifiers)
        
        args = [mask, on_hotkey, hotkey.command, True, hotkey.directory]
        if binding_type == "keyboard":            
            logging.info("grabbing key: %s/%s/%s" % (mask, keycode, hotkey.command))
            server.add_key_grab(keycode, *args)
        elif binding_type == "mouse":
            logging.info("grabbing button: %s/%s/%s" % (mask, button, hotkey.command))
            server.add_button_grab(button, *args)
            
def start_server(get_config_callback, pidfile=None, ignore_mask=None):
    """
    Start a xhotkeys server linking key bindings to commands.
        
    get_config_callback should return config, a dictionary-like object. This
    scheme is used to allow easy config reloading. If XhotkeysServerReload 
    exception is raised, config will be reloaded.    
        
    >>> config = {
        "calculator": { 
            "binding": "<ControlMask><Mod1Mask>C",
            "directory": "~",
            "command": "xcalc",
        }
    }
    
    >>> start_server(lambda: config)
    """
    if not write_pidfile(pidfile):
        logging.critical("xhotkeys server already running (see %s)" % pidfile)
        return 2
    logging.info("starting xhotkeys server")
    if ignore_mask is None:
        ignore_mask = Xlib.X.LockMask | Xlib.X.Mod2Mask | Xlib.X.Mod5Mask
    logging.debug("ignore mask value: %s" % ignore_mask)
    server = xhotkeys.XhotkeysServer(ignore_mask)
    set_signal_handlers(server, pidfile)
    while 1:   
        try:
            config = get_config_callback()
            configure_server(server, config)
            server.run()
            break
        except XhotkeysServerReload:
            logging.info("reloading configuration")
            server.clear_grabs()

def get_config(configfile):
    """Load configfile and return a ConfigObj object."""
    if isinstance(configfile, basestring) and not os.path.isfile(configfile):
        logging.warning("configuration file not found: %s" % configfile)
    logging.info("load configuration: %s" % configfile)
    Hotkey.init(configfile)
    return Hotkey.items()

def write_pidfile(pidfile):
    """Write a pidfile with current process PID."""
    logging.debug("checking existence of pidfile: %s" % pidfile)
    if os.path.isfile(pidfile):
        try:
            pid = int(open(pidfile).read())
        except ValueError:
            pid = None
        if pid and os.path.exists("/proc/%s" % pid):
            logging.debug("pidfile exists and pid %s is a running process" % pid)
            return
    logging.debug("creating pidfile: %s" % pidfile)
    pid = os.getpid()
    open(pidfile, "w").write("%d\n" % pid)
    return pid

def show_keyboard_info(ignore_mask, stream=None):
    """Show keyboard info (keys and available modifiers) to stream."""
    if stream is None:
        stream = sys.stdout
    keys = [re.sub("^XK_", "", k) for (k, v) in inspect.getmembers(Xlib.XK) 
        if re.match("^XK_", k)]
    modifiers = ["ShiftMask", "LockMask", "ControlMask", "Mod1Mask", 
        "Mod2Mask", "Mod3Mask", "Mod4Mask", "Mod5Mask"]
    modifiers2 = [mod for mod in modifiers 
        if getattr(Xlib.X, mod) & ~ignore_mask]
    stream.write("Keyboard info:\n\n")
    stream.write("Available key symbols: %s\n\n" % ", ".join(keys))
    stream.write("Available key modifiers: %s\n\n" % ", ".join(modifiers2)) 
                     
def main(args):
    """Parse arguments and start a xhotkeys server reading a given 
    configuration file."""
    usage = """usage: xhotkeyd [options]
        
    Bind keys and mouse combinations to commands for X-Windows"""
    parser = optparse.OptionParser(usage, version=VERSION)  
    parser.add_option('-v', '--verbose', default=1, dest='verbose_level', 
        action="count", help='Increase verbose level')
    parser.add_option('-c', '--config-file', dest='cfile', default=None, 
        metavar='FILE', type='string', help='Alternative configuration file')        
    parser.add_option('-p', '--pid-file', dest='pidfile', default=None, 
        metavar='FILE', type='string', help='Alternative pidfile')
    parser.add_option('-i', '--key-info', dest='keyinfo', default=False, 
        action='store_true', help='Show keyboard info')
                        
    options, args = parser.parse_args(args)
    misc.verbose_level = options.verbose_level
    ignore_mask = Xlib.X.LockMask | Xlib.X.Mod2Mask | Xlib.X.Mod5Mask        
    misc.set_verbose_level(options.verbose_level) 
    
    if options.keyinfo:
        show_keyboard_info(ignore_mask)
        return
        
    # Get absolute path for the files as current directory is likely to change
    configuration_files = [os.path.expanduser(path) for path in 
        [options.cfile] + CONFIGURATION_FILES if path]
    configfile = os.path.abspath(misc.first(configuration_files, os.path.isfile))
    if not configfile:
        args = ", ".join(configuration_files)
        logging.critical("configuration files not found: %s" % args)
        return 1
    pidfile = os.path.abspath(os.path.expanduser(options.pidfile or PIDFILE))
    return start_server(misc.partial_function(get_config, configfile), 
        pidfile, ignore_mask)
        
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
