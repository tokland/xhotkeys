#!/usr/bin/python
"""
Start a xhotkeys server and bind key combinations to commands.

Configuration file (similar to INI-files) should look like this:

    # xhotkeys.conf

    [calculator]
        binding-type = keyboard
        binding = <ControlMask><Mod1Mask>C
        directory = ~
        command = /usr/bin/xcalc
        shell = no

    [abiword]
        binding-type = mouse
        binding = <ControlMask><Mod1Mask>2
        directory = ~/mydocs/
        command = abiword ~/mydocs/readme.txt
        shell = yes
    
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
import configobj

# Application modules
from xhotkeys import misc
import xhotkeys

# Global values
VERSION = "0.0.1" 
CONFIGURATION_FILES = ["~/.xhotkeysrc", "/etc/xhotkeys.conf"]
PIDFILE = "~/.xhotkeys.pid"

# Verbose levels
VERBOSE_LEVELS = {
    0: logging.CRITICAL,
    1: logging.ERROR,
    2: logging.WARNING,
    3: logging.INFO,
    4: logging.DEBUG,
}

class XhotkeysServerReload(Exception):
    """Raised when the configuration must be reload."""
    pass

def set_verbose_level(verbose_level):
    """Set verbose level for logging.
    
    See VERBOSE_LEVELS constant for allowed values."""
    nlevel = max(0, min(verbose_level, len(VERBOSE_LEVELS)-1))
    level = VERBOSE_LEVELS[nlevel]
    logging.basicConfig(level=level, stream=sys.stderr,  
        format='%(levelname)s: %(message)s')
        
def on_terminate(signum, frame, server, pidfile):
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
            
def on_hotkey(command, shell=False, directory=None, **popen_kwargs):
    """
    Called when a configured key binding is detected. Run a command
    with (an optional) shell and setting the current directory if necessary.
    """    
    logging.debug("on_hotkey: %s" % command)
    if directory:
        directory2 = os.path.expanduser(directory)
        logging.info("setting directory: %s" % directory2)
        os.chdir(directory2)
    popen = subprocess.Popen(command, shell=shell, **popen_kwargs)
    logging.info("process started with pid %s: %s" % (popen.pid, command))
    return popen
    
def set_signal_handlers(server, pidfile):
    """Set signal handlers."""
    logging.debug("setting signal handlers")
    signal.signal(signal.SIGCHLD, on_sigchild)
    signal.signal(signal.SIGHUP, on_sighup) 
    terminate_callback = misc.partial_function(on_terminate, server, pidfile)
    signal.signal(signal.SIGTERM, terminate_callback)
    signal.signal(signal.SIGINT, terminate_callback)

def configure_server(server, config):
    """Configure xhotkeys server from config object."""
    for item, options in config.iteritems():
        logging.debug("configuring: %s (%s)" % (item, options))
        smodifiers, skey = re.search("(<.*>)(.*)$", options["binding"]).groups()
        modifiers = re.findall("<(.*?)>", smodifiers)
        mask = sum(getattr(Xlib.X, modifier) for modifier in modifiers)
        
        shell = (options["shell"].lower() in ("true", "yes", "on", "1"))
        command = (options["command"] if shell else 
            shlex.split(options["command"]))
        directory = options["directory"]
        binding_type = options.get("binding-type", "keyboard")
        if binding_type == "keyboard":
            logging.info("grabbing key: %s/%s/%s" % (mask, command, shell))
            server.add_key_grab(xhotkeys.get_keysym(skey), mask, on_hotkey, 
                command, shell, directory)
        elif binding_type == "mouse":
            logging.info("button: %s/%s/%s" % (mask, command, shell))
            server.add_button_grab(int(skey), mask, on_hotkey, command, 
                shell, directory)
            
def start_server(get_config_callback, pidfile=None, ignore_mask=None):
    """
    Start a xhotkeys server linking key bindings to commands.
        
    get_config_callback should return config, a dictionary-like object. This
    scheme is used to allow easy config reloading. If XhotkeysServerReload 
    exception is raised, config will be reloaded.    
        
    >>> config = {
        "calculator": { 
            "binding": "<ControlMask><Mod1Mask>C",
            "binding-type": "keyboard",
            "directory": "~",
            "command": "xcalc",
            "shell": "1",
        }
    }
    
    >>> start_server(lambda: config)
    """
    write_pidfile(pidfile)
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
    return configobj.ConfigObj(configfile)

def write_pidfile(path):
    """Write a pidfile with current process PID."""
    logging.debug("creating pidfile: %s" % path)
    open(path, "w").write("%d\n" % os.getpid())

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
    set_verbose_level(options.verbose_level) 
    
    if options.keyinfo:
        show_keyboard_info(ignore_mask)
        return
        
    # Get absolute path for the files as current directory is likely to change
    configuration_files = [os.path.expanduser(path) for path in 
        [options.cfile] + CONFIGURATION_FILES if path]
    configfile = misc.first(configuration_files, os.path.isfile)
    if not configfile:
        args = ", ".join(configuration_files)
        logging.critical("configuration files not found: %s" % args)
        return 1
    pidfile = os.path.abspath(os.path.expanduser(options.pidfile or PIDFILE))
    return start_server(misc.partial_function(get_config, configfile), 
        pidfile, ignore_mask)
        
if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
