import yaml
import numpy as np
from epics import caget_many, PV, caget, caput

from bokeh.models import ColumnDataSource, Slider
from bokeh.plotting import figure
from bokeh.io import curdoc
from bokeh.layouts import column, row

from bokeh import palettes, colors

pal = palettes.Viridis[256]
white=colors.named.white

# Helper functions:
def get_xy_image(xx, yy, r, Pr):

    rr = np.sqrt(xx*xx + yy*yy)
    
    n,m = xx.shape
    
    rr = np.reshape(rr, (n*m,1) )
    pp = np.interp(rr, r, Pr)
    
    return np.reshape(pp, xx.shape)


class pv_slider():

    def __init__(self, title, pvname, scale, start, end, nsteps):

        self.pvname = pvname
        self.scale=scale
        
        self.slider = Slider(title=title, value=scale*caget(pvname), start=start, end=end, step=(end-start)/nsteps)
        self.slider.on_change('value',self.set_pv_from_slider)

    def set_pv_from_slider(self,attrname,old,new):
        caput(self.pvname, new*self.scale)


# PV initializtion
pv_file = 'laser_pvs.yaml'
pvdb = yaml.safe_load(open(pv_file))

dist_monitors = {key:PV('dist:'+key,auto_monitor=True) for (key,value) in pvdb['output']['dist'].items()}

xy_names = ['xy_length', 'alpha_xy']
xy_pv_sliders = [(pv_slider(key.replace('_',' ')+' ('+pvdb['input']['laser'][key]['unit']+')','laser:'+key, 1, float(pvdb['input']['laser'][key]['lolim']), float(pvdb['input']['laser'][key]['hilim']), 100)).slider for key in xy_names]

t_names = ['t_length', 'alpha_t']
t_pv_sliders = [(pv_slider(key.replace('_',' ')+' ('+pvdb['input']['laser'][key]['unit']+')','laser:'+key, 1, float(pvdb['input']['laser'][key]['lolim']), float(pvdb['input']['laser'][key]['hilim']), 100)).slider for key in t_names]

npts = 500
x = np.linspace(-15,15,npts)
y = np.linspace(-15,15,npts)
xx, yy = np.meshgrid(x, y) # get 2D variables instead of 1D

rs = dist_monitors['r'].value
Pr = dist_monitors['Pr'].value

xy_image = get_xy_image(xx, yy, rs, Pr)

source = ColumnDataSource({'image':[xy_image], 'x':[x[0]] , 'y':[y[0]], 'dw':[x[-1]-x[0]] , 'dh':[y[-1]-y[0]]})
p1 = figure(tooltips=[("x", "$x"), ("y", "$y"), ("value", "@image")], height=400, width=400, match_aspect=True)
img_obj = p1.image(name='img',image='image', x='x', y='y', dw='dw', dh='dh', source=source, palette=pal)

p1.xaxis.axis_label = 'x (mm)'
p1.yaxis.axis_label = 'y (mm)'

source = ColumnDataSource(dict(x=dist_monitors['t'].value, y=dist_monitors['Pt'].value))
p2 = figure(plot_width=400, plot_height=400)
p2.line(x='x', y='y', line_width=2, source=source)
p2.xaxis.axis_label = 't ('+pvdb['output']['dist']['t']['unit']+')'
p2.yaxis.axis_label = 'Power ('+pvdb['output']['dist']['Pt']['unit']+')'

def update():

    replot=True

    if(replot):
        
        rs = dist_monitors['r'].value
        Pr = dist_monitors['Pr'].value

        xy_image = get_xy_image(xx,yy,rs,Pr)
        img_obj.data_source.data.update({'image': [xy_image]})

        source.data = dict(x=dist_monitors['t'].value, y=dist_monitors['Pt'].value)

xyscol = column(xy_pv_sliders,width=350)
tscol = column(t_pv_sliders,width=350)
curdoc().add_root( row(column(row(p1,width=300),xyscol), column(p2,tscol))  )
curdoc().add_periodic_callback(update, 250)



    
