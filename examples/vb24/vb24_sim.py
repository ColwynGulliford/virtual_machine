
from virtual_machine.physical_constants import unit_registry as units

from epics import caget, caput, cainfo, PV, caput_many

import numpy as np
from optparse import OptionParser
import yaml
import copy 
import time
import re
import os

from virtual_machine.tools import timeit
from virtual_machine.physical_constants import unit_registry as units

from distgen import Generator
from distgen.dist import SuperGaussianRad
from distgen.physical_constants import unit_registry as dunits

from gpt import GPT
from pmd_beamphysics import ParticleGroup

# Will clean this up later
def multiply(a, b):
    return a*b

def equals(a, b):
    return b

class SyncedPV():

    def __init__(self, linked_pvname, synced_pvname, operation, auto_sync=False):

        self.operation_fun = self.get_operation(operation)

        self.auto_sync = auto_sync
        self.linked_pv = PV(linked_pvname)
        self.synced_pv = PV(synced_pvname, auto_monitor=True, callback=self.synced_pv_callback)
        self.sync_value = self.synced_pv.value        

    def synced_pv_callback(self, pvname, value, **kwargs):
        if(self.auto_sync):
            self.linked_pv.put(self.operation_fun(self.linked_pv.value, value))
        self.sync_value = value

    def sync(self):
        self.linked_pv.put(self.operation_fun(self.linked_pv.value, self.synced_pv.value))

    def get_operation(self, operation):
        if(operation=='*'):
            return multiply
        elif(operation=='='):
            return equals


class PVMonitorArray():

    def __init__(self,pvnames):
        self.monitors = {pvname:PV(pvname,auto_monitor=True) for pvname in pvnames}

    def get(self,with_units=False):

        if(with_units):  # Convert to Quantity with units
            return {pvname:self.monitors[pvname].value*units(self.monitors[pvname].units) for pvname in self.monitors}
        
        return {pvname:self.monitors[pvname].value for pvname in self.monitors}

    @timeit
    def put(self, pvd, verbose=True):
        if(verbose):
            for pv in pvd:
                print(pv+',' ,'caput success:', caput(pv, pvd[pv]))

        else:
            caput_many(pvd.keys(), pvd.values())     

class b24Model():

    def __init__(self, pvdefs):

        self.pvdefs = {**pvdefs['input'],**pvdefs['output']}

        self.id = list(set([m[m.find("@")+1:m.find(":",1)] for m in pvdefs['input'] if('vb24' in m)]))[0]

    @timeit
    def run(self, inputs, verbose=False):
       
        tag = f'vb24@{self.id}:'

        #----------------------------------------------------------------------------
        # Get laser distribution, cathode quantities, and gun current
        #----------------------------------------------------------------------------
        r_params = {'sigma_xy': dunits(str(inputs[f'{tag}laser:sigma_xy'])),
                    'alpha':    dunits(str(inputs[f'{tag}laser:alpha_xy']))}

        count = self.pvdefs[f'{tag}laser:r']['count']
        laser_wavelength = inputs[f'{tag}laser:wavelength']
        laser_power = inputs[f'{tag}laser:power']
        laser_sigma_xy = inputs[f'{tag}laser:sigma_xy']
        laser_alpha_xy = inputs[f'{tag}laser:alpha_xy']
        laser_avg_x = inputs[f'{tag}laser:mean_x']
        laser_avg_y = inputs[f'{tag}laser:mean_y']

        r_dist = SuperGaussianRad(verbose=False, **r_params)
        rs = (r_dist.get_r_pts(count)).to(self.pvdefs[f'{tag}laser:r']['unit'])
        Pr = (dunits(str(laser_power))*r_dist.rho(rs)).to(self.pvdefs[f'{tag}laser:Pr']['unit'])

        cathode_QE = inputs[f'{tag}cathode:QE']
        cathode_MTE = inputs[f'{tag}cathode:MTE']

        hc = 1*units.h*units.c
        photon_flux = (laser_power/(hc/laser_wavelength) ).to_base_units()
        gun_current = (photon_flux*cathode_QE*(1*units.e)).to(self.pvdefs[f'{tag}gun:current']['unit'])
        #----------------------------------------------------------------------------
       

        #----------------------------------------------------------------------------
        # Create Distgen input and run generator
        #----------------------------------------------------------------------------
        distgen_input = yaml.dump(
                        {'n_particle':inputs[f'{tag}gpt:n_particle'].magnitude,
                         'random_type':'hammersley',
                         'total_charge': {'value': 0.0, 'units': 'pC'},   
                         'start': {
                             'type':'cathode',
                             'MTE': {'value': cathode_MTE.magnitude, 'units': str(cathode_MTE.units)}},

                         'r_dist': {
                             'type':'rsg',
                             'sigma_xy':{'value': laser_sigma_xy.magnitude, 'units': str(laser_sigma_xy.units)},
                             'alpha':{'value': laser_alpha_xy.magnitude, 'units': str(laser_alpha_xy.units)},},

                         'transforms':{
                             't1':{'type':'set_avg x', 'avg_x': {'value': laser_avg_x.magnitude, 'units': str(laser_avg_x.units)}},
                             't2':{'type':'set_avg y', 'avg_y': {'value': laser_avg_y.magnitude, 'units': str(laser_avg_y.units)}}
                         }})
 
        gen = Generator(distgen_input, verbose=True)     
        beam = gen.beam()   
        #----------------------------------------------------------------------------


        #----------------------------------------------------------------------------
        # Configure GPT and run
        #----------------------------------------------------------------------------
        G = GPT(input_file=os.path.join(os.getcwd(),'templates/gpt.in'), 
                initial_particles = ParticleGroup(data=beam.data()), 
                use_tempdir=True,
                workdir=os.path.join(os.getcwd(),'tmp'),
                timeout = 5,
                verbose=True)

        settings = {'gun_voltage':   inputs[f'{tag}gun:voltage'].magnitude, 
                    'sol01_current': inputs[f'{tag}sol1:current'].magnitude,
                    'sol02_current': inputs[f'{tag}sol2:current'].magnitude,
                    'npts':          inputs[f'{tag}gpt:n_screen'].magnitude+1}

        result = G.set_variables(settings)
        G.run()
        #----------------------------------------------------------------------------


        #----------------------------------------------------------------------------
        # Load all relevant data into output structure
        #----------------------------------------------------------------------------
        # laser distribution
        output = {f'{tag}laser:r':rs.magnitude, f'{tag}laser:Pr':Pr.magnitude, f'{tag}gun:current':gun_current.magnitude}

        # GPT statistical data
        stats = {'max':['r'], 'mean':['x', 'y', 'z', 'kinetic_energy'], 'sigma':['x','y']}
        for stat, variables in stats.items():
                output = {**output, **{f'{tag}beam:{stat}_{var}': self.gpt_stat_to_pv(G, f'{stat}_{var}', 'screen').magnitude for var in variables} }

        scr_numbers = [1]
        for scr_number in scr_numbers:
            z = inputs[f'{tag}scr{scr_number}:mean_z'].magnitude
            for var in ['x' ,'y']:
                output[f'{tag}scr{scr_number}:mean_{var}']  = np.interp(z, output[f'{tag}beam:mean_z'], output[f'{tag}beam:mean_{var}'])
                output[f'{tag}scr{scr_number}:sigma_{var}'] = np.interp(z, output[f'{tag}beam:mean_z'], output[f'{tag}beam:sigma_{var}'])
                
        # transmission
        output[f'{tag}beam:transmission'] = [100*len(screen['x'])/inputs[f'{tag}gpt:n_particle'].magnitude for screen in G.screen]
    
        min_clearance = np.min( (inputs[f'{tag}beampipe:radius']-self.gpt_stat_to_pv(G, f'{stat}_{var}', 'screen') ) ).to('mm')
        output[f'{tag}beam:radiation'] = output[f'{tag}gun:current']*np.max(output[f'{tag}beam:mean_kinetic_energy'])/min_clearance.magnitude
        #----------------------------------------------------------------------------


        return output

    def gpt_stat_to_pv(self, G, name, output_type):

        value = G.stat(name, output_type)*units(str(G.stat_units(name)))
        return value.to(self.pvdefs[f'vb24@{self.id}:beam:{name}']['unit'])

def set_up(pv_template, target, tid):

    if(tid is None):
        tid='test'
        print(f'No {target} name specified, defaulting to "test", pvs are addressed: {target}@{tid}:pvname.')
        prefix = '{target}@test'
    else:
        prefix = f'{target}@{tid}'

    pvdefs = yaml.safe_load(open(pv_template))

    prefix = f'{target}@{tid}:'
    
    # Get sync pvs
    syncs = copy.deepcopy(pvdefs['sync'])
    for synced_pv in pvdefs['sync']:
        for linked_pv in pvdefs['sync'][synced_pv].keys():
            syncs[synced_pv][f'{prefix}{linked_pv}'] = pvdefs['sync'][synced_pv][linked_pv] 
            del syncs[synced_pv][linked_pv]     
    pvdefs['sync']=syncs

    sim_pvdb = {'vid':f'{target}@{tid}',
                'sync': syncs,
                'input': {f'{prefix}{key}':value for key, value in pvdefs['input'].items()},
                'output':{f'{prefix}{key}':value for key, value in pvdefs['output'].items()},}

    sim_pv_file = f'{target}@{tid}.sim.pvs.yaml'
    
    with open(sim_pv_file, 'w') as fid:
        yaml.dump(sim_pvdb,fid)

    return sim_pv_file, prefix

if __name__ == '__main__':

    pv_template_file = 'pv.template.yaml'

    parser = OptionParser()
    parser.add_option("-t", "--tid", dest="tid", default=None, 
                      help="target ID tag, prepended to all associated PVs", metavar="FILE")
    parser.add_option("-m", "--mid", dest="mid", default=None, 
                      help="monitor ID tag, prepended to all associated PVs", metavar="FILE")

    (options, args) = parser.parse_args()
    tid = options.tid

    target = 'vb24'

    sim_pv_file, vid = set_up(pv_template_file, 'vb24', tid)

    # Load PVdefs:
    pvdefs = yaml.safe_load(open(sim_pv_file))
    
    # Set PV monitors
    input_pvs = PVMonitorArray(pvdefs['input'].keys())
    output_pvs = PVMonitorArray(pvdefs['output'].keys())

    # Set sim status to not ready
    caput(f'{vid}sim:status',0)

    # Get initial sim state, and initialize the model
    print('Initialize model >-----------')
    current_sim_inputs = input_pvs.get(with_units=True)
    model = b24Model(pvdefs)
    current_sim_outputs = model.run(current_sim_inputs,verbose=True)
    output_pvs.put(current_sim_outputs,verbose=True)
    caput(f'{vid}sim:status',1)
    print('-----------< done.\n')

    # Get synced pv relations
    sync_pvs = []
    for sync_pv, linked_pvs in pvdefs['sync'].items():
        for linked_pv in linked_pvs:
            sync_pvs.append( SyncedPV(linked_pv, sync_pv, linked_pvs[linked_pv]['operation'], auto_sync=True) )

    print('Monitoring...')
    while True:

        while current_sim_inputs != input_pvs.get(with_units=True):
            caput(f'{vid}sim:status',0)
            current_sim_inputs = input_pvs.get(with_units=True)

            print('\nRunning Model >-----------')
            current_sim_outputs = model.run(current_sim_inputs,verbose=True)
            print('Updating outputs...')
            output_pvs.put(current_sim_outputs, verbose=False)
            print('-----------< done.')

        caput(f'{vid}sim:status',1)
        time.sleep(0.1)
        

