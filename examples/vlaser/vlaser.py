
from virtual_machine.epics_ca import Model, SimCAServer

from distgen.physical_constants import unit_registry as units
from distgen.dist import SuperGaussianRad, SuperGaussian

import numpy as np
from optparse import OptionParser
import yaml

class vlaser_model(Model):

    def __init__(self):
        pass

    def run(self, inputs, verbose=False):
 
        # Form the radial distribution 
        r_params = {'sigma_xy':units(str(inputs['sigma_xy'])),
                    'alpha': units(str(inputs['alpha_xy']))}

        r_dist = SuperGaussianRad(verbose=False, **r_params)
        r_npts = inputs['r_npts']
        rs = r_dist.get_r_pts(r_npts)
        Pr = units(str(inputs['pulse_energy']))*r_dist.rho(rs)
        sigma_xy = r_dist.rms()*np.sqrt(0.5)

        t_params = {'sigma_t': units(str(inputs['sigma_t'])),
                    'alpha':  units(str(inputs['alpha_t']))}

        t_dist = SuperGaussian('t',verbose=False, **t_params)
        t_npts = inputs['t_npts']
        ts = t_dist.get_x_pts(t_npts)
        Pt = units(str(inputs['pulse_energy']))*t_dist.pdf(ts)

        sigma_t = t_dist.std()

        output = {
                  'r':rs, 
                  'Pr':Pr, 
                  't':ts, 
                  'Pt':Pt, 
                  }

        return output

def main():

    pv_template_file = 'pv.defs.yaml'

    parser = OptionParser()
    parser.add_option("-i", "--id", dest="id", default=None, 
                      help="vlaser ID tag, prepended to all associated PVs", metavar="FILE")
    parser.add_option("-v",dest="verbose", default=0,help="Print short status messages to stdout")

    (options, args) = parser.parse_args()

    vid = options.id
    if(vid is None):
        print(f'No vlaser name specified, defaulting to "test", pvs are addressed: vlaser@{vid}:pvname.')
        prefix = 'vlaser@test'
    else:
        prefix = f'vlaser@{vid}'

    pvdef = yaml.safe_load(open(pv_template_file))
    pvdef['name']=prefix
  
    pv_file = prefix+'.pvs.yaml'
    with open(pv_file, 'w') as fid:
        yaml.dump(pvdef,fid)

    server = SimCAServer(pv_file,model=vlaser_model())
    server.start()

if __name__ == '__main__':
    main()

