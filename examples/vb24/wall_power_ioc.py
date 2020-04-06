import yaml
from optparse import OptionParser

# For IOC testing
from virtual_machine.ca_epics import epics_ca_ioc

if __name__ == '__main__':
    
    pvs = {'prefix':'',
           'pv':{'laser_on':{'type':'int', 'value':0}, 
                 'gun_on'  :{'type':'int', 'value':0}} }

    ioc_pv_file = 'wall_power.pvs.yaml'    

    with open(ioc_pv_file,'w') as fid:
        yaml.dump(pvs, fid)

    epics_ca_ioc(ioc_pv_file)

