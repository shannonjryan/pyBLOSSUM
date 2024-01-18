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
Reference: E Christiansen. 1993. Design and performance equations for advanced
meteoroid and debris shields, International Journal of Impact Engineering; 14: 145-156
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def NNO_performance(row):
    
    ## define the remaining variables
    vLV = 3
    vHV = 7
    row['angle'] = 65 if row['angle'] > 65 else row['angle']
    anglerad = np.deg2rad(row['angle'])
    vn = row['velocity']*np.cos(anglerad)
    
    if vn <= vLV:  # low velocity regime
         dc = ((row['wall_thick']*(row['wall_yield']/40)**0.5+row['bumper_thick'])/(0.6*(np.cos(anglerad))**(5/3)*row['proj_density']**0.5*row['velocity']**(2/3)))**(18/19)
    elif vn >= vHV:  # hypervelocity regime
        dc = 3.918*row['wall_thick']**(2/3)*row['standoff']**(1/3)*(row['wall_yield']/70)**(1/3)/(row['proj_density']**(1/3)*row['bumper_density']**(1/9)*(row['velocity']*np.cos(anglerad))**(2/3))
    else:  # shatter regime
        dcLV = ((row['wall_thick']*(row['wall_yield']/40)**0.5+row['bumper_thick'])/(0.6*(np.cos(anglerad))**(5/3)*row['proj_density']**0.5*(vLV/np.cos(anglerad))**(2/3)))**(18/19)
        dcHV = 3.918*row['wall_thick']**(2/3)*row['standoff']**(1/3)*(row['wall_yield']/70)**(1/3)/(row['proj_density']**(1/3)*row['bumper_density']**(1/9)*vHV**(2/3))
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']*np.cos(anglerad)-vLV)

    return dc

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def NNO_design(row):

    row['angle'] = 65 if row['angle'] > 65 else row['angle']
    anglerad = np.deg2rad(row['angle'])

    # sizing coefficients
    cb = 0.25 if row['standoff']/row['proj_dia'] < 30 else 0.2
    cw = 0.16

    # sizing the shield
    tb = cb*row['proj_dia']*row['proj_density']/row['bumper_density']
    tw = cw*row['proj_dia']**0.5*(row['proj_density']*row['bumper_density'])**(1/6)*(np.pi/6*row['proj_dia']**3*row['proj_density'])**(1/3)*(row['velocity']*np.cos(anglerad)/row['standoff']**0.5)*(70/row['wall_yield'])**0.5

    t = [tb,tw]

    return t

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
## run the code to calculate critical diameter and generate ballistic limit curve
if __name__ == "__main__":
        
    ## import the data
    root_dir = os.path.dirname(os.getcwd())
    filename = sys.argv[1]
    # filename = 'eval_example.csv'
    df_data = pd.read_csv(os.path.join(root_dir,'data',filename))
    
    ## assess the BLE performance
    dc = np.array([])
    for index,row in df_data.iterrows():
        dc = np.append(dc,NNO_performance(row))
        
    df_data.insert(loc=df_data.shape[1],column='dc_NNO',value=dc)
       
    ## save the output
    df_data.to_csv(os.path.join(root_dir,'results',f'eval-NNO-{filename}'),index=False)
    
    ## perforation & non-perforation results
    df_P = df_data.loc[df_data['perforated_class'] == 1]
    df_NP = df_data.loc[df_data['perforated_class'] == 0]    
       
    ## generate ballistic limit curves
    V_plot = np.linspace(0.1,15,150)
    df_plot = pd.DataFrame()
    df_temp = pd.Series(df_data.iloc[0])
    features = ['proj_mat','proj_density','angle','bumper_mat','bumper_thick','bumper_density','standoff','wall_thick','wall_mat','wall_density','wall_yield']
    df_temp = df_temp[features]
    for vel in V_plot:
        df_temp['velocity'] = vel
        df_temp['dc'] = NNO_performance(df_temp)
        df_plot = pd.concat([df_plot,df_temp],ignore_index=True,axis=1)
    
    df_plot = df_plot.transpose()
    
    ## save the plot data to file
    df_plot.to_csv(os.path.join(root_dir,'results',f'plotdata-NNO-{filename}'),index=False)
    
    ## plot the results
    plt.figure()
    plt.plot(df_plot['velocity'],df_plot['dc'],label='NNO')
    plt.scatter(df_P['velocity'],df_P['proj_diam'],c='w',edgecolors='k',label='P')
    plt.scatter(df_NP['velocity'],df_NP['proj_diam'],c='k',edgecolors='k',label='NP')
    plt.xlabel('Velocity (km/s)')
    plt.ylabel('Projectile diameter (cm)')
    plt.ylim(0.0,2.0*df_plot['dc'][71])
    plt.legend()
        
    # plt.show()
    plt.savefig(os.path.join(root_dir,'plots',f'plot-NNO-{filename.split(".")[0]}.png'))
