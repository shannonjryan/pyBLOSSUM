import numpy as np
if __package__:
    from .solver_utils import checked_slsqp, positive_scalar, solve_hypervelocity_diameter, solve_once
    from .curve_utils import solver_whipple_curve
else:  # Direct CLI execution and GUI imports from the BLEs directory
    from solver_utils import checked_slsqp, positive_scalar, solve_hypervelocity_diameter, solve_once
    from curve_utils import solver_whipple_curve
import pandas as pd
import os
import seaborn as sns
from matplotlib import pyplot as plt
import argparse
import sys

plt.close('all')
sns.set_theme()


'''
Reference: S Ryan, EL Christiansen. 2011. "A ballistic limit analysis programme
for shielding against micrometeoroids and orbital debris", Acta Astronautica; 69: 245-257

Note: The code used in NASA/TM-2009-214789 calculates the S/dp,crit ratio in an 
initial step, from which the F2star calculation is influenced throughout the calculation. 
More correctly this should not be pre-defined but rather should be included in the
optimisation, as is done here. As a result, the ballistic limits calculated with this
code may vary slightly from those calculated using the Ballistic Limit Analysis Program
described in NASA/TM-2009-214789.
'''

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def impact_angle_rad(angle_deg):
    return np.deg2rad(min(angle_deg, 65))


def JSCwhipple_performance(row, *, solver_cache=None):
    '''
    Function to calculate the critical projectile diameter using the JSC Whipple shield performance BLE.
    Pass a fresh solver_cache dictionary when evaluating a velocity curve.
    '''

    ## define the obliquity limit and convert to radians
    anglerad = impact_angle_rad(row['angle'])

    ## account for the presence of MLI
    if row['S_MLI'] > 0:  # internal MLI
        K_MLI = 1.4
        vLV = 2.0/np.cos(anglerad)
        delta_dcHV = K_MLI*row['AD_MLI']*(row['S_MLI']/row['standoff'])**(1/2)
        tb_tot = row['bumper_thick']
    else:  # external MLI
        K_MLI = 3
        if row['AD_MLI'] > 0:
            rho_ref = 2.78
            tb_tot = row['bumper_thick']+K_MLI*row['AD_MLI']/rho_ref
        else:
            tb_tot = row['bumper_thick']
        vLV = solve_once(solver_cache,vLV_solve_piek,tb_tot,row['wall_thick'],row['proj_density'],row['wall_yield'],anglerad)/np.cos(anglerad)
        delta_dcHV = 0

    # define the velocity regime transitions
    vHV = 7.0/np.cos(anglerad)

    ## Ballistic limit calculation               
    if row['velocity'] <= vLV:  # low velocity regime
        dc = ((row['wall_thick']*(row['wall_yield']/40)**0.5+tb_tot)/(0.6*(np.cos(anglerad))**(5/3)*row['proj_density']**0.5*row['velocity']**(2/3)))**(18/19)
    elif row['velocity'] >= vHV:  # hypervelocity regime
        dc = dc_HV(tb_tot,row['wall_thick'],row['standoff'],row['wall_yield'],row['proj_density'],row['bumper_density'],anglerad,row['velocity'],vHV) + delta_dcHV
    else:  # shatter regime
        dcLV = ((row['wall_thick']*(row['wall_yield']/40)**0.5+tb_tot)/(0.6*(np.cos(anglerad))**(5/3)*row['proj_density']**0.5*vLV**(2/3)))**(18/19)
        dcHV = solve_once(solver_cache,dc_HV,tb_tot,row['wall_thick'],row['standoff'],row['wall_yield'],row['proj_density'],row['bumper_density'],anglerad,vHV,vHV) + delta_dcHV
        dc = dcLV+(dcHV-dcLV)/(vHV-vLV)*(row['velocity']-vLV)    

    return dc


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def JSCwhipple_curve(config, velocities):
    """Return a float NumPy curve for one configuration (wall_yield in ksi)."""
    return solver_whipple_curve(config, velocities, vLV_solve_piek, dc_HV, angle_rule=impact_angle_rad)


def vLV_solve_piek(tb,tw,rhop,sigyksi,anglerad):
    '''
    Function to calculate the low-to-shatter regime transition velocity
    '''    
      
    def diameters(x):
        left = tb/(x/1.436)**(1/3)
        right = ((tw*(sigyksi/40)**0.5+tb)/(0.6*np.cos(anglerad)**(5/3)*rhop**0.5*np.abs(x)**(2/3)))**(18/19)
        return left, right

    def func(x):
        left, right = diameters(x)
        return np.abs(left**2-right**2)

    # The original piecewise rule returns 2.60 for the capped branch; its
    # intermediate minimizer need not be a root of the uncapped equation.
    def residual_required(x):
        dp = diameters(x)[0]
        return tb/dp < 0.16

    vLV = checked_slsqp(func, 3.0, diameters, bounds=[(1.854, 50.0)],
                       context="JSC Whipple transition velocity",
                       residual_required=residual_required)
    dpLV = tb/(vLV/1.436)**(1/3)
    v1 = 2.60 if (tb/dpLV) >= 0.16 else 1.436*(tb/dpLV)**(-1/3)

    return positive_scalar(v1, context="JSC Whipple derived transition velocity")


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def dc_HV(tb,tw,S,sigyksi,rhop,rhob,anglerad,v,vHV):
    """
    Function to calculate critical projectile diameter in the hypervelocity regime
    """
    
    def derating(diameter):
        return F2star(S, diameter, tb, anglerad, rhop, rhob, sigyksi, vHV)

    dp0 = 3.918*tw**(2/3)*S**(1/3)*(sigyksi/70)**(1/3)/(rhop**(1/3)*rhob**(1/9)*(v*np.cos(anglerad))**(2/3))
    return solve_hypervelocity_diameter(
        dp0, S, derating, context=f"JSC Whipple hypervelocity diameter at {v:g} km/s",
    )


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def F2star(S,dp,tb,anglerad,rhop,rhob,sigyksi,vHV):
    """
    Function to calculate the de-rating factor F2*
    """

    twtb0 = ((0.6*dp**(19/18)*(np.cos(anglerad))**(5/3)*rhop**0.5*vHV**(2/3)-0)/(sigyksi/40)**0.5)       
    twtbcrit = 0.16*dp**0.5*(rhop*rhob)**(1/6)*(np.pi*(dp/2)**3*rhop)**(1/3)*(vHV*np.cos(anglerad))*S**(-1/2)*(70/sigyksi)**(1/2)
    rSD = twtb0/twtbcrit

    if dp <= S/30:
        tbondp_crit = 0.20
    else:
        tbondp_crit = 0.25            
        
    if tb/dp >= tbondp_crit:
        F2star = 1.0
    else:
        F2star = rSD-2*(tb/dp)/tbondp_crit*(rSD-1)+((tb/dp)/tbondp_crit)**2*(rSD-1)

    return F2star


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
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
                                'dc_BLE-JSCwhipple': JSCwhipple_curve(df_data.iloc[0], velocities)})
        
        results_dir, now_str = create_run_directory(root_dir)
        df_results = df_plot[['velocity', 'dc_BLE-JSCwhipple']] 
        df_results.to_csv(results_dir / f"blc_data_{now_str}.csv", index=False)

        ## save the configuration to file (for file name consistency)
        write_config_csv(df_config, results_dir / f"config_data_{now_str}.csv", input_file=filename)

        ## plot the results
        plt.figure()
        plt.plot(df_plot['velocity'],df_plot['dc_BLE-JSCwhipple'],label='BLE-JSCwhipple')
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

        plt.ylim(0.0,2.0*df_plot['dc_BLE-JSCwhipple'][len(velocities)/2])
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
