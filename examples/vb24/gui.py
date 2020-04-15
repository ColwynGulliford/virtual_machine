from os import sys

import yaml
import numpy as np
from epics import caget_many, PV, caget, caput

from bokeh.models import ColumnDataSource, Slider, TextInput, ColorBar, LinearColorMapper, Range1d, LogTicker, Toggle, Paragraph
from bokeh.plotting import figure
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh import palettes, colors
from bokeh.models.glyphs import VArea


class PVSlider():

    def __init__(self, title, pvname, scale, start, end, nsteps):

        self.pv = PV(pvname,auto_monitor=True)
         
        self.scale= float(scale)

        start=float(start)
        end=float(end)
        
        self.slider = Slider(title=title, value=scale*caget(pvname), start=start, end=end, step=(end-start)/nsteps)
        self.slider.on_change('value', self.set_pv_from_slider)

    def set_pv_from_slider(self,attrname,old,new):
        self.pv.put(new*self.scale)
        
    def set_slider_from_pv(self):
        self.slider.value = self.pv.value/self.scale
    

class PVTextBox():

    def __init__(self, pvname, pvdef):

        self.pvname = pvname
        title = (pvname).split(':')[-1].replace('_',' ')+' ('+pvdef['unit']+')'
        value = str(pvdef['value'])
        self.unit = pvdef['unit']

        self.text_input = TextInput(value=value, title=title)
        self.text_input.on_change("value", self.set_pv)

    def set_pv(self, attr, old, new):
        caput(self.pvname, new)

# PV initializtion
pv_file = sys.argv[-1]
pvdb = yaml.safe_load(open(pv_file))
prefix = f'{pvdb["vid"]}:'


#-------------------------------------------------------
# LASER PV AND GUI SET UP
laser_pvs = { pv.replace(prefix,''):PV(f'{pv}',auto_monitor=True) for pv in list(pvdb['input'].keys())+list(pvdb['output'].keys()) if 'laser' in pv }


# Get the PV slider and related slider objects:
laser_pv_sliders=[]
for name in ['laser:power', 'laser:sigma_xy', 'laser:alpha_xy', 'laser:mean_x', 'laser:mean_y']:
    lolim = pvdb['input'][f'{prefix}{name}']['lolim']
    hilim = pvdb['input'][f'{prefix}{name}']['hilim']
    units = pvdb['input'][f'{prefix}{name}']['unit']

    laser_pv_sliders.append(PVSlider(f'{name} ({units})',  f'{prefix}{name}', 1.0, lolim, hilim, 100))

laser_sliders = [pv_slider.slider for pv_slider in laser_pv_sliders]

# Initialize laser image:
npts = 500
x = np.linspace(-25,25,npts)
y = np.linspace(-25,25,npts)
xx, yy = np.meshgrid(x, y) # get 2D variables instead of 1D

def get_xy_image(xx, x0, yy, y0, r, Pr):

    rr = np.sqrt( (xx-x0)*(xx-x0) + (yy-y0)*(yy-y0))
    
    n,m = xx.shape
    
    rr = np.reshape(rr, (n*m,1) )
    pp = np.interp(rr, r, Pr)
    
    return np.reshape(pp, xx.shape)

def get_laser_dist(laser_pvs, xx, yy):
    
    x0 = laser_pvs['laser:mean_x'].value
    y0 = laser_pvs['laser:mean_y'].value
    rs = laser_pvs['laser:r'].value
    Pr = laser_pvs['laser:Pr'].value

    return get_xy_image(xx, x0, yy, y0, rs, Pr)*caget('laser_on')

# Set up the initial laser image and source object
xy_image = get_laser_dist(laser_pvs, xx, yy)
source = ColumnDataSource({'image':[xy_image], 'x':[x[0]] , 'y':[y[0]], 'dw':[x[-1]-x[0]] , 'dh':[y[-1]-y[0]]})

laser_fig = figure(tooltips=[('x', '$x'), ('y', '$y'), ('value', '@image')], 
                   height=400, 
                   width=400, 
                   match_aspect=True, 
                   toolbar_location="right", 
                   title=f'vLaser CCD ('+pvdb["output"][f'{prefix}laser:Pr']['unit']+')')

color_mapper = LinearColorMapper(palette="Viridis256", low=0, high=5)
color_bar = ColorBar(color_mapper=color_mapper, 
                     label_standoff=8, border_line_color=None, location=(0,0))

img_obj = laser_fig.image(name='img',image='image', x='x', y='y', dw='dw', dh='dh', source=source, color_mapper=color_mapper)
laser_fig.xaxis.axis_label = 'x (mm)'
laser_fig.yaxis.axis_label = 'y (mm)'
laser_fig.add_layout(color_bar, 'right')

wavelength_txt_box = PVTextBox(f'{prefix}laser:wavelength', pvdb['input'][f'{prefix}laser:wavelength'])

def laser_wall_power(value):
    caput('laser_on', int(value))

# Power button
laser_on_button = Toggle(label="Laser Power", button_type="success")
laser_on_button.on_click(laser_wall_power)

#-------------------------------------------------------
# BEAM PVS AND SET UP
beamline_pv_sliders = []
for name in ['gun:voltage', 'sol1:current', 'sol2:current']:
    lolim = pvdb['input'][f'{prefix}{name}']['lolim']
    hilim = pvdb['input'][f'{prefix}{name}']['hilim']
    units = pvdb['input'][f'{prefix}{name}']['unit']

    beamline_pv_sliders.append(PVSlider(f'{name} ({units})',  f'{prefix}{name}', 1.0, lolim, hilim, 100))

beamline_sliders = [pv_slider.slider for pv_slider in beamline_pv_sliders]

beam_pvs = { pv.replace(prefix,''):PV(f'{pv}',auto_monitor=True) for pv in pvdb['output'] if 'beam' in pv }

def get_beam_data(beam_pvs):
    avgx = beam_pvs['beam:mean_x'].value
    avgy = beam_pvs['beam:mean_y'].value
    avgz = beam_pvs['beam:mean_z'].value
    stdxy = beam_pvs['beam:sigma_x'].value
    maxr = beam_pvs['beam:max_r'].value

    power_on = caget('laser_on')

    return dict(x=avgz, y1=(avgx + stdxy)*power_on, y2=(avgx - stdxy)*power_on)

beamsize_source = ColumnDataSource( data=get_beam_data(beam_pvs) )

def get_fractional_laser_power(laser_pvs, pvdb):
    return (laser_pvs['laser:power'].value)/pvdb['input'][f'{prefix}laser:power']['hilim']
frac_power = get_fractional_laser_power(laser_pvs, pvdb)

avgz = beam_pvs['beam:mean_z'].value
beamsize_plot = figure(plot_height=200, plot_width=800, title="vB24", tools="crosshair,pan,reset,save,wheel_zoom", x_range=[0, avgz[-1]], y_range=[-20,20])
beamsize_glyph = VArea(x="x", y1="y1", y2="y2", fill_color="blue", fill_alpha=frac_power)

beamsize_plot.add_glyph(beamsize_source, beamsize_glyph)
beamsize_plot.xaxis.axis_label = 's (m)'
beamsize_plot.yaxis.axis_label = 'Transverse Beam Size (mm)'

# Transmission plot
T = beam_pvs['beam:transmission'].value
zero = np.zeros( (len(T),) )
Tsource = ColumnDataSource( data=dict(x=avgz, y1=T, y2=zero) )
glyphT = VArea(x="x", y1="y1", y2="y2", fill_color="grey", fill_alpha=frac_power)
transplot = figure(plot_height=200, plot_width=800, title="vB24", tools="crosshair,pan,reset,save,wheel_zoom", x_range=[0, avgz[-1]])
transplot.add_glyph(Tsource, glyphT)
transplot.xaxis.axis_label = 's (m)'
transplot.yaxis.axis_label = 'Transmission (%)'

# KE Plot
KE = beam_pvs['beam:mean_kinetic_energy'].value
kesource =  ColumnDataSource( data=dict(x=avgz, y=KE) )
keplot = figure(plot_height=200, plot_width=800, title="vB24", tools="crosshair,pan,reset,save,wheel_zoom", x_range=[0, avgz[-1]])
keplot.line(x='x',y='y',source=kesource)
keplot.xaxis.axis_label = 's (m)'
keplot.yaxis.axis_label = 'KE (keV)'


gun_current_pv = PV(f'{prefix}gun:current')
gunp = Paragraph(text=f'Gun Current: {gun_current_pv.value:G} (mA)')

radiation_pv = PV(f'{prefix}beam:radiation')
radp = Paragraph(text=f'Radiation: {radiation_pv.value:G} (arb.)')

def update():

    fpower = get_fractional_laser_power(laser_pvs,pvdb)

    xy_image = get_laser_dist(laser_pvs, xx, yy)
    img_obj.data_source.data.update({'image': [xy_image]})
        
    beamsize_source.data = get_beam_data(beam_pvs)
    Tsource.data = dict(x=avgz, y1=beam_pvs['beam:transmission'].value*caget('laser_on'), y2=zero)
    kesource.data = dict(x=avgz, y=beam_pvs['beam:mean_kinetic_energy'].value*caget('laser_on'))

    for pv_slider in laser_pv_sliders + beamline_pv_sliders: 
        pv_slider.set_slider_from_pv()

    kwargs = {'fill_alpha':fpower}
    beamsize_glyph.update(**kwargs)
    glyphT.update(**kwargs)

    gunp.text = f'Gun Current: {gun_current_pv.value:G} (mA)'
    radp.text = f'Radiation: {radiation_pv.value:G} (arb.)'
 
# Quckly throw together the final pieces:
wlength = row([wavelength_txt_box.text_input], width=500) 

laser_slider_col = column(laser_sliders, width=350)
beamline_slider_col = column(beamline_sliders, width=350)

curdoc().add_root(  row(column(laser_on_button, wlength, laser_fig, laser_slider_col), 
                        column(beamsize_plot, transplot, keplot,    row(beamline_slider_col,gunp,radp)))  )

#curdoc().add_root( row(column(buttons, p1, xyscol), column(xyplot,transplot,keplot,bscol))  ) 
curdoc().add_periodic_callback(update, 250)

    
