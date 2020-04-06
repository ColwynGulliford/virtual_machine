import yaml
from optparse import OptionParser

# For IOC testing
from virtual_machine.ca_epics import epics_ca_ioc

def set_up(pv_template, target, tid,):

    if(tid is None):
        tid='test'
        print(f'No {target} name specified, defaulting to "test", pvs are addressed: {target}@{tid}:pvname.')
        prefix = '{target}@test'
    else:
        prefix = f'{target}@{tid}'

    pvdefs = yaml.safe_load(open(pv_template))

    ioc_pv_file = f'{target}@{tid}.ioc.pvs.yaml'
    ioc_pvdb = {'pv':{**pvdefs['input'], **pvdefs['output']}}
    ioc_pvdb['prefix']=f'{target}@{tid}:'
    
    with open(ioc_pv_file,'w') as fid:
        yaml.dump(ioc_pvdb, fid)

    return ioc_pv_file


if __name__ == '__main__':

    parser = OptionParser()
    parser.add_option("-t", "--id", dest="tid", default=None, 
                      help="target ID tag, prepended to all associated PVs", metavar="FILE")

    (options, args) = parser.parse_args()
    tid = options.tid

    ioc_pv_file = set_up('pv.template.yaml', 'vb24', tid)

    epics_ca_ioc(ioc_pv_file)


