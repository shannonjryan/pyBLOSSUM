import numpy as np
import pandas as pd
import os
import sys
from matplotlib import pyplot as plt
import seaborn as sns
import warnings

plt.close('all')
sns.set()
warnings.filterwarnings("ignore", category=RuntimeWarning)  ## supress runtime warnings

'''
Reference: E Christiansen, J Kerr. 2001. Ballistic limit equations for spacecraft shielding, 
International Journal of Impact Engineering; 26: 93-104
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def modNNO_performance(row):
    
    ## define the remaining variables
    row['angle'] = 65 if row['angle'] > 65 else row['angle']
    anglerad = np.deg2rad(row['angle'])
    
    ## define the transition velocities
    vLV = 3/(np.cos(anglerad))**1.5
    vHV = 7/np.cos(anglerad)
    
    ## equation constants
    kl = 1.9
    kh = 1.35 if row['bumper_thick']/(row['wall_thick']**(2/3)*row['standoff']**(1/3)) < 0.126 else 7.451*row['bumper_thick']/(row['wall_thick']**(2/3)*row['standoff']**(1/3))+0.411
    
    ## calculate the ballistic limit
    if row['velocity'] <= vLV:  # low velocity regime
         dc = kl*(row['wall_thick']*(row['wall_yieldksi']/40)**0.5+0.37*row['bumper_thick']*row['bumper_density'])/ \
             ((np.cos(anglerad))**(11/6)*row['proj_density']**0.5*row['velocity']**(2/3))             
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = kh*(row['wall_thick']*row['wall_density'])**(2/3)*row['standoff']**(1/2)*(row['wall_yieldksi']/70)**(1/3)/ \
            (row['proj_density']**(1/3)*row['bumper_density']**(1/9)*(row['velocity']*np.cos(anglerad))**(2/3))
    else:  # shatter regime
        dcLV = kl*(row['wall_thick']*(row['wall_yieldksi']/40)**0.5+0.37*row['bumper_thick']*row['bumper_density'])/ \
            ((np.cos(anglerad))**(11/6)*row['proj_density']**0.5*vLV**(2/3))  
        dcHV = kh*(row['wall_thick']*row['wall_density'])**(2/3)*row['standoff']**(1/2)*(row['wall_yieldksi']/70)**(1/3)/ \
            (row['proj_density']**(1/3)*row['bumper_density']**(1/9)*(vHV*np.cos(anglerad))**(2/3))
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']-vLV)

    return dc  

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

## run the code to calculate critical diameter and generate ballistic limit curve
if __name__ == "__main__":
        
    ## import the data
    root_dir = os.path.dirname(os.getcwd())
    filename = sys.argv[1]
    df_data = pd.read_csv(os.path.join(root_dir,'data',filename))
        
    ## assess the BLE performance
    dc = np.array([])
    for index,row in df_data.iterrows():
        dc = np.append(dc,modNNO_performance(row))
        
    df_data.insert(loc=df_data.shape[1],column='dc_modNNO',value=dc)
       
    ## save the output
    df_data.to_csv(os.path.join(root_dir,'results',f'eval-modNNO-{filename}'),index=False)
    
    ## perforation & non-perforation results
    df_P = df_data.loc[df_data['perforated_class'] == 1]
    df_NP = df_data.loc[df_data['perforated_class'] == 0]
    
    ## generate ballistic limit curves
    V_plot = np.linspace(0.1,15,150)
    df_plot = pd.DataFrame()
    df_temp = pd.Series(df_data.iloc[0])
    for vel in V_plot:
        df_temp['velocity'] = vel
        df_temp['dc'] = modNNO_performance(df_temp)
        df_plot = pd.concat([df_plot,df_temp],ignore_index=True,axis=1)
    
    df_plot = df_plot.transpose()
    
    ## save the plot data to file
    df_plot.to_csv(os.path.join(root_dir,'results',f'plotdata-modNNO-{filename}'),index=False)
    
    plt.figure()
    plt.plot(df_plot['velocity'],df_plot['dc'],label='mod NNO')
    plt.scatter(df_P['velocity'],df_P['proj_diam'],c='w',edgecolors='k',label='P')
    plt.scatter(df_NP['velocity'],df_NP['proj_diam'],c='k',edgecolors='k',label='NP')
    plt.xlabel('Velocity (km/s)')
    plt.ylabel('Projectile diameter (cm)')
    plt.ylim(0.0,2.0*df_plot['dc'][71])
    plt.legend()
        
    # plt.show()
    plt.savefig(os.path.join(root_dir,'plots',f'plot-modNNO-{filename.split(".")[0]}.png'))

