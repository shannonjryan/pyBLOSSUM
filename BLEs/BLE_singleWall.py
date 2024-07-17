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
[1] EL Christiansen. “Shield Sizing and Response Equations.” SN3-91-42. 
NASA Johnson Space Center, Houston. 1991
[2] M. Ratliff. "Single-wall equation for titanium shield", NESC Study of
meteoroid protection for JWST cryogenic harnesses, May 2008
[3] EL Christiansen et al. 2009. Handbook for designing MMOD protection,
NASA Johnson Space Center, Houston, NASA/TM-2009-214785
[4] FK Schaefer, E Schneider, M Lambert. Review of Ballistic Limit
Equations for CFRP Structure Walls of Satellites. Proceedings of the 5th
International Symposium on Environmental Testing for Space Programmes, 
ESA SP-558, Noordwijk, June 15-17, 2004
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def singleWall_performance(row):

    ## convert the angle to radians
    anglerad = np.deg2rad(row['angle'])
    
    ## calculate the configuration-specific constants
    if row['type'] == 'TI':
        alpha = row['shield_HB']**0.25
        beta = 0.5
        k = 1.8 if row['mode'] == 'perforate' else 2.4 if row['mode'] == 'detached_spall' else 3.0
        K = 5.24/row['shield_C']**(2/3)
        gamma = 1

    elif row['type'] == 'ST':
        alpha = 1
        beta = 0.5
        k = 1.8  # no perforation
        K = 0.345
        gamma = 18/19
        
    elif row['type'] == 'AL':
        alpha = row['shield_HB']**0.25
        beta = 0.5 if row['proj_density']/row['shield_density'] < 1.5 else 3/2
        k = 1.8 if row['mode'] == 'perforate' else 2.2 if row['mode'] == 'detached_spall' else 3.0
        K = 5.24/row['shield_C']**(2/3)
        gamma = 18/19
        
    elif row['type'] == 'CFRP':
        alpha = 1
        beta = 0.5
        k = 1.8 if row['mode'] == 'perforate' else 3.0 
        K = 0.62
        gamma = 1

    elif row['type'] == 'fibreglass':
        alpha = 1
        beta = 0.5
        k = 1.8  # no perforation
        K = 0.434
        gamma = 1        

    ## Ballistic limit calculation
    if row['MLI_AD'] == 0:  # no MLI
        dc = (row['shield_thick']*alpha*(row['shield_density']/row['proj_density'])**beta/(k*K*(row['velocity']*np.cos(anglerad))**(2/3)))**gamma
    elif row['MLI_AD'] > 0:
        if row['type'] == 'TI' or row['type'] == 'ST' or row['type'] == 'AL':
            delta_dc = 2.2*row['MLI_AD']*row['proj_density']**-0.47*(row['velocity']*np.cos(anglerad))**-0.63   # from [3]
            dc = (row['shield_thick']*alpha*(row['shield_density']/row['proj_density'])**beta/(k*K*(row['velocity']*np.cos(anglerad))**(2/3)))**gamma + delta_dc
        elif row['type'] == 'CFRP' or row['type'] == 'fibreglass':
            tb = row['shield_thick'] + 4.5*row['MLI_AD']/row['shield_density']  # from [4]
            dc = (tb*alpha*(row['shield_density']/row['proj_density'])**beta/(k*K*(row['velocity']*np.cos(anglerad))**(2/3)))**gamma
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

        ## generate ballistic limit curves
        velocities = np.linspace(0.1,15,150)
        df_plot = pd.DataFrame(np.repeat(df_data.values, len(velocities), axis=0), columns=df_data.columns)  # takes the first row of the imported dataframe and duplicates it to match the size of the 'velocities' vector
        df_plot['velocity'] = velocities
        df_plot['dc_BLE'] = df_plot.apply(singleWall_performance,axis=1)

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