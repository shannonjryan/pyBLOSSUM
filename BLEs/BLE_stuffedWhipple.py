import numpy as np
import pandas as pd
import os
import argparse
from matplotlib import pyplot as plt
import seaborn as sns
import warnings

plt.close('all')
sns.set_theme()
warnings.filterwarnings("ignore", category=RuntimeWarning)  ## supress runtime warnings

'''
References:
[1] EL Christiansen, J Kerr. 2001. Ballistic limit equations for spacecraft
shielding, International Journal of Impact Engineering; 26: 93-104
[2] EL Christiansen et al. 2009. Handbook for designing MMOD protection,
NASA Johnson Space Center, Houston, NASA/TM-2009-214785
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def stuffedWhipple_performance(row):

    ## define the constants
    KLSW = 2.35
    CL = 0.37
    K_MLI = 3

    ## account for the presence of MLI by increasing the effective thickness of the front facesheet
    if row['AD_MLI'] > 0:
        rho_ref = 2.78
        tb_tot = row['bumper_thick']+K_MLI*row['AD_MLI']/rho_ref
    else:
        tb_tot = row['bumper_thick']

    ## calculate the areal densities
    ADb = tb_tot*row['bumper_density']+row['kevlar_AD']+row['nextel_AD']  # units = g/cm2
    ADshield = ADb+row['wall_thick']*row['wall_density']

    ## define the remaining equation constants
    if (row['kevlar_AD']+row['nextel_AD']) >= (0.1*ADshield) and (row['kevlar_AD']+row['nextel_AD']) <= (0.15*ADshield):  # page 60 from [2]
        KHSW = 0.45
    else:
        KHSW = 0.6  # specific limits are also defined for KHSW in [2] based on ADshield, however here they are implemented as a baseline

    ## convert the angle to radians
    anglerad = np.deg2rad(row['angle'])
    
    ## Define the impact velocity regimes
    vLV = 2.6/np.cos(anglerad)**0.5
    vHV = 6.5/np.cos(anglerad)**0.75
    
    # Ballistic limit calculation
    if row['velocity'] <= vLV:  # low velocity regime
        dc = KLSW*row['velocity']**(-2/3)*(np.cos(anglerad))**(-4/3)*row['proj_density']**(-1/2)*(row['wall_thick']*(row['wall_yield']/40)**0.5+CL*ADb)
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = KHSW*(row['wall_thick']*row['wall_density'])**(1/3)*row['proj_density']**(-1/3)*row['velocity']**(-1/3)*(np.cos(anglerad))**-0.5*row['standoff']**(2/3)*(row['wall_yield']/40)**(1/6)
    else:  # shatter regime
        dcLV = KLSW*vLV**(-2/3)*(np.cos(anglerad))**(-4/3)*row['proj_density']**(-1/2)*(row['wall_thick']*(row['wall_yield']/40)**0.5+CL*ADb)
        dcHV = KHSW*(row['wall_thick']*row['wall_density'])**(1/3)*row['proj_density']**(-1/3)*vHV**(-1/3)*(np.cos(anglerad))**-0.5*row['standoff']**(2/3)*(row['wall_yield']/40)**(1/6)
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']-vLV)    
    
    return dc



# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
## run the code to calculate critical diameter and generate ballistic limit curve
if __name__ == "__main__":

    from datetime import datetime

    ## Create the parser
    parser = argparse.ArgumentParser(description='Process analysis inputs and flags.')

    ## Add the arguments
    parser.add_argument('filename', type=str, help='The name and location of the file containing the analysis details, e.g., input_data/eval_example-foamSP.csv')
    parser.add_argument('--data', action='store_true', help='Flag indicating that relevant test data should be included in the ballistic limit plot')

    ## Parse the arguments
    args = parser.parse_args()       

    try:        
        # import the analysis details
        root_dir = os.getcwd() 
        filename = args.filename
        df_data = pd.read_csv(filename,skiprows=[1])

        ## convert units
        df_data['wall_yield'] *= 0.145038  # units = ksi        

        ## generate ballistic limit curves
        velocities = np.linspace(0.1,15,150)
        df_plot = pd.DataFrame(np.repeat(df_data.values, len(velocities), axis=0), columns=df_data.columns)  # takes the first row of the imported dataframe and duplicates it to match the size of the 'velocities' vector
        df_plot['velocity'] = velocities
        df_plot['dc_BLE'] = df_plot.apply(stuffedWhipple_performance,axis=1)

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

        ## If the test data flag is set, plot the test data
        if args.data:
            # Load the test data
            filename = 'database_stuffedWhipple_pyBLOSSUM.csv'
            df_test = pd.read_csv(os.path.join(root_dir,'data',filename),skiprows=[1])

            # Filter the test data based on the selected values
            lower_bound = 0.95
            upper_bound = 1.05
            mask = ((df_test['bumper_mat'].str[:9] == df_data['bumper_mat'][0][:9]) &  # allows for e.g., AA6061-T651 and AA6061-T6 to be handled as common materials
                    (df_test['bumper_thick'] >= lower_bound * df_data['bumper_thick'][0]) &
                    (df_test['bumper_thick'] <= upper_bound * df_data['bumper_thick'][0]) &
                    (df_test['standoff'] >= lower_bound * df_data['standoff'][0]) &
                    (df_test['standoff'] <= upper_bound * df_data['standoff'][0]) &
                    (df_test['stuffing_AD'] >= lower_bound * (df_data['kevlar_AD'][0]+df_data['nextel_AD'][0])) &
                    (df_test['stuffing_AD'] <= upper_bound * (df_data['kevlar_AD'][0]+df_data['nextel_AD'][0])) &                   
                    (df_test['wall_mat'].str[:9] == df_data['wall_mat'][0][:9]) &  # allows for e.g., AA6061-T651 and AA6061-T6 to be handled as common materials
                    (df_test['wall_thick'] >= lower_bound * df_data['wall_thick'][0]) &
                    (df_test['wall_thick'] <= upper_bound * df_data['wall_thick'][0]) &
                    (df_test['angle'] == df_data['angle'][0]))
            df_filtered_test_data = df_test[mask]
            df_NP = df_filtered_test_data[df_filtered_test_data['perforated_class'] == 0]
            df_P = df_filtered_test_data[df_filtered_test_data['perforated_class'] == 1]
            plt.scatter(df_NP['velocity'],df_NP['proj_diam'],edgecolors='black',facecolors='black',label='NP')
            plt.scatter(df_P['velocity'],df_P['proj_diam'],edgecolors='black',facecolors='white',label='P')
            df_filtered_test_data.to_csv(os.path.join(root_dir,"results",f"test_data_{now_str}.csv"), index=False) 

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
