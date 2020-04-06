from .physical_constants import unit_registry as ureg

import time

def vprint(msg, verbose):

    if(verbose):
        print(msg)

def set_nested_dict(dd, flatkey, val, sep=':', prefix=''):
    """
    Set a value inside nested dicts using a key string. 
    Example:
        dd = {'key1':{'key2':{'key3':9}}}
        set_nested_dict(dd, 'P:key1:key2:key3', 4, prefix='P')
        
        will set dd in place as:
            {'key1': {'key2': {'key3': 4}}}
        
    
    """
    if flatkey.startswith(prefix+sep):
        flatkey=flatkey[len(prefix+sep):]    
    keys = flatkey.split(':')
    d = dd
    # Go through nested dicts
    for k in keys[0:-1]:
        d = d[k]
    final_key = keys[-1]
    # Set
    if final_key in d:
        d[final_key] = val
    else:
        print(f'Error: flat key {flatkey} key does not exist:', final_key)

def get_nested_dict(dd, flatkey, sep=':', prefix='distgen'):
    """
    Gets the value in a nested dict from a flattened key.
    See: flatten_dict
    """
    if flatkey.startswith(prefix+sep):
        flatkey=flatkey[len(prefix+sep):]
    keys = flatkey.split(':')
    d = dd
    # Go through nested dicts
    for k in keys:
        d = d[k]
    return d

def is_floatable(test_float):
    try:
        float(test_float)
        is_float=True
    except:
        is_float=False
    return is_float

def convert_unit_registry(Q, ureg):
    return ureg(str(Q))

def timeit(method):

    def timed(*args, **kw):

        tstart = time.time() * ureg.second
        result = method(*args, **kw)
        tstop = time.time() * ureg.second

        if(kw['verbose']):
            dt = '{0:.3f}'.format((tstop-tstart).to_compact())
            print ( f'Time ellapsed executing {method.__name__}: {dt}' )

        return result

    return timed





