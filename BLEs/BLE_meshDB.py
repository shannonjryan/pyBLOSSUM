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
[1] EL Christiansen, JH Kerr. Mesh double-bumper shield: a low-weight alternative
for spacecraft meteoroid and orbital debris protection. International Journal of
Impact Engineering; 14(1-4): 169-180, 1993
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def meshDB_performance(row):

    ## convert the angle to radians
    anglerad = np.deg2rad(row['angle'])

    ## define the velocity regime transitions
    vLV = 2.8/(np.cos(anglerad))**0.5
    vHV = 6.4/(np.cos(anglerad))**(1/3)

    ## calculate the total bumper AD
    bumper_AD = row['mesh_AD'] + row['bumper_thick']*row['bumper_density'] + row['kevlar_AD']  # units = g/cm2

    if row['velocity'] <= vLV:  # low velocity regime
        dc = 2.2*(row['wall_thick']*(row['wall_yield']/40)**0.5+0.37*bumper_AD)/((np.cos(anglerad))**(5/3)*row['proj_density']**0.5*row['velocity']**(2/3))
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = 0.6*(row['wall_thick']*row['wall_density'])**(1/3)*row['standoff']**(1/2)*(row['wall_yield']/40)**(1/6)/(row['proj_density']**(1/3)*row['velocity']**(1/3)*(np.cos(anglerad))**(1/3))
    else:  # shatter regime
        dcLV = 2.2*(row['wall_thick']*(row['wall_yield']/40)**0.5+0.37*bumper_AD)/((np.cos(anglerad))**(5/3)*row['proj_density']**0.5*vLV**(2/3))
        dcHV = 0.6*(row['wall_thick']*row['wall_density'])**(1/3)*row['standoff']**(1/2)*(row['wall_yield']/40)**(1/6)/(row['proj_density']**(1/3)*vHV**(1/3)*(np.cos(anglerad))**(1/3))
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
        df_plot['dc_BLE'] = df_plot.apply(meshDB_performance,axis=1)
        
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