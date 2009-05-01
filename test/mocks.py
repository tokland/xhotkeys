    #!/usr/bin/python

SCALAR, LIST = range(2)

class Struct:
    """Struct/record-like class"""
    def __init__(self, **entries):
        self.__dict__.update(entries)

    def __repr__(self):
        args = ('%s=%s' % (k, repr(v)) for (k,v) in vars(self).iteritems())
        return 'Struct(%s)' % (', '.join(args))

def get_calls(mock):
    return mock._calls

def get_calls_args(mock):
    return [args for (args, kwargs) in get_calls(mock)]

def get_calls_kwargs(mock):
    return [kwargs for (args, kwargs) in get_calls(mock)]    

class Mock:
    pass
    
class MockCallable:
    """Mock callable with support for:
        
        - Track of calls and arguments
        - Responses to calls
    """
    def __init__(self, name=None, responses=None):
        self._name = name
        self._calls = []
        self._responses = responses
        
    def __repr__(self):
        if self._name:
            return "MockObject (%s)" % self._name
        return "MockObject"

    def __nonzero__(self):
        return True
        
    def __getattr__(self, attr):
        def callable(*args, **kwargs):
            return self._method_missing(attr, *args, **kwargs)
        return callable
    
    def __call__(self, *args, **kwargs):
        self._calls.append((args, kwargs))
        
        # Process responses to function calls
        if not self._responses:
            return
        ftype, fargs = self._responses
        if ftype == SCALAR:
            return fargs(*args, **kwargs)
        elif ftype == LIST:
            assert fargs, \
                "%s call: %s. No more responses" % (repr(self), name)
            func = fargs.pop(0)
            return func(*args, **kwargs)
