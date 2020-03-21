#from matrix_tracker import lattice
import copy
import multiprocessing
from pcaspy import Driver, SimpleServer
import time
from epics import caget, PV
import numpy as np
import random
import yaml

from virtual_machine.tools import set_nested_dict

class Model():

    def __init__(self,**kwargs):
        pass

    def run(self,input_state,verbose=False):
        if(verbose):
            print('running empty model')
        return {}

def parse_pv_file(pv_file):
    return yaml.safe_load(open(pv_file))

class CASimDriver(Driver):

    def __init__(self, io_pv_list):

        super(CASimDriver, self).__init__()
        self.io_pv_list = io_pv_list
 
    def read(self,reason): 
        return self.getParam(reason)

    def is_output_pv(self,pv):
        for iopv in self.io_pv_list:
            if(iopv.endswith(pv) and iopv.startswith('ouput')):
                return True
        return False
                
    def write(self,reason,value):

        if(is_output_pv(reason)):
            print(reason+" is a read-only (sim ouput) pv")
            return False

        else:

            self.setParam(reason,value)
            self.updatePVs()
            return True

    def set_output_pvs(self,outpvs):
        post_updates=False
        for opv in outpvs:
            if(opv in self.output_pvs):
                self.setParam(opv,outpvs[opv])
                post_updates=True
    
        if(post_updates):
            self.updatePVs()

    def get_input_pv_state(self):

        input_pv_state = {}
        for iopv in self.io_pv_list:
            if(iopv.startswith('input')):
                input_pv_state[iopv]=self.getParam(iopv.split(':')[-1])

        return input_pv_state
              
class CASyncedSimServer():

    '''Defines basic PV server that continuously syncs the input model to the input (command) EPICS PV values 
    and publishes updated model data to output EPICS PVs.  Assumes fast model execution, as the model executes
    in the main CAS server thread.  CAS for the input and ouput PVs is handled by the SimDriver object'''

    def __init__(self, pv_file, model=None):
        
        self.serve_data=False
        self.pvdb = parse_pv_file(pv_file) 
   
        assert 'input' in self.pvdb, 'User supplied pv definitions must contain "input" pvs.'
        
        if(model is None):
            self.model = Model()
        else:
            self.model = model

        self.server = SimpleServer() 

        for io_type in self.pvdb:
            for prefix in self.pvdb[io_type]:
                self.server.createPV(prefix+':', self.pvdb[io_type][prefix])

        self.driver = CASimDriver(self.get_pv_list())
        
    def set_pvs(pv_state):
        for pv,value in pv_state:
            set_nested_dict(self.pvdb, pv, value)
        
    def get_pv_list(self):
        pv_list=[]
        for io_type in self.pvdb:
            for prefix in self.pvdb[io_type]:
                for pv in self.pvdb[io_type][prefix]:
                    pv_list.append(io_type+':'+prefix+':'+pv)
  
        return pv_list

    def start_server(self):

        self.serve_data=True

        current_sim_input_pv_state = self.driver.get_input_pv_state()

        # Do initial simulation
        print("Initializing sim...")
        self.driver.set_output_pvs(self.model.run(current_sim_input_pv_state, verbose=True))
        print("...done.")
     
        while self.serve_data:
            # process CA transactions
            self.server.process(0.1)

            while(current_sim_input_pv_state != self.driver.get_input_pv_state()):

                current_sim_input_pv_state = self.server.get_input_pv_state()
                self.driver.set_output_pvs(self.model.run(self.input_pv_state, verbose=True))

    def stop_server(self):
        self.serve_data=False


