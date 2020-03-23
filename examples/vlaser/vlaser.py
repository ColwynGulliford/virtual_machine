from virtual_machine.epics_ca import Model, SyncedSimCAServer

from distgen.physical_constants import unit_registry as units
from distgen.dist import SuperGaussianRad, SuperGaussian

import numpy as np

class vlaser_model(Model):

    def __init__(self):
        pass

    def run(self, inputs, verbose=False):
 
        # Form the radial distribution 
        r_params = {'lambda':units(str(inputs['input:laser:xy_length'])),
                    'alpha': units(str(inputs['input:laser:alpha_xy']))}

        r_dist = SuperGaussianRad(verbose=False, **r_params)
        r_npts = inputs['input:laser:r_npts']
        rs = r_dist.get_r_pts(r_npts)
        Pr = units(str(inputs['input:laser:pulse_energy']))*r_dist.rho(rs)
        sigma_xy = r_dist.rms()*np.sqrt(0.5)

        t_params = {'lambda': units(str(inputs['input:laser:t_length'])),
                    'alpha':  units(str(inputs['input:laser:alpha_t']))}

        t_dist = SuperGaussian('t',verbose=False, **t_params)
        t_npts = inputs['input:laser:t_npts']
        ts = t_dist.get_x_pts(t_npts)
        Pt = units(str(inputs['input:laser:pulse_energy']))*t_dist.pdf(ts)

        sigma_t = t_dist.std()

        output = {'output:dist:r':rs, 
                  'output:dist:Pr':Pr, 
                  'output:dist:sigma_xy':sigma_xy, 
                  'output:dist:t':ts, 
                  'output:dist:Pt':Pt, 
                  'output:dist:sigma_t':sigma_t
                  }

        return output

def main():

    pv_file = 'laser_pvs.yaml'
    server = SyncedSimCAServer(pv_file,model=vlaser_model())
    server.start()

if __name__ == '__main__':
   main()
