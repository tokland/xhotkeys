#!/usr/bin/python
"""
General-use functions and classes.
"""
import os
import sys
import time

# By default, verbose level is set the lowest value (print only errors)
verbose_level = 0

class Struct:
    """Struct/record-like class"""
    def __init__(self, **entries):
        self.__dict__.update(entries)

    def __repr__(self):
        args = ('%s=%s' % (k, repr(v)) for (k, v) in vars(self).iteritems())
        return 'Struct(%s)' % ', '.join(args)

def partial_function(callback, *pargs, **pkwargs):
    """Return a partial function to callback."""
    def _wrapper(*args, **kwargs):
        kwargs.update(pkwargs)
        return callback(*(args+pargs), **kwargs)
    return _wrapper

def first(it, pref=bool):
    """Return first element in iterator that matches the predicate."""
    for item in it:
        if bool(item):
            return item

def _debug(line):
    """Write line to standard error."""
    sys.stderr.write(str(line) + "\n")
    sys.stderr.flush()
    
def debug(level, line):
    """Write a line debug if level is below or equal the configured."""
    if level <= verbose_level:
        _debug(line)
