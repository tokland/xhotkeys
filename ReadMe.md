# Introduction #

Xhotkeys provides a simple and easily configurable hotkey launcher for the X-Window System, binding keys and mouse buttons to configurable commands. It should work on all desktops (Gnome, KDE, Xfce, ...) available for the UNIX-like operating systems (GNU/Linux, BSD, ...).

# Dependencies #

  * [Python](http://www.python.org) (version >= 2.5)
  * [Kiwi](http://www.async.com.br/projects/kiwi/).

# Install #

```
$ sudo python setup.py install
```

# Manual configuration #

Example of configuration file (/home/youruser/.xhotkeysrc):

```
[calculator]
    binding = <Control>2
    directory = ~
    command = xcalc

[abiword]
    binding = <Control><Alt>Button3
    directory = ~/docs
    command = abiword
```

Allowed modifiers: _Control_, _Alt_, _Shift_, _WinKey_, _AltGr_

# GUI configuration #

```
$ xhotkeys-gui
```

# Start the daemon #

```
$ xhotkeysd
```

To launch _xhotkeysd_ on X boot, configure the sessions of you desktop environment.