#!/usr/bin/python2
import unittest
import xhotkeys
import Xlib.XK
import mocks

def get_mocks():
    display = Xlib.display.Display()
    display.flush = mocks.MockCallable()
    root = display.screen().root
    root.grab_key = mocks.MockCallable()
    root.grab_button = mocks.MockCallable()
    root.ungrab_key = mocks.MockCallable()
    root.ungrab_button = mocks.MockCallable()
    return display, root
            
class XhotkeysTest(unittest.TestCase):
        
    def setUp(self):
        self.display, self.root = get_mocks()
        
    def test_get_keysym(self):
        self.assertEqual(Xlib.XK.XK_Cancel, xhotkeys.get_keysym("Cancel"))
        self.assertEqual(Xlib.XK.XK_A, xhotkeys.get_keysym("A"))
        self.assertEqual(Xlib.XK.XK_Up, xhotkeys.get_keysym("Up"))

    def test_get_mask_combinations(self):
        self.assertEqual([0x0, 0x1, 0x10, 0x11], 
            xhotkeys.get_mask_combinations(0x11))   
        self.assertEqual([0x0, 0x1, 0x2, 0x3, 0x80, 0x81, 0x82, 0x83], 
            xhotkeys.get_mask_combinations(0x83))
            
    def test_ungrab(self):
        xhotkeys.ungrab(self.display, self.root)
        self.assertEqual(1,
            len(mocks.get_calls(self.display.flush)))
        self.assertEqual(1, 
            len(mocks.get_calls(self.root.ungrab_key)))
        self.assertEqual(1, 
            len(mocks.get_calls(self.root.ungrab_button)))
                 
    def test_grab_key(self):
        ignore_masks = xhotkeys.get_mask_combinations(
            Xlib.X.LockMask | Xlib.X.Mod5Mask)
        akc = self.display.keysym_to_keycode(Xlib.XK.XK_A)
        mode = Xlib.X.GrabModeAsync
        x = Xlib.X
        expected_grab_keys = [
            (akc, x.ControlMask | x.Mod1Mask), 
            (akc, x.ControlMask | x.Mod1Mask | x.LockMask), 
            (akc, x.ControlMask | x.Mod1Mask | x.Mod5Mask),
            (akc, x.ControlMask | x.Mod1Mask | x.LockMask | x.Mod5Mask),
        ]
        grab_keys = xhotkeys.grab_key(
            self.display, 
            self.root, 
            keycode=self.display.keysym_to_keycode(Xlib.XK.XK_A), 
            modifiers=Xlib.X.ControlMask | Xlib.X.Mod1Mask,
            ignore_masks=ignore_masks)
        self.assertEqual(expected_grab_keys, grab_keys)

    def test_grab_button(self):
        ignore_masks = xhotkeys.get_mask_combinations(
            Xlib.X.LockMask | Xlib.X.Mod5Mask)
        mode = Xlib.X.GrabModeAsync
        x = Xlib.X
        expected_grab_button = [
            (1, x.ControlMask | x.Mod1Mask), 
            (1, x.ControlMask | x.Mod1Mask | x.LockMask), 
            (1, x.ControlMask | x.Mod1Mask | x.Mod5Mask),
            (1, x.ControlMask | x.Mod1Mask | x.LockMask | x.Mod5Mask),
        ]   
        grab_buttons = xhotkeys.grab_button(
            self.display, 
            self.root, 
            button=1, 
            modifiers=Xlib.X.ControlMask | Xlib.X.Mod1Mask,
            ignore_masks=ignore_masks)
        self.assertEqual(expected_grab_button, grab_buttons)


class XhotkeysServerTest(unittest.TestCase):
    def setUp(self):
        self.display, self.root = get_mocks()
        self.server = xhotkeys.XhotkeysServer(
            Xlib.X.LockMask | Xlib.X.Mod2Mask | Xlib.X.Mod5Mask,
            display=self.display,
            root=self.root)
        
    def test_add_key_grab(self):
        callback = mocks.MockCallable()    
        self.server.add_key_grab(
            keycode=self.server.display.keysym_to_keycode(Xlib.XK.XK_A), 
            modifiers=Xlib.X.ControlMask | Xlib.X.Mod1Mask, 
            callback=callback)
        self.assertEqual(8, len(mocks.get_calls_args(self.root.grab_key)))
        self.assertEqual(1, len(self.server.callbacks))

    def test_add_button_grab(self):
        callback = mocks.MockCallable()    
        self.server.add_button_grab(
            button=3, 
            modifiers=Xlib.X.ControlMask | Xlib.X.Mod1Mask, 
            callback=callback)
        self.assertEqual(8, len(mocks.get_calls_args(self.root.grab_button)))
        self.assertEqual(1, len(self.server.callbacks))

    def test_clear_grabs(self):
        self.server.callbacks = {"forced": 1}            
        self.server.clear_grabs()
        self.assertEqual(0, len(self.server.callbacks))

    def test_run(self):
        akc = self.display.keysym_to_keycode(Xlib.XK.XK_A)
        responses = {
            "pending_events": 
                (mocks.LIST, 
                    [lambda: 3, lambda: 2, lambda: 1, lambda: None]),
            "next_event":
                (mocks.LIST, [
                    lambda: mocks.Struct(type=Xlib.X.KeyPress, 
                               state=Xlib.X.ControlMask | Xlib.X.Mod1Mask,
                               detail=akc),
                    lambda: mocks.Struct(type=Xlib.X.ButtonPress, 
                               state=Xlib.X.ControlMask | Xlib.X.Mod1Mask,
                               detail=3),                                   
                    lambda: mocks.Struct(type=Xlib.X.KeyPress, 
                               state=Xlib.X.ControlMask | Xlib.X.Mod1Mask,
                               detail=akc),
                    
                ]),
        }                                                    
        self.server.display.pending_events = mocks.MockCallable(
            responses=responses["pending_events"])
        self.server.display.next_event = mocks.MockCallable(
            responses=responses["next_event"])
        callback1 = mocks.MockCallable()    
        callback2 = mocks.MockCallable()
        self.server.add_key_grab(
            keycode=self.server.display.keysym_to_keycode(Xlib.XK.XK_A), 
            modifiers=Xlib.X.ControlMask | Xlib.X.Mod1Mask, 
            callback=callback1)
        self.server.add_button_grab(
            button=3, 
            modifiers=Xlib.X.ControlMask | Xlib.X.Mod1Mask, 
            callback=callback2)
        self.server.run(looptime=0.0)
        self.assertEqual(2, len(mocks.get_calls(callback1)))
        self.assertEqual(1, len(mocks.get_calls(callback2)))
        
def suite():
    suite = unittest.TestLoader().loadTestsFromTestCase(XhotkeysTest)
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(XhotkeysServerTest))
    return suite

if __name__ == '__main__':
    unittest.main()
