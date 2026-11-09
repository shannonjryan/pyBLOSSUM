import numpy as np
if __package__:
    from .curve_utils import algebraic_whipple_curve
else:
    from curve_utils import algebraic_whipple_curve
import pandas as pd
import os
from matplotlib import pyplot as plt
import seaborn as sns
import warnings
import argparse
import sys

plt.close('all')
sns.set_theme()
warnings.filterwarnings("ignore", category=RuntimeWarning)  ## supress runtime warnings

'''
Reference: E Christiansen, J Kerr. 2001. Ballistic limit equations for spacecraft shielding, 
International Journal of Impact Engineering; 26: 93-104
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def impact_angle_rad(angle_deg):
    return np.deg2rad(min(angle_deg, 65))


def modNNO_performance(row):
    
    ## define the obliquity limit
    anglerad = impact_angle_rad(row['angle'])

    ## account for the presence of MLI
    if row['S_MLI'] > 0:  # internal MLI
        K_MLI = 1.4
        vLV = 2.0/np.cos(anglerad)**1.5
        delta_dcHV = K_MLI*row['AD_MLI']*(row['S_MLI']/row['standoff'])**(1/2)
        tb_tot = row['bumper_thick']
    else:  # external MLI
        K_MLI = 3
        if row['AD_MLI'] > 0:
            rho_ref = 2.78
            tb_tot = row['bumper_thick']+K_MLI*row['AD_MLI']/rho_ref
        else:
            tb_tot = row['bumper_thick']
        vLV = 3/(np.cos(anglerad))**1.5
        delta_dcHV = 0

    ## define the transition velocities
    vHV = 7/np.cos(anglerad)
    
    ## equation constants
    kl = 1.9
    kh = 1.35 if tb_tot/(row['wall_thick']**(2/3)*row['standoff']**(1/3)) < 0.126 else 7.451*tb_tot/(row['wall_thick']**(2/3)*row['standoff']**(1/3))+0.411
    
    ## calculate the ballistic limit
    if row['velocity'] <= vLV:  # low velocity regime
         dc = kl*(row['wall_thick']*(row['wall_yield']/40)**0.5+0.37*tb_tot*row['bumper_density'])/ \
             ((np.cos(anglerad))**(11/6)*row['proj_density']**0.5*row['velocity']**(2/3))             
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = kh*(row['wall_thick']*row['wall_density'])**(2/3)*row['standoff']**(1/2)*(row['wall_yield']/70)**(1/3)/ \
            (row['proj_density']**(1/3)*row['bumper_density']**(1/9)*(row['velocity']*np.cos(anglerad))**(2/3)) + delta_dcHV
    else:  # shatter regime
        dcLV = kl*(row['wall_thick']*(row['wall_yield']/40)**0.5+0.37*tb_tot*row['bumper_density'])/ \
            ((np.cos(anglerad))**(11/6)*row['proj_density']**0.5*vLV**(2/3))  
        dcHV = kh*(row['wall_thick']*row['wall_density'])**(2/3)*row['standoff']**(1/2)*(row['wall_yield']/70)**(1/3)/ \
            (row['proj_density']**(1/3)*row['bumper_density']**(1/9)*(vHV*np.cos(anglerad))**(2/3)) + delta_dcHV
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']-vLV)

    return dc  

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

def modNNO_curve(config, velocities):
    """Return a float NumPy curve for one configuration (wall_yield in ksi)."""
    return algebraic_whipple_curve(config, velocities, modified=True, angle_rule=impact_angle_rad)


## run the code to calculate critical diameter and generate ballistic limit curve
if __name__ == "__main__":

    if __package__:
        from .results_utils import create_run_directory, write_config_csv
    else:
        from results_utils import create_run_directory, write_config_csv

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

        df_config = df_data.copy()

        ## convert units
        df_data['wall_yield'] *= 0.145038  # units = ksi        
            
        ## generate ballistic limit curves
        velocities = np.linspace(0.1,15,150)
        if len(df_data) != 1:
            raise ValueError("Expected exactly one shield configuration in the input CSV.")
        df_plot = pd.DataFrame({'velocity': velocities,
                                'dc_BLE-modNNOwhipple': modNNO_curve(df_data.iloc[0], velocities)})
        
        results_dir, now_str = create_run_directory(root_dir)
        df_results = df_plot[['velocity', 'dc_BLE-modNNOwhipple']] 
        df_results.to_csv(results_dir / f"blc_data_{now_str}.csv", index=False)

        ## save the configuration to file (for file name consistency)
        write_config_csv(df_config, results_dir / f"config_data_{now_str}.csv", input_file=filename)

        ## plot the results
        plt.figure()
        plt.plot(df_plot['velocity'],df_plot['dc_BLE-modNNOwhipple'],label='BLE-modNNOwhipple')
        plt.xlabel('Velocity (km/s)')
        plt.ylabel('Projectile diameter (cm)')

        ## If the test data flag is set, plot the test data
        if args.data:
            # Load the test data
            filename = 'database_whipple_pyBLOSSUM.csv'
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
            df_filtered_test_data.to_csv(results_dir / f"test_data_{now_str}.csv", index=False)

        plt.ylim(0.0,2.0*df_plot['dc_BLE-modNNOwhipple'][len(velocities)/2])
        plt.legend()
        # plt.show()
            
        ## Save the plot
        plt.savefig(results_dir / f'plot_{now_str}.png')

        ## Print completion statements
        print(f"Results directory: {results_dir}")
        print(f"Ballistic limit plot saved to file: plot_{now_str}.png")
        print(f"Ballistic limit curve data saved to file: blc_data_{now_str}.csv")
        print(f"Configuration data saved to file: config_data_{now_str}.csv")        

    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    finally:
        # Code to clean up resources here
        plt.close('all')
