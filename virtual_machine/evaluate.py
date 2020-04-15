from epics import caget, caput, caget_many, caput_many
import yaml
import time
import numpy as np


def hold_up(status_pv, pause, timeout):

    tnow = time.time()
    while(caget(status_pv)!=1, time.time()-tnow < timeout):
        time.sleep(0.2)
    
def default_epics_ca_merit(data):

    # check all caget's returned values, no None's, 
    #put all output_pvs into merits

    if(np.any(data.values() == None) ):
        return {'error':True}
    else:
        return {'error':False, **data}


def default_measurement(settings, measurements, pause=1.0):


    set_results = caput_many(settings.keys(), settings.values())

    time.sleep(pause)

    measured_values = caget_many(measurements)

    if None in set_results:
        raise ValueError('Could not set machine settings.')

    data = { name:measured_values[ii] for ii, name in enumerate(measurements) }

    return data
    

def evaluate_epics_ca(settings, 
                      pv_file= 'vb24@test.sim.pvs.yaml',
                      status_pv = 'vb24@test:sim:status',
                      pause=1.0,
                      simulation='epics_ca', 
                      archive_path=None, 
                      measurement_f=None,
                      merit_f=None, 
                      verbose=False):

    if(caget(status_pv)==0):
        ready = False
    else:
        ready = True

    with open(pv_file) as fid:
        pvdefs = yaml.safe_load(fid)

    measurements = pvdefs['output'].keys()   # Get the list of things to pull
    #print(pause)

    if(ready):
         
        if measurement_f:
            data = measurement_f(settings, measurements, pause=pause)

        else:
            data = default_measurement(settings, measurements, pause=pause)

        if merit_f:
            output = merit_f(data)
        else:
            output = default_epics_ca_merit(data)

        if output['error']:
            raise 

    else:
        raise ValueError('Machine was not ready')

    return output

