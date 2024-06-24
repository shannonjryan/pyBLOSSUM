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
[1] S Ryan, F Schaefer, R Destefanis, M Lambert. 2007. A ballistic limit equation 
for hypervelocity impacts on composite honeycomb sandwich panel satellite structures,
Advances in Space Research; DOI:10.1016/j.asr.2007.02.032
[2] F Schaefer, S Ryan, M Lambert, R Putzar. 2008. Ballistic limit equation for 
equipment placed behind satellite structure walls, International Journal of Impact
Engineering; 35: 1784-1791, doi:10.1016/j.ijimpeng.2008.07.074
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def SRL_double_performance(row):

    ## define the equation constants
    K_MLI = 3
    K3D = 0.4
    
    ## define the reference material properties
    sigyksi_ref = 59.5
    rho_ref = 2.78

    ## handle the impact obliquity
    angledeg = row['angle']
    anglerad = np.deg2rad(angledeg)
    
    ## define the reference material properties (AA2024-T81)
    if row['bumper_mat'] == "CFRP":
        sigyksi = sigyksi_ref
        rhob = rho_ref
        tb = row['bumper_thick']*row['bumper_density']/rho_ref
        tw = row['wall_thick']*row['wall_density']/rho_ref
        tb_tot = tb+K_MLI*row['AD_MLI']/rho_ref
        vLV = 4.2/np.cos(anglerad)
        vHV = 8.4/np.cos(anglerad)
        delta = 4/3
        K3S = 1.1
    elif row['bumper_mat'] == "Other":
        sigyksi = sigyksi_ref
        rhob = rho_ref
        tb = row['bumper_thick']*row['bumper_density']/rho_ref
        tw = row['wall_thick']*row['wall_density']/rho_ref
        tb_tot = tb+K_MLI*row['AD_MLI']/rho_ref
        vLV = 3/np.cos(anglerad)
        vHV = 7/np.cos(anglerad)
        if angledeg <= 45 or angledeg >= 65:
            delta = 4/3
        else:
            delta = 5/4
        K3S = 1.4
    else:
        sigyksi = row['wall_yield']
        rhob = row['bumper_density']
        tb = row['bumper_thick']
        tw = row['wall_thick']
        tb_tot = tb+K_MLI*row['AD_MLI']/rho_ref
        vLV = 3/np.cos(anglerad)
        vHV = 7/np.cos(anglerad)
        if angledeg <= 45 or angledeg >= 65:
            delta = 4/3
        else:
            delta = 5/4
        K3S = 1.4
        
    # Ballistic limit calculation
    if row['velocity'] <= vLV:  # low velocity regime
        dc = ((tw/K3S*(sigyksi/40)**0.5+tb_tot)/(0.6*(np.cos(anglerad))**delta*row['proj_density']**0.5*row['velocity']**(2/3)))**(18/19)
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = (1.155*(row['standoff']**(1/3)*tw**(2/3))*(sigyksi/70)**(1/3))/(K3D**(2/3)*row['proj_density']**(1/3)*rhob**(1/9)*row['velocity']**(2/3)*(np.cos(anglerad))**delta)
    else:  # shatter regime
        dcLV = ((tw/K3S*(sigyksi/40)**0.5+tb_tot)/(0.6*(np.cos(anglerad))**delta*row['proj_density']**0.5*vLV**(2/3)))**(18/19)
        dcHV = (1.155*(row['standoff']**(1/3)*tw**(2/3))*(sigyksi/70)**(1/3))/(K3D**(2/3)*row['proj_density']**(1/3)*rhob**(1/9)*vHV**(2/3)*(np.cos(anglerad))**delta)
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']-vLV) 
    
    return dc

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def SRL_triple_performance(row):

    ## define the equation constants
    K_MLI = 3
    K3D = 0.4
    
    ## define the reference material properties (AA2024-T81)
    # sigyksi_ref = 59.5
    rho_ref = 2.78

    ## handle the impact obliquity
    angledeg = 65 if row['angle'] > 65 else row['angle']
    anglerad = np.deg2rad(angledeg)
    
    ## Define the material-dependent constants for the outer bumper
    if row['outerBumper_mat'] == "CFRP":
        tob = row['outerBumper_thick']*row['outerBumper_density']/rho_ref
        tob_tot = tob+K_MLI*row['AD_MLI']/rho_ref
        vLV = 4.2/np.cos(anglerad)
        vHV = 8.4/np.cos(anglerad)
        K3S = 1.1
        KS2 = 1
        KTW = 1
        beta = 1/3
        delta = 4/3
        epsilon = 0
        gamma = 2/3
    else:
        tob_tot = row['outerBumper_thick']+K_MLI*row['AD_MLI']/rho_ref
        vLV = 3/np.cos(anglerad)
        vHV = 7/np.cos(anglerad)
        K3S = 1.4
        KS2 = 0.1
        KTW = 1.5
        beta = 2/3
        if angledeg <= 45 or angledeg >= 65:
            delta = 4/3
            epsilon = 8/3
        else:
            delta = 5/4
            epsilon = 10/4
        gamma = 1/3
    
    ## Define the material-dependent constants for the inner bumper
    if row['innerBumper_mat'] == "CFRP":
        rhob = rho_ref
        tb = row['innerBumper_thick']*row['innerBumper_density']/rho_ref
    else:
        rhob = row['innerBumper_density']
        tb = row['innerBumper_thick']
    
    ## Ballistic limit calculation
    if row['velocity'] <= vLV:  # low velocity regime
        dc = (((row['wall_thick']**0.5+tb)/K3S*(row['wall_yield']/40)**0.5+tob_tot)/(0.6*(np.cos(anglerad))**delta*row['proj_density']**0.5*row['velocity']**(2/3)))**(18/19)
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = (1.155*(row['standoff1']**(1/3)*(tb+KTW*row['wall_thick'])**(2/3)+KS2*row['standoff2']**beta*row['wall_thick']**gamma*np.cos(anglerad)**(-epsilon))*(row['wall_yield']/70)**(1/3))/(K3D**(2/3)*row['proj_density']**(1/3)*rhob**(1/9)*row['velocity']**(2/3)*(np.cos(anglerad))**delta)
    else:  # shatter regime
        dcLV = (((row['wall_thick']**0.5+tb)/K3S*(row['wall_yield']/40)**0.5+tob_tot)/(0.6*(np.cos(anglerad))**delta*row['proj_density']**0.5*vLV**(2/3)))**(18/19)
        dcHV = (1.155*(row['standoff1']**(1/3)*(tb+KTW*row['wall_thick'])**(2/3)+KS2*row['standoff2']**beta*row['wall_thick']**gamma*np.cos(anglerad)**(-epsilon))*(row['wall_yield']/70)**(1/3))/(K3D**(2/3)*row['proj_density']**(1/3)*rhob**(1/9)*vHV**(2/3)*(np.cos(anglerad))**delta)
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
        if df_plot.iloc[0]['type'] == 'double':
            df_plot['dc_BLE'] = df_plot.apply(SRL_double_performance,axis=1)
        elif df_plot.iloc[0]['type'] == 'triple':
            df_plot['dc_BLE'] = df_plot.apply(SRL_triple_performance,axis=1)
        
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
        plt.plot(df_plot['velocity'],df_plot['dc_BLE'],label='BLE-SRL')
        plt.xlabel('Velocity (km/s)')
        plt.ylabel('Projectile diameter (cm)')

        ## If the test data flag is set, plot the test data
        if args.data and df_data.iloc[0]['type'] == 'double':
            # Load the test data
            filename = 'database_HCSP_pyBLOSSUM.csv'
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