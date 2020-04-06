
from virtual_machine.physical_constants import unit_registry as ureg

from epics import caget, cainfo, PV

import numpy as np
from optparse import OptionParser
import yaml
import copy 
import time
import re

from multiprocessing import Process
from virtual_machine.tools import timeit

class PVMonitorArray():

    def __init__(self,pvnames):
        self.monitors = {pvname:PV(pvname,auto_monitor=True) for pvname in pvnames}

    def state(self):
        return {pvname:self.monitors[pvname].value for pvname in self.monitors}

class CathodeModel():#(Model):

    def __init__(self, pvdefs):

        self.pvdefs = pvdefs
        self.laser_mid = list(set([m[m.find("@")+1:m.find(":",1)] for m in pvdefs['monitor'] if('vlaser' in m)]))[0]
        self.cathod_tid = list(set([m[m.find("@")+1:m.find(":",1)] for m in pvdefs['input'] if('vcathode' in m)]))[0]

    @timeit
    def run(self, inputs, verbose=False):
 
        laser = f'vlaser@{self.laser_mid}'
        cathode = f'vcathode@{self.cathod_tid}'

        wavelength = inputs[f'{laser}:wavelength']*ureg( self.pvdefs['monitor'][f'{laser}:wavelength']['unit'] )
        pulse_energy = inputs[f'{laser}:pulse_energy']*ureg( self.pvdefs['monitor'][f'{laser}:pulse_energy']['unit'] )

        QE = inputs[f'{cathode}:QE']*ureg( self.pvdefs['input'][f'{cathode}:QE']['unit'] )

        hc = 1*ureg.h*ureg.c
        n_photon = (pulse_energy/(hc/wavelength) ).to_base_units()
        qbunch = QE*n_photon*(1*ureg.e)

        print('qb', qbunch.to(self.pvdefs['output'][f'{cathode}:q_bunch']['unit']) )

        output = {
                  #'output:laser:r':rs, 
                  #'output:laser:Pr':Pr, 
                  #'output:dist:sigma_xy':sigma_xy, 
                  #'output:laser:t':ts, 
                  #'output:laser:Pt':Pt, 
                  #'output:dist:sigma_t':sigma_t
                  }

        return output

def set_up(pv_template, target, tid, mid):

    if(tid is None):
        tid='test'
        print(f'No {target} name specified, defaulting to "test", pvs are addressed: {target}@{tid}:pvname.')
        prefix = '{target}@test'
    else:
        prefix = f'{target}@{tid}'

    if(mid is None):
        mid = 'test'
        print(f'No monitor ID specified for monitors, defaulting to "test", monitored pvs are addressed: [monitor_target]@{mid}:pvname.')
     
    pvdefs = yaml.safe_load(open(pv_template))

    assert 'monitor' in pvdefs, 'Virtual cathode must have monitor pvs.'

    monitor_ids = pvdefs['monitor']
    monitor_pvs = []
    for monitor_id in monitor_ids:
        monitor_pvs = monitor_pvs + [monitor_id.replace('@mid',f'@{mid}:')+pvname for pvname in monitor_ids[monitor_id]]
    
    pvdefs['monitor']=monitor_pvs
    prefix = f'{target}@{tid}:'
    
    sim_pvdb = {'monitor':{},
                'input': {prefix+key:value for key, value in pvdefs['input'].items()},
                'output':{prefix+key:value for key, value in pvdefs['output'].items()},}

    # Get monitor info?
    for mpvname in monitor_pvs:
       mpv = PV(mpvname)
       sim_pvdb['monitor'][mpvname] = {'unit':mpv.units}

    sim_pv_file = f'{target}@{tid}.sim.pvs.yaml'
    
    with open(sim_pv_file, 'w') as fid:
        yaml.dump(sim_pvdb,fid)

    return sim_pv_file

if __name__ == '__main__':

    pv_template_file = 'pv.template.yaml'

    parser = OptionParser()
    parser.add_option("-t", "--tid", dest="tid", default=None, 
                      help="target ID tag, prepended to all associated PVs", metavar="FILE")
    parser.add_option("-m", "--mid", dest="mid", default=None, 
                      help="monitor ID tag, prepended to all associated PVs", metavar="FILE")

    (options, args) = parser.parse_args()

    tid = options.tid
    mid = options.mid

    sim_pv_file = set_up(pv_template_file, 'vcathode', tid, mid)

    # Load PVdefs:
    pvdefs = yaml.safe_load(open(sim_pv_file))
    
    # Set PV monitors
    monitor_pvnames = [mpv for mpv in pvdefs['monitor']] + [ipv for ipv in pvdefs['input']]
    monitors = PVMonitorArray(monitor_pvnames)
    
    # Get initial sim state, and initialize the model
    current_sim_input = monitors.state()
    model = CathodeModel(pvdefs)
    sim_outputs = model.run(current_sim_input,verbose=True)

    while True:

        current_monitor_state = monitors.state()
        while current_sim_input != current_monitor_state:
            
            sim_outputs = model.run(current_sim_input,verbose=True)
            current_sim_input = current_monitor_state
            

        time.sleep(0.1)
        

