#!/usr/bin/python
"""
Listen to keyboard and mouse combinations and run callbacks. Example:

>>> import xhotkeys
>>> import Xlib.XK
>>> import Xlib.X
>>> 
>>> def callback(arg):
>>>     print "callback:", arg
>>>
>>> ignore_mask = Xlib.X.LockMask | Xlib.X.Mod2Mask | Xlib.X.Mod5Mask
>>> server = xhotkeys.XhotkeysServer(ignore_mask)
>>> server.add_key_grab(Xlib.XK.XK_1, Xlib.X.ControlMask, callback, 1) 
>>> server.add_button_grab(1, Xlib.X.ControlMask | Xlib.X.Mod1Mask, callback, 3)
>>> server.run() 
"""   
import time

# Xlib modules
import Xlib.display
import Xlib.XK
import Xlib.X

def get_keysym(string):
    """Return keysymbol from key string.
     
    >>> get_keysym("Cancel")
    Xlib.XK.XK_Cancel
    """
    return getattr(Xlib.XK, "XK_" + string)
    
def get_mask_combinations(mask):
    """Get all combinations for a mask"""
    return [x for x in xrange(mask+1) if not (x & ~mask)]
                    
def ungrab(display, root):
    """Ungrab all keycoard bindings"""
    display.flush()
    root.ungrab_key(Xlib.X.AnyKey, Xlib.X.AnyModifier)
    root.ungrab_button(Xlib.X.AnyButton, Xlib.X.AnyModifier)
            
def grab_key(display, root, keysym, modifiers, ignore_masks):
    """Grab a key symbol (with an optional modifier)"""
    def _grab(keycode, mode):
        for mask in ignore_masks:
            mod = modifiers | mask
            root.grab_key(keycode, mod, 0, mode, mode)
            yield (keycode, mod)
    keycode = display.keysym_to_keycode(keysym)
    return list(_grab(keycode=keycode, mode=Xlib.X.GrabModeAsync))

def grab_button(display, root, button, modifiers, ignore_masks):
    """Grab a key symbol (with an optional modifier)"""
    def _grab(button, mode):
        for mask in ignore_masks:
            mod = modifiers | mask
            root.grab_button(button, mod, root, Xlib.X.ButtonPressMask, 
                mode, mode, 0, 0)
            yield (button, mod)
    return list(_grab(button=button, mode=Xlib.X.GrabModeAsync))
            

class XhotkeysServer:
    """
    Listen to keyboard and mouse hotkeys and run callbacks.
    
    ignore_mask is the mask to apply to event to ignore 
    some states. Allowed values are: 
    
    Xlib.X.ShiftMask: Shift
    Xlib.X.LockMask: Caps Lock
    Xlib.X.ControlMask: Control
    Xlib.X.Mod1Mask: Alt
    Xlib.X.Mod2Mask: Num Lock
    Xlib.X.Mod3Mask: (normally unused)
    Xlib.X.Mod4Mask:,Window$ Key
    Xlib.X.Mod5Mask: Scroll Lock
    
    >>> ignore_mask = Xlib.X.LockMask | Xlib.X.Mod2Mask | Xlib.X.Mod5Mask
    >>> server = xhotkeys.XhotkeysServer(ignore_mask)
    >>> server.add_key_grab(Xlib.XK.XK_1, Xlib.X.ControlMask, callback, 1) 
    >>> server.add_button_grab(1, Xlib.X.ControlMask | Xlib.X.Mod1Mask, callback, 3)
    >>> server.run() 
    """

    accepted_event_types = [Xlib.X.KeyPress, Xlib.X.ButtonPress]

    def _add_callback(self, event_type, code, modifiers, cbfun, cbargs):
        """Add a callback to callbacks dictionary."""
        key = (event_type, code, modifiers)
        self.callbacks[key] = (cbfun, cbargs)

    # Public interface
    
    def __init__(self, ignore_mask, display=None, root=None):
        """Init xhotkeys server and callbacks data"""
        self.display = display or Xlib.display.Display()
        self.root = root or self.display.screen().root
        self.ignore_mask = ignore_mask
        self.ignore_masks = get_mask_combinations(ignore_mask)
        self.callbacks = {}
    
    def add_key_grab(self, keysym, modifiers, callback, *args):
        """Add a keyboard grab to server. Look Xlib.X for key symbols"""        
        keycode = self.display.keysym_to_keycode(keysym)
        grab_key(self.display, self.root, keysym, modifiers, self.ignore_masks)
        self._add_callback(Xlib.X.KeyPress, keycode, modifiers, callback, args)

    def add_button_grab(self, button, modifiers, callback, *args):
        """Add a button (normally, a mouse button) grab to server"""
        grab_button(self.display, self.root, button, modifiers, self.ignore_masks)
        self._add_callback(Xlib.X.ButtonPress, button, modifiers, callback, args)
                        
    def clear_grabs(self):
        """Clear all grabs and its callbacks"""
        ungrab(self.display, self.root)
        self.callbacks.clear()
        
    def run(self, looptime=0.1):        
        """Run the server calling the configured callbacks on events"""
        while 1:
            pending_events = self.display.pending_events()
            if pending_events is None:
                break
            elif not pending_events:
                time.sleep(looptime)
                continue
            event = self.display.next_event()
            if (not hasattr(event, "type") or 
                    event.type not in self.accepted_event_types): 
                continue
            mask = event.state & ~self.ignore_mask
            key = (event.type, event.detail, mask)
            try:
                callback, args = self.callbacks[key]
                callback(*args)
            except KeyError:
                print "warning: undefined event received: %s" % list(key)        
