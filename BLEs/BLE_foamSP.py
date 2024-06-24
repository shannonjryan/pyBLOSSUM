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
[1] S Ryan, E Ordonez, EL Christiansen, DM Lear. 2009. Hypervelocity impact 
performance of open cell foam core sandwich panel structures, Proceedings of the 
Hypervelocity Impact Symposium, Freiburg
[2] S Ryan, EL Christiansen. 2015. Hypervelocity impact testing of aluminum 
foam core sandwich panels, NASA Johnson Space Center, Houston, NASA/TM-2015-218593
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def foamSP_performance(row):
   
    ## define the constants
    C1 = 1.83
    C2 = 1.1
    C3 = 0.89
    K_MLI = 3
    
    ## convert the angle to radians
    anglerad = np.deg2rad(row['angle'])
            
    ## define the velocity regime transitions
    vLV = 2.25/(np.cos(anglerad))**(1/3)
    vHV = 4.0/(np.cos(anglerad))**(1/3)
    
    ## calculate the missing information (user must input either SP mass, foam AD, or foam density)
    if row['SP_mass'] != 0:
        SP_AD = row['SP_mass']/(row['standoff']+row['bumper_thick']+row['wall_thick'])  # units = g/cm2
        foam_AD = SP_AD-row['bumper_thick']*row['bumper_density']-row['wall_thick']*row['wall_density']  # units = g/cm2
        foam_density = foam_AD/row['standoff']  # units = g/cm3
    elif row['SP_AD'] != 0:
        foam_AD = row['SP_AD']-row['bumper_thick']*row['bumper_density']-row['wall_thick']*row['wall_density']
        foam_density = foam_AD/row['standoff']    # units = g/cm3
    elif row['foam_density'] != 0:
        foam_density = row['foam_density']    # units = g/cm3
        foam_AD = row['foam_density']*row['standoff']  # units = g/cm2
    elif row['foam_AD'] != 0:
        foam_density = row['foam_AD']/row['standoff']  # units = g/cm3
        foam_AD = row['foam_AD']

    ## account for the presence of MLI by increasing the effective thickness of the front facesheet
    if row['AD_MLI'] > 0:
        rho_ref = 2.78
        tb_tot = row['bumper_thick']+K_MLI*row['AD_MLI']/rho_ref
    else:
        tb_tot = row['bumper_thick']
    
    # Ballistic limit calculation
    if row['velocity'] <= vLV:  # low velocity regime
        dc = C1*(tb_tot+row['wall_thick']*(row['wall_yield']/40)**(1/2)+row['standoff']**C2*(foam_density/row['wall_density']))/(row['proj_density']**(1/2)*row['velocity']**(2/3)*np.cos(anglerad)**(4/5))**(18/19)
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = 2.152*(row['wall_thick']+0.5*foam_AD/row['wall_density'])**(2/3)*C3*row['standoff']**(9/20)*(row['wall_yield']/70)**(1/3)/(row['proj_density']**(1/3)*row['bumper_density']**(1/9)*row['velocity']**(2/5)*np.cos(anglerad)**(4/5))
    else:  # shatter regime
        dcLV = C1*(tb_tot+row['wall_thick']*(row['wall_yield']/40)**(1/2)+row['standoff']**C2*(foam_density/row['wall_density']))/(row['proj_density']**(1/2)*vLV**(2/3)*np.cos(anglerad)**(4/5))**(18/19)
        dcHV = 2.152*(row['wall_thick']+0.5*foam_AD/row['wall_density'])**(2/3)*C3*row['standoff']**(9/20)*(row['wall_yield']/70)**(1/3)/(row['proj_density']**(1/3)*row['bumper_density']**(1/9)*vHV**(2/5)*np.cos(anglerad)**(4/5))
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
        ## import the analysis details
        root_dir = os.getcwd()
        filename = args.filename
        df_data = pd.read_csv(filename,skiprows=[1]) 

        ## convert units
        df_data['wall_yield'] *= 0.145038  # units = ksi        
        
        ## generate ballistic limit curves
        velocities = np.linspace(0.1,15,150)
        df_plot = pd.DataFrame(np.repeat(df_data.values, len(velocities), axis=0), columns=df_data.columns)  # takes the first row of the imported dataframe and duplicates it to match the size of the 'velocities' vector
        df_plot['velocity'] = velocities
        df_plot['dc_BLE'] = df_plot.apply(foamSP_performance,axis=1)
        
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
            filename = 'database_foamSP_pyBLOSSUM.csv'
            df_test = pd.read_csv(os.path.join(root_dir,'data',filename),skiprows=[1])

            # Filter the test data based on the selected values
            lower_bound = 0.95
            upper_bound = 1.05
            mask = ((df_test['bumper_mat'].str[:9] == df_data['bumper_mat'][0][:9]) &  # allows for e.g., AA6061-T651 and AA6061-T6 to be handled as common materials
                    (df_test['bumper_thick'] >= lower_bound * df_data['bumper_thick'][0]) &
                    (df_test['bumper_thick'] <= upper_bound * df_data['bumper_thick'][0]) &
                    (df_test['standoff'] >= lower_bound * df_data['standoff'][0]) &
                    (df_test['standoff'] <= upper_bound * df_data['standoff'][0]) &
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