
from pcaspy import Driver, SimpleServer
import time
from epics import caget, PV
import numpy as np
import yaml
import warnings

from virtual_machine.tools import vprint
from virtual_machine.tools import set_nested_dict

from pint import UnitRegistry, Quantity
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    Quantity([])
unit_registry = UnitRegistry()
unit_registry.setup_matplotlib()

class Model():

    def __init__(self,**kwargs):
        pass

    def run(self,input_state,verbose=False):
        if(verbose):
            print('running empty model')
        return {}


def parse_pv_file(pv_file):
    return yaml.safe_load(open(pv_file))


class SimCADriver(Driver):

    def __init__(self, input_pvs, output_pvs):

        super(SimCADriver, self).__init__()
        self.input_pvs = input_pvs
        self.output_pvs = output_pvs
 
    def read(self,reason): 
        return self.getParam(reason)

    def is_input_pv(self,pv):
        if(pv in self.input_pvs):
            return True
        return False

    def is_output_pv(self,pv):
        if(pv in self.output_pvs):
            return True
        return False
                
    def write(self,reason,value):

        if(self.is_output_pv(reason)):
            print(reason+" is a read-only (sim ouput) pv")
            return False

        else:
            self.setParam(reason,value)
            self.updatePVs()
            return True

    def set_output_pvs(self,outpvs):

        post_updates=False

        for opv in outpvs:

            if(self.is_output_pv(opv)):

                pinfo = self.getParamInfo(opv)   
                value = outpvs[opv]
  
                self.set_param(opv,value)
                post_updates=True
    
        if(post_updates):
            self.updatePVs()

    def get_input_pv_state(self):

        input_pv_state = {}
        for ipv in self.input_pvs:
            pinfo = self.getParamInfo(ipv)
            if(pinfo['type']==9):  # 9 <-> float, 
                input_pv_state[ipv]=self.getParam(ipv)*unit_registry(pinfo['unit'])
            else:
                input_pv_state[ipv]=self.getParam(ipv)

        return input_pv_state


    def set_param(self,reason, value): 

        pinfo = self.getParamInfo(reason)   

        if(pinfo['count']>1):

            if(len(value)!=pinfo['count']):
                pinfo['count']=len(value)
                self.setParamInfo(reason, pinfo)

            self.setParam(reason,value.to(pinfo['unit']))

        else:

            self.setParam(reason, float(value.to(pinfo['unit']).magnitude))
           

              
class SimCAServer():

    '''Defines basic PV server that continuously syncs the input model to the input (command) EPICS PV values 
    and publishes updated model data to output EPICS PVs.  Assumes fast model execution, as the model executes
    in the main CAS server thread.  CAS for the input and ouput PVs is handled by the SimDriver object'''

    def __init__(self, pv_file, model=None):
        
        self.serve_data=False
        inputs = parse_pv_file(pv_file) 
   
        assert 'name'  in inputs
        self.name = inputs['name']

        assert 'input' in inputs, 'User supplied pv definitions must contain "input" pvs.'
        
        if(model is None):
            self.model = Model()
        else:
            self.model = model

        self.pvdb = {**inputs['input'], **inputs['output']}

        self.server = SimpleServer() 
        self.server.createPV(self.name+':', self.pvdb)

        self.driver = SimCADriver(inputs['input'], inputs['output'])

    def start(self):

        self.serve_data=True
        	
        current_sim_input_pv_state = self.driver.get_input_pv_state()

        # Do initial simulation
        vprint("Initializing sim...", True)
        self.driver.set_output_pvs(self.model.run(current_sim_input_pv_state, verbose=True))
        vprint("...done.", True)
     
        while self.serve_data:

            # process CA transactions
            self.server.process(0.1)

            while(current_sim_input_pv_state != self.driver.get_input_pv_state()):
                
                current_sim_input_pv_state = self.driver.get_input_pv_state()
                vprint('Running model and updating pvs...', True)
                t1 = time.time()
                self.driver.set_output_pvs(self.model.run(current_sim_input_pv_state, verbose=True))
                t2 = time.time()
                dt = ((t2-t1)*unit_registry('s')).to_compact()
                vprint('...done. Time ellapsed: {:.3E}'.format(dt), True) 
                

    def stop(self):
        self.serve_data=False


class SyncedSimCAServer(SimCAServer):

    '''Defines basic PV server that continuously syncs the input model to the input (command) EPICS PV values 
    and publishes updated model data to output EPICS PVs.  Assumes fast model execution, as the model executes
    in the main CAS server thread.  CAS for the input and ouput PVs is handled by the SimDriver object'''

    def __init__(self, pv_file, model=None):
       
        caget('vlaser@test:energy_pulse')

        super(SyncedSimCAServer, self).__init__(pv_file,model)

        pvdefs = parse_pv_file(pv_file) 
        #self.monitor_pv_list = pvdefs['monitor']
        #print(self.monitor_pv_list)
   
        #assert 'input' in pvdefs, 'User supplied pv definitions must contain "input" pvs.'

        print('Setting monitors...')
        self.monitors = {mpv:PV(mpv,auto_monitor=True) for mpv in pvdefs['monitor']}
        for pv in self.monitors:
            print(pv,self.monitors[pv])

        #del pvdefs['monitors']
        #self.pvdb = pvdefs
        
        #if(model is None):
        #    self.model = Model()
        #else:
        #    self.model = model

        #self.server = SimpleServer() 

        #for io_type in self.pvdb:
        #    for prefix in self.pvdb[io_type]:
        #        self.server.createPV(prefix+':', self.pvdb[io_type][prefix])

        #self.driver = SimCADriver(self.get_pv_list())
        
    #def set_pvs(pv_state):
    #    for pv,value in pv_state:
    #        set_nested_dict(self.pvdb, pv, value)
        
    #def get_pv_list(self):
    #    pv_list=[]
    #    for io_type in self.pvdb:
    #        for prefix in self.pvdb[io_type]:
    #            for pv in self.pvdb[io_type][prefix]:
    #                pv_list.append(io_type+':'+prefix+':'+pv)
  
#        return pv_list

    def start(self):

        self.serve_data=True

        current_sim_input_pv_state = self.driver.get_input_pv_state()

        # Do initial simulation
        vprint("Initializing sim...", True)
        self.driver.set_output_pvs(self.model.run(current_sim_input_pv_state, verbose=True))
        vprint("...done.", True)
     
        while self.serve_data:

            # process CA transactions
            self.server.process(0.1)

            while(current_sim_input_pv_state != self.driver.get_input_pv_state()):
                
                current_sim_input_pv_state = self.driver.get_input_pv_state()
                vprint('Running model and updating pvs...', True)
                t1 = time.time()
                self.driver.set_output_pvs(self.model.run(current_sim_input_pv_state, verbose=True))
                t2 = time.time()
                dt = ((t2-t1)*unit_registry('s')).to_compact()
                vprint('...done. Time ellapsed: {:.3E}'.format(dt), True) 
                

    def stop(self):
        self.serve_data=False

