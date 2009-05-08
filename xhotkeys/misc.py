#!/usr/bin/python
"""
General-use functions and classes.
"""
import os
import sys
import time
import logging

# Verbose levels
VERBOSE_LEVELS = {
    0: logging.CRITICAL,
    1: logging.ERROR,
    2: logging.WARNING,
    3: logging.INFO,
    4: logging.DEBUG,
}

class Struct:
    """Struct/record-like class."""
    def __init__(self, name, **entries):
        self._name = name
        self.__dict__.update(entries)

    def __repr__(self):
        args = ('%s=%s' % (k, repr(v)) for (k, v) in vars(self).iteritems())
        return 'Struct %s (%s)' % (self._name, ', '.join(args))

def partial_function(callback, *pargs, **pkwargs):
    """Return a partial function to callback."""
    def _wrapper(*args, **kwargs):
        kwargs.update(pkwargs)
        return callback(*(args+pargs), **kwargs)
    return _wrapper

def first(it, pred=None):
    """Return first element in iterator that matches the predicate."""
    for item in it:
        if pred is None or pred(item):
            return item

def uniq(it):
    """Yield uniq values in iterator."""
    seen = set()
    for x in it:
        if x not in seen:
            seen.add(x)
            yield x

def flatten(it):
    """Flatten iterator content (only first level nesting)"""
    return [x for y in it for x in y]
        
def set_verbose_level(verbose_level):
    """Set verbose level for logging.
    
    See VERBOSE_LEVELS constant for allowed values."""
    nlevel = max(0, min(verbose_level, len(VERBOSE_LEVELS)-1))
    logging.basicConfig(level=VERBOSE_LEVELS[nlevel], stream=sys.stderr,  
        format='%(levelname)s: %(message)s')        
