#!/usr/bin/python
import unittest
import subprocess
import signal
import tempfile
import mocks
import sys
import os
import StringIO
import Xlib.X

import xhotkeys
from xhotkeys import xhotkeysd

config = {
    "calculator": { 
        "binding": "<Control><Alt>1",
        "directory": "~",
        "command": "xcalc",
    },
    "abiword": {
        "binding": "<Control><Alt>Button2",
        "directory": "~/mydocs/",
        "command": "abiword ~/mydocs/readme.txt",
    },        
}

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
            
class XhotkeysDaemonTest(unittest.TestCase):
        
    def setUp(self):
        self.display = Xlib.display.Display()
        
    def test_get_on_terminate(self):
        server = mocks.Mock()
        server.clear_grabs = mocks.MockCallable()
        fd, pidfile = tempfile.mkstemp()
        sys.exit = mocks.MockCallable()
        xhotkeysd.on_terminate(signum=0, frame=0, server=server, pidfile=pidfile)
        self.assertTrue(mocks.get_calls(server.clear_grabs))        
        self.assertFalse(os.path.exists(pidfile))        
        self.assertTrue(mocks.get_calls(sys.exit))    

    def test_on_sigchild(self):
        os.wait = mocks.MockCallable(responses=(mocks.SCALAR, lambda: (12345, 0)))        
        xhotkeysd.on_sigchild(signum=0, frame=0)

    def test_on_sighup(self):
        self.assertRaises(xhotkeysd.XhotkeysServerReload, 
            xhotkeysd.on_sighup, signum=0, frame=0)

    def test_on_hotkey(self):
        popen = xhotkeysd.on_hotkey(["/bin/echo", "hello"], 
            shell=False, directory=None, stdout=subprocess.PIPE)
        self.assertTrue(popen)
        self.assertEqual(('hello\n', None), popen.communicate())
        
        popen = xhotkeysd.on_hotkey("echo hello", 
            shell=True, directory=None, stdout=subprocess.PIPE)
        self.assertTrue(popen)
        self.assertEqual(('hello\n', None), popen.communicate())

        popen = xhotkeysd.on_hotkey(["./echo", "hello"], 
            shell=False, directory="/bin", stdout=subprocess.PIPE)
        self.assertTrue(popen)
        self.assertEqual(('hello\n', None), popen.communicate())

    def test_set_signal_handlers(self):
        server = xhotkeys.XhotkeysServer(
            Xlib.X.LockMask | Xlib.X.Mod2Mask | Xlib.X.Mod5Mask)
        pidfile = tempfile.NamedTemporaryFile()
        signal.signal = mocks.MockCallable()
        xhotkeysd.set_signal_handlers(server=server, pidfile=pidfile.name)
        self.assertEqual(4, 
            len(mocks.get_calls(signal.signal)))
                                    

    def test_configure_server(self):
        server = xhotkeys.XhotkeysServer(
            Xlib.X.LockMask | Xlib.X.Mod2Mask | Xlib.X.Mod5Mask)

        server.add_key_grab = mocks.MockCallable()
        server.add_button_grab = mocks.MockCallable()
        fd = StringIO.StringIO(config_contents)
        hotkeys = xhotkeysd.get_config(fd)
        xhotkeysd.configure_server(server, hotkeys)
        expected_key_grabs = [(
            self.display.keysym_to_keycode(Xlib.XK.XK_1),
            Xlib.X.ControlMask | Xlib.X.Mod1Mask, 
            xhotkeysd.on_hotkey, 
            'xcalc', 
            True, 
            '~'
        )]
        expected_button_grabs = [(
            2,
            Xlib.X.ControlMask | Xlib.X.Mod1Mask, 
            xhotkeysd.on_hotkey, 
            'abiword ~/mydocs/readme.txt', 
            True, 
            '~/mydocs/'
        )]
        self.assertEqual(expected_button_grabs,
            mocks.get_calls_args(server.add_button_grab))
        self.assertEqual(expected_key_grabs,
            mocks.get_calls_args(server.add_key_grab))
            
    def test_start_server(self):
        def get_config_callback():
            return config
        server = mocks.Mock
        server.add_key_grab = mocks.MockCallable()
        server.add_button_grab = mocks.MockCallable()
        server.add_key_grab = mocks.MockCallable()
        server.run = mocks.MockCallable()
        xhotkeys.XhotkeysServer = mocks.MockCallable(
            responses=(mocks.SCALAR, lambda *args: server))
        pidfile = tempfile.NamedTemporaryFile()                      
        xhotkeysd.start_server(get_config_callback, pidfile=pidfile.name)
                                            
    def test_get_config(self):
        fd = StringIO.StringIO(config_contents)
        items = [(x.name, x.get_attributes()) for x in xhotkeysd.get_config(fd)]
        self.assertEqual(config, dict(items))             

    def test_write_pidfile(self):
        pidfile = tempfile.NamedTemporaryFile()                      
        xhotkeysd.write_pidfile(pidfile.name)
        self.assertEqual(os.getpid(), 
            int(open(pidfile.name).read()))

    def test_show_keyboard_info(self):
        ignore_mask = Xlib.X.LockMask | Xlib.X.Mod2Mask | Xlib.X.Mod5Mask
        fd = StringIO.StringIO()    
        xhotkeysd.show_keyboard_info(ignore_mask, stream=fd)
        self.assertTrue(fd.getvalue())
        
    def test_main(self):
        conf = tempfile.NamedTemporaryFile()
        conf.write(config_contents)        
        xhotkeysd.start_server = mocks.MockCallable()
        xhotkeysd.main(["-c", conf.name])
        self.assertTrue(mocks.get_calls_args(xhotkeysd.start_server)) 

    def test_main_keyboard_info(self):
        sys.stdout = StringIO.StringIO()
        xhotkeysd.main(["-i"])
        self.assertTrue(sys.stdout.getvalue())
        
                                                        
def suite():
    return unittest.TestLoader().loadTestsFromTestCase(XhotkeysDaemonTest)
 
if __name__ == '__main__':
    unittest.main()
