from epics import caget, caput, cainfo, PV, caput_many
import numpy as np
import time
from matplotlib import pyplot as plt

from scipy import optimize as opt

VID = 'vb24@test:'

def holdup():
    time.sleep(0.2)
    caput(f'{VID}sim:status',0)
    while(caget(f'{VID}sim:status')==0):
        time.sleep(0.01)

def scan_sol(currents, MTE, plot_on=False, verbose=False, noise=None):

    stdxs = np.empty(currents.shape)
    stdxs[:] = np.NaN
 
    caput(f'{VID}cathode:MTE',MTE)
    holdup()

    if(plot_on):
        plt.figure()
        h, = plt.plot([], [])
        plt.xlabel('Solenoid 1 Current (A)')
        plt.ylabel('$\sigma_x$ (mm)')
        plt.ion()
        plt.show()

    for ii, I in enumerate(currents):
        if(verbose):
            print(f'{ii} Solenoid 1 setting: {I} A')
        caput(f'{VID}sol1:current',I)

        holdup()

        stdxs[ii] = caget(f'{VID}scr1:sigma_x') 

        if(plot_on):
            plt.plot(currents,stdxs,'or')
            plt.draw()
            plt.pause(0.01)
        else:
            time.sleep(0.01)
       
    return stdxs


if __name__ == '__main__':

    ndata = 15
    nplot = 100

    currents_data = np.linspace(0,5,ndata)

    print('Taking vData >---------------')
    stdx_data = scan_sol(currents_data, 150, True, True)
    print('----------------------< done.')        

    print('\nAnalyzing vData >----------')
    MTE0 = 100  # An mte guess

    MTE, covar = opt.curve_fit(scan_sol, currents_data, stdx_data, MTE0) 

    print(f'Fit MTE: {MTE} (meV)')
    print('----------------------< done.') 

    currents_fit =  np.linspace(0, 5, nplot)
    stdx_fit = scan_sol(currents_fit, MTE, False)

    plt.figure()
    plt.plot(currents_fit, stdx_fit,'b', currents_data, stdx_data, 'or')
    plt.legend(['fit','data'])
    plt.xlabel('Solenoid 1 Current (A)')
    plt.ylabel('$\sigma_x$ (mm)')

    input('werd')  
  
 



