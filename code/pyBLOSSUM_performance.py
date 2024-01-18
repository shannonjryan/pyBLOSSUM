import os
import sys
import pandas as pd
import numpy as np
from matplotlib import pyplot as plt
import seaborn as sns
from itertools import cycle
from BLE_NNOwhipple import NNO_performance
from BLE_modNNOwhipple import modNNO_performance
from BLE_reimerdeswhipple import reimerdes_performance
from BLE_JSCwhipple import JSCwhipple_performance
from BLE_JSCwhipple_mod import JSCwhipple_performance_mod

## default settings etc
plt.close('all')
sns.set()
# colors = sns.color_palette()
linecycler = cycle(['-','--','-.',':'])
root_dir = os.path.dirname(os.getcwd())

## read the input arguments
# filename = sys.argv[1]
# BLElist = sys.argv[2:]
filename = 'eval_example.csv'
BLElist = ['NNO','modNNO','reimerdes','JSCwhipple','JSCwhipple_mod']

## import the data file
df_data = pd.read_csv(os.path.join(root_dir,'data',filename),skiprows=[1])
  
## generate the ballistic limit curve data
V_plot = np.linspace(0.1,15,150)
df_plot = pd.DataFrame()
df_temp = pd.Series(df_data.iloc[0])
for vel in V_plot:
    df_temp['velocity'] = vel
    if 'NNO' in BLElist or 'all' in BLElist:
        df_temp['dc_NNO'] = NNO_performance(df_temp)
    if 'modNNO' in BLElist or 'all' in BLElist:
        df_temp['dc_modNNO'] = modNNO_performance(df_temp)        
    if 'reimerdes' in BLElist or 'all' in BLElist:
        df_temp['dc_reimerdes'] = reimerdes_performance(df_temp) 
    if 'JSCwhipple' in BLElist or 'all' in BLElist:
        df_temp['dc_JSCwhipple'] = JSCwhipple_performance(df_temp) 
    if 'JSCwhipple_mod' in BLElist or 'all' in BLElist:
        df_temp['dc_JSCwhipple_mod'] = JSCwhipple_performance_mod(df_temp) 
    
    df_plot = pd.concat([df_plot,df_temp],ignore_index=True,axis=1)

df_plot = df_plot.transpose()

## save the plot data to file
df_plot.to_csv(os.path.join(root_dir,'results',f'result-{filename}'),index=False)

## plot the ballistic limit curves
plt.figure()
plt.xlabel('Velocity (km/s)')
plt.ylabel('Projectile diameter (cm)')
ylim = 0.0
if 'NNO' in BLElist or 'all' in BLElist:
    plt.plot(V_plot,df_plot['dc_NNO'],ls=next(linecycler),label='NNO')
    ylim = df_plot['dc_NNO'][71] if df_plot['dc_NNO'][71] > ylim else ylim
if 'modNNO' in BLElist or 'all' in BLElist:
    plt.plot(V_plot,df_plot['dc_modNNO'],ls=next(linecycler),label='mod NNO')
    ylim = df_plot['dc_modNNO'][71] if df_plot['dc_modNNO'][71] > ylim else ylim    
if 'reimerdes' in BLElist or 'all' in BLElist:
    plt.plot(V_plot,df_plot['dc_reimerdes'],ls=next(linecycler),label='Reimerdes')
    ylim = df_plot['dc_reimerdes'][71] if df_plot['dc_reimerdes'][71] > ylim else ylim        
if 'JSCwhipple' in BLElist or 'all' in BLElist:
    plt.plot(V_plot,df_plot['dc_JSCwhipple'],ls=next(linecycler),label='JSC Whipple')
    ylim = df_plot['dc_JSCwhipple'][71] if df_plot['dc_JSCwhipple'][71] > ylim else ylim  
if 'JSCwhipple_mod' in BLElist or 'all' in BLElist:
    plt.plot(V_plot,df_plot['dc_JSCwhipple_mod'],ls=next(linecycler),label='JSC Whipple (mod)')
    ylim = df_plot['dc_JSCwhipple_mod'][71] if df_plot['dc_JSCwhipple_mod'][71] > ylim else ylim  

plt.title(f'{df_data["ref"][0]}')
plt.ylim(0.0,2.0*ylim)
plt.legend()

plt.show()
plt.savefig(os.path.join(root_dir,'plots',f'plot-{filename.split(".")[0]}.png'))

