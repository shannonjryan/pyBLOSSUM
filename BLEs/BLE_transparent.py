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
[1] BG Cour-Palais, Hypervelocity Impact in Metals, Glass, and Composites,
International Journal of Impact Engineering; 5: pp. 221-237, 1987.
[2] EL Christiansen, RR Burt, Hypervelocity Impact Testing of Transparent 
Spacecraft Materials, International Journal of Impact Engineering; 29: 153-166, 2003.
[3] S Ryan, EL Christiansen, Micrometeoroid and orbital debris (MMOD) shield
ballistic limit analysis program, NASA Johnson Space Center, NASA/TM-2009-214789, 2009.
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def transparent_performance(row):

    ## convert to radians
    anglerad = np.deg2rad(row['angle'])
    
    ## calculate the configuration-specific constants
    if row['type'] == 'Silica':
        k = 2.0 if row['mode'] == 'Perforate' else 3.0 if row['mode'] == 'Detached spall' else 7.0
        Q = 1.89
        K1 = 30.9
        alpha = 0.5
        beta = 2/3
        gamma = 18/19
        
    elif row['type'] == 'Quartz':
        k = 2.0 if row['mode'] == 'Perforate' else 3.0 if row['mode'] == 'Detached spall' else 7.0
        Q = 1.32
        K1 = 15.1
        alpha = 0.5
        beta = 2/3
        gamma = 18/19
        
    elif row['type'] == 'Polycarbonate':
        k = 1/1.04 if row['mode'] == 'Perforate' else 1/0.98 if row['mode'] == 'Detached spall' else 1/0.65
        Q = 1
        K1 = 1  # the max damage failure criteria is not valid for polycarbonate
        alpha = 1/3
        beta = 1/3
        gamma = 1
        
    ## Ballistic limit calculation
    if row['mode'] == 'Damage':  # surface damage requirement
        dc = (row['max_damage']/(K1*row['proj_density']**0.44*(row['velocity']*np.cos(anglerad))**0.44))**(1/1.33)
    else:  # penetration-based requirement
        dc = (Q*row['thickness']/(k*row['proj_density']**alpha*row['velocity']**(2/3)*(np.cos(anglerad))**beta))**gamma

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
        df_plot['dc_BLE'] = df_plot.apply(transparent_performance,axis=1)
        
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
