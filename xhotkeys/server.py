#!/usr/bin/python2
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
import time
import shlex
import signal
import logging
import inspect
import optparse
import subprocess

# Third-party mdoules
import Xlib
from Xlib import X 
try:
    import pyosd
    pyosdobj = pyosd.osd(lines=2)
except ImportError:
    pyosdobj = None

# Application modules
import xhotkeys
from xhotkeys import misc
from xhotkeys.hotkey import Hotkey

# Global values
VERSION = "0.1.3"
CONFIGURATION_FILE = "~/.xhotkeysrc"
PIDFILE = "~/.xhotkeys.pid"

modifiers_name = {
    X.ShiftMask: "Shift",
    X.LockMask: "CapsLock", 
    X.ControlMask: "Control",
    X.Mod1Mask: "Alt",
    X.Mod2Mask: "NumLock",
    X.Mod3Mask: "ScrollLock",
    X.Mod4Mask: "WinKey", 
    X.Mod5Mask: "AltGr",
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

def show_osd(*lines):
    """Show lines in global OSD object."""
    if not pyosdobj:
        return
    pyosdobj.set_pos(pyosd.POS_MID)
    pyosdobj.set_align(pyosd.ALIGN_CENTER)
    pyosdobj.set_colour("#FF0000")
    pyosdobj.set_timeout(1)
    pyosdobj.set_shadow_offset(2)
    pyosdobj.set_font("-*-times-*-r-*-*-*-200-*-*-*-*-*-*")
    for index, line in enumerate(lines):
        pyosdobj.display(line, line=index)
       
def on_hotkey(state, dcombinations, combination):
    """
    Callback run with a combination is detected.
    
    It searches configured combinations to determine which hotkeys is refering.
    """  
    logging.debug("combination: %s" % repr(combination))
    if state.timeout is not None and time.time() > state.timeout:
        logging.debug("combinations expired: %s" % repr(state.current_combination))
        state.current_combination = []
        logging.debug("start new combination")
    state.current_combination.append(combination)
    hotkeys = [(hotkey0, len(sequences) == len(state.current_combination)) 
        for (hotkey0, sequences) in dcombinations.iteritems() 
        if sequences[:len(state.current_combination)] == state.current_combination]
    if len(hotkeys) > 1:
        logging.debug("matching hotkeys: %s" % ", ".join(hk.name for (hk, f) in hotkeys))
        state.timeout = time.time() + 2.0
    elif len(hotkeys) == 1:
        hotkey, finished = hotkeys[0]
        if finished:
            show_osd(hotkey.name, hotkey.command)
            run_command(hotkey.command, directory=hotkey.directory)
            state.current_combination = []
            state.timeout = None
        else:
            logging.debug("matching partial hotkey: %s" % hotkey)
            state.timeout = time.time() + 2.0
    else:
        logging.debug("no combination found for sequence: %s" % state.current_combination)
        state.current_combination = []
        state.timeout = None

def run_command(command, shell=True, directory=None, **popen_kwargs):
    """Run command"""    
    logging.debug("run_command: %s" % command)
    if directory:
        directory2 = os.path.expanduser(directory)
        logging.info("setting current directory: %s" % directory2)
        os.chdir(directory2)
    try:
        popen = subprocess.Popen(command, shell=shell, **popen_kwargs)
        logging.info("process started with pid %s: %s" % (popen.pid, command))
    except OSError, details:
        logging.error("error on subprocess.Popen: %s" % details)
    else:
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
    def get_combination_from_hotkey(hotkey):
        logging.debug("configuring: %s (%s)" % (hotkey.name, hotkey.get_attributes()))
        if not hotkey.binding:
            logging.warning("empty binding for hotkey: %s" % hotkey.name)
            return        
        smodifiers, string_keys = re.search("(<.*>)?(.*)$", hotkey.binding).groups()
        combinations = []
        for string_key in string_keys.split("+"):
          match = re.match("button(\d+)$", string_key.lower())
          if match:
              binding_type = "mouse"
              button = int(match.group(1))
          else:
              binding_type = "keyboard"
              if string_key.startswith("#"):
                  keycode = int(string_key[1:])
              else:
                  keycode = xhotkeys.get_keycode(string_key)
          if smodifiers: 
              modifiers = re.findall("<(.*?)>", smodifiers)
          else: 
              modifiers = []        
          mask = sum(modifiers_masks[modifier.lower()] for modifier in modifiers)
          combination = (binding_type, mask, keycode)
          combinations.append(combination)
        return (hotkey, combinations)
                
    dcombinations = dict(misc.compact(map(get_combination_from_hotkey, hotkeys)))
    state = misc.Struct("combination-state", current_combination=[], timeout=None)
    unique_combinations = misc.uniq(combination 
        for (hotkey, combinations) in dcombinations.iteritems() 
        for combination in combinations)
    for combination in unique_combinations:        
        binding_type, mask, keycode = combination
        callback = misc.partial_function(on_hotkey, state, dcombinations, combination)          
        if binding_type == "keyboard":
            logging.info("grabbing key: %s/%s" % (mask, keycode))
            server.add_key_grab(keycode, mask, callback)
        elif binding_type == "mouse":
            logging.info("grabbing mouse button: %s/%s" % (mask, button))
            server.add_button_grab(button, mask, callback)
            
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
        ignore_mask = X.LockMask | X.Mod2Mask | X.Mod5Mask
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
    xk_keys = inspect.getmembers(Xlib.XK)
    keys = [re.sub("^XK_", "", k) for (k, v) in xk_keys if re.match("^XK_", k)]
    modifiers = ["ShiftMask", "LockMask", "ControlMask", "Mod1Mask", 
        "Mod2Mask", "Mod3Mask", "Mod4Mask", "Mod5Mask"]        
    modifiers2 = [name for (value, name) in modifiers_name.items() if value & ~ignore_mask]
    stream.write("Keys: %s\n" % ", ".join(keys))
    stream.write("Modifiers: %s\n" % ", ".join(modifiers2)) 
                     
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
    ignore_mask = X.LockMask | X.Mod2Mask | X.Mod3Mask | X.Mod5Mask        
    misc.set_verbose_level(options.verbose_level) 
    
    if options.keyinfo:
        show_keyboard_info(ignore_mask)
        return    
    # Get absolute path for the files as current directory is likely to change
    configfile = os.path.abspath(os.path.expanduser(options.cfile or CONFIGURATION_FILE))
    pidfile = os.path.abspath(os.path.expanduser(options.pidfile or PIDFILE))
    get_config_callback = misc.partial_function(get_config, configfile) 
    return start_server(get_config_callback, pidfile, ignore_mask)
        
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
