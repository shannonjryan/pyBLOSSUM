import numpy as np
import pandas as pd
import os
import sys
from matplotlib import pyplot as plt
import seaborn as sns
import warnings

plt.close('all')
sns.set_theme()
warnings.filterwarnings("ignore", category=RuntimeWarning)  ## supress runtime warnings

'''
References:
[1] EL Christiansen. 2003. Meteoroid/Debris shielding. NASA Johnson Space Center,
Houston, NASA/TP-2003-210788.
[2] EL Christiansen et al. 2009. Handbook for designing MMOD protection,
NASA Johnson Space Center, Houston, NASA/TM-2009-214785
[3] S Ryan, EL Christiansen. 2009. Micrometeoroid and orbital debris (MMOD) shield
ballistic limit analysis program, NASA Johnson Space Center, Houston, NASA/TM-2009-214789 
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def multishockNextel_performance(row):
    '''
    Multi-shock shield with four Nextel bumper and a Fabric rear wall
    Eq. 79, 82, and 85 from [3]
    '''

    ## define the equation constants
    KL = 2.7  # units = g^(1/2)*km^(2/3)/(cm^(3/2)*s^(2/3))
    KH = 43.6
    CL = 0.37  # units = cm3/g
    CW = 0.5  # units = cm3/g

    ## convert the angle to radians
    anglerad = np.deg2rad(row['angle'])

    ## define the velocity regime transitions
    vLV = 2.4/(np.cos(anglerad))**0.5
    vHV = 6.4/(np.cos(anglerad))**0.25

    ## Ballistic limit calculation
    if row['velocity'] <= vLV:  # low velocity regime
        dc = KL*(CW*row['wall_AD']+CL*row['bumper_AD'])/((np.cos(anglerad))**(4/3)*row['proj_density']**0.5*row['velocity']**(2/3))
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = 1.24*row['wall_AD']**(1/3)*row['standoff']**(2/3)/(43.6**(1/3)*row['proj_density']**(1/3)*row['velocity']**(1/3)*(np.cos(anglerad))**(1/3))
    else:  # shatter regime
        dcLV = KL*(CW*row['wall_AD']+CL*row['bumper_AD'])/((np.cos(anglerad))**(4/3)*row['proj_density']**0.5*vLV**(2/3))
        dcHV = 1.24*row['wall_AD']**(1/3)*row['standoff']**(2/3)/(KH**(1/3)*row['proj_density']**(1/3)*vHV**(1/3)*(np.cos(anglerad))**(1/3))
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']-vLV)   

    return dc


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def multishockKevlar_performance(row):
    '''
    Multi-shock shield with four Nextel bumper and a Fabric rear wall
    Eq. 79, 82, and 85 from [3]
    '''

    ## define the equation constants
    KL = 2.7  # units = g^(1/2)*km^(2/3)/(cm^(3/2)*s^(2/3))
    KH = 29.0
    CL = 0.37  # units = cm3/g
    CW = 0.5  # units = cm3/g

    ## convert the angle to radians
    anglerad = np.deg2rad(row['angle'])

    ## define the velocity regime transitions
    vLV = 2.4/(np.cos(anglerad))**0.5
    vHV = 6.4/(np.cos(anglerad))**0.25

    ## Ballistic limit calculation
    if row['velocity'] <= vLV:  # low velocity regime
        dc = KL*(CW*row['wall_AD']+CL*row['bumper_AD'])/((np.cos(anglerad))**(4/3)*row['proj_density']**0.5*row['velocity']**(2/3))
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = 1.24*row['wall_AD']**(1/3)*row['standoff']**(2/3)/(KH**(1/3)*row['proj_density']**(1/3)*row['velocity']**(1/3)*(np.cos(anglerad))**(1/3))
    else:  # shatter regime
        dcLV = KL*(CW*row['wall_AD']+CL*row['bumper_AD'])/((np.cos(anglerad))**(4/3)*row['proj_density']**0.5*vLV**(2/3))
        dcHV = 1.24*row['wall_AD']**(1/3)*row['standoff']**(2/3)/(KH**(1/3)*row['proj_density']**(1/3)*vHV**(1/3)*(np.cos(anglerad))**(1/3))
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']-vLV)   

    return dc


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def multishockAl_performance(row):
    '''
    Multi-shock shield with four Nextel bumper and an aluminium rear wall
    Eq. 4-25 through 4-37 from [1] 
    '''

    ## define the equation constants
    KL = 2.0  # units = g^(1/2)*km^(2/3)/(cm^(3/2)*s^(2/3))
    KH = 0.358  # units = km^(1/3)/(s^(1/3))
    CL = 0.37  # units = cm3/g

    ## convert the angle to radians
    anglerad = np.deg2rad(row['angle'])

    ## define the velocity regime transitions
    vLV = 2.4/(np.cos(anglerad))**0.5
    vHV = 6.4/(np.cos(anglerad))**0.25

    ## Ballistic limit calculation
    if row['velocity'] <= vLV:  # low velocity regime
        dc = KL*(row['wall_thick']*(row['wall_yield']/40)**0.5+CL*row['bumper_AD'])/((np.cos(anglerad))**(4/3)*row['proj_density']**0.5*row['velocity']**(2/3))
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = KH*(row['wall_thick']*row['wall_density'])**(1/3)*(row['wall_yield']/40)**(1/6)*row['standoff']**(2/3)/(row['proj_density']**(1/3)*row['velocity']**(1/3)*(np.cos(anglerad))**(1/3))
    else:  # shatter regime
        dcLV = KL*(row['wall_thick']*(row['wall_yield']/40)**0.5+CL*row['bumper_AD'])/((np.cos(anglerad))**(4/3)*row['proj_density']**0.5*vLV**(2/3))
        dcHV = KH*(row['wall_thick']*row['wall_density'])**(1/3)*(row['wall_yield']/40)**(1/6)*row['standoff']**(2/3)/(row['proj_density']**(1/3)*vHV**(1/3)*(np.cos(anglerad))**(1/3))
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']-vLV)   

    return dc

    
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def multishockHybrid_performance(row):
    '''
    Hybrid multi-shock shield with two Nextel bumpers, an aluminium bumper, and
    an aluminium rear wall
    Eq. 4-62 through 4-64 from [2] 
    '''

    ## define the equation constants
    CL = 0.37
    if row['angle'] <= 45:
        x = 7/3
    else:
        x = 2

    ## handle the impact obliquity
    angledeg = 75 if row['angle'] > 75 else row['angle']
    anglerad = np.deg2rad(angledeg)

    ## define the velocity regime transitions
    vLV = 2.7/(np.cos(anglerad))**0.5
    vHV = 6.5/(np.cos(anglerad))**(2/3)
    
    ## Ballistic limit calculation
    if row['velocity'] <= vLV:  # low velocity regime
        dc = 2.0*(row['wall_thick']*(row['wall_yield']/40)**0.5+CL*row['bumper_AD'])/((np.cos(anglerad))**x*row['proj_density']**0.5*row['velocity']**(2/3))
    elif row['velocity'] >= vHV:  # hypervelocity regime
        # dc = 2.4*(row['wall_thick']*row['wall_density'])**(2/3)*(row['wall_yield']/40)**(1/3)*row['standoff']**(1/3)/((np.cos(anglerad))**(2/3)*row['proj_density']**(1/3)*row['velocity']**(2/3)*row['bumper_density']**(1/9))
        dc = 2.15*(row['wall_thick']*row['wall_density'])**(2/3)*(row['wall_yield']/40)**(1/3)*row['standoff']**(1/3)/((np.cos(anglerad))**(2/3)*row['proj_density']**(1/3)*row['velocity']**(2/3))
    else:  # shatter regime
        dcLV = 2.0*(row['wall_thick']*(row['wall_yield']/40)**0.5+CL*row['bumper_AD'])/((np.cos(anglerad))**x*row['proj_density']**0.5*vLV**(2/3))
        # dcHV = 2.4*(row['wall_thick']*row['wall_density'])**(2/3)*(row['wall_yield']/40)**(1/3)*row['standoff']**(1/3)/((np.cos(anglerad))**(2/3)*row['proj_density']**(1/3)*vHV**(2/3)*row['bumper_density']**(1/9))
        dcHV = 2.15*(row['wall_thick']*row['wall_density'])**(2/3)*(row['wall_yield']/40)**(1/3)*row['standoff']**(1/3)/((np.cos(anglerad))**(2/3)*row['proj_density']**(1/3)*vHV**(2/3))
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']-vLV)
    
    return dc


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
## run the code to calculate critical diameter and generate ballistic limit curve
if __name__ == "__main__":

    from datetime import datetime

    try:        
        ## import the analysis details
        root_dir = os.getcwd()
        filename = sys.argv[1]
        df_data = pd.read_csv(filename,skiprows=[1])

        ## convert units
        df_data['wall_yield'] *= 0.145038  # units = ksi        
        
        ## generate ballistic limit curves
        velocities = np.linspace(0.1,15,150)
        df_plot = pd.DataFrame(np.repeat(df_data.values, len(velocities), axis=0), columns=df_data.columns)  # takes the first row of the imported dataframe and duplicates it to match the size of the 'velocities' vector
        df_plot['velocity'] = velocities
        if df_plot.iloc[0]['type'] == 'nextel':
            df_plot['dc_BLE'] = df_plot.apply(multishockNextel_performance,axis=1)
        if df_plot.iloc[0]['type'] == 'kevlar':
            df_plot['dc_BLE'] = df_plot.apply(multishockKevlar_performance,axis=1)        
        elif df_plot.iloc[0]['type'] == 'aluminium':
            df_plot['dc_BLE'] = df_plot.apply(multishockAl_performance,axis=1)
        elif df_plot.iloc[0]['type'] == 'hybrid':
            df_plot['dc_BLE'] = df_plot.apply(multishockHybrid_performance,axis=1)
        
        ## Get the current date and time
        now = datetime.now()
        now_str = now.strftime("%Y%m%d_%H%M%S")
        
        ## save the plot data to file
        # Check if the "results" directory exists, and create it if it doesn't
        results_dir = os.path.join(root_dir, "results")
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)    
        df_results = df_plot[['velocity', 'dc_BLE']] 
        df_results.to_csv(os.path.join(root_dir,"results",f"blc_data_{now_str}.csv"), index=False)     

        ## save the configuration to file (for file name consistency)
        df_data.to_csv(os.path.join(root_dir,"results",f"config_data_{now_str}.csv"), index=False)    

        ## plot the results
        plt.figure()
        plt.plot(df_plot['velocity'],df_plot['dc_BLE'],label='BLE')
        plt.xlabel('Velocity (km/s)')
        plt.ylabel('Projectile diameter (cm)')
        plt.ylim(0.0,2.0*df_plot['dc_BLE'][len(velocities)/2])
        plt.legend()
        # plt.show()
        
        ## Save the plot
        plt.savefig(os.path.join(root_dir,'results',f'plot_{now_str}.png'))

        ## Print completion statements
        print(f"Ballistic limit plot saved to file: plot_{now_str}.png")
        print(f"Ballistic limit curve data saved to file: blc_data_{now_str}.csv")
        print(f"Configuration data saved to file: config_data_{now_str}.csv")             

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        # Code to clean up resources here
        plt.close('all')