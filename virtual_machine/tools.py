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

#def get_flat_keys(dd,sep=':'):


#    for k in 
