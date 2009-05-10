#!/usr/bin/python
"""Run command on hotkeys (keyboard & mouse) for X-Windows"""

# Copyright (c) 2008-2009 Arnau Sanchez <tokland@gmail.com>

# This file is part of xhotkeys.

# This script is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this software.  If not, see <http://www.gnu.org/licenses/>

from distutils.core import setup

setup(
    name="xhotkeys",
    description="Run command on hotkeys (keyboard & mouse) for X-Windows",
    author="Arnau Sanchez",
    author_email="tokland@gmail.com",
    url="http://code.google.com/p/xhotkeys",
    packages=[  
        "xhotkeys",
        "xhotkeys/gui"
    ],
    scripts=[
		"bin/xhotkeysd",
		"bin/xhotkeys-gui",
	],
    license="GNU Public License v3.0",
    long_description=" ".join(__doc__.strip().splitlines()),
    data_files = [
        ('share/doc/xhotkeys/examples',
            ('examples/xhotkeys.conf',)),
        ('share/xhotkeys/',
            ('pics/xhotkeys.xpm',)),
        ('share/applications',
            ('xhotkeys.desktop',)),
    ],
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP',
    ],
)
