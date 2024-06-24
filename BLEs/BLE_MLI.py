import numpy as np
import pandas as pd
import os
import sys
from matplotlib import pyplot as plt
import seaborn as sns
import warnings
from scipy import optimize

plt.close('all')
sns.set_theme()
warnings.filterwarnings("ignore", category=RuntimeWarning)  ## supress runtime warnings

'''
References:
[1] EL Christiansen et al. 2009. Handbook for designing MMOD protection,
NASA Johnson Space Center, Houston, NASA/TM-2009-214785
[2] EL Christiansen, DM Lear. 2015. Toughened thermal blanket for micrometeoroid 
and orbital debris protection. Proceedings of the 13th Hypervelocity Impact
Symposium, Boulder.
'''


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def f(x,row,vel,anglerad,msheff):   
    '''
    Calculates Eq. (8) from [2], the function value for a projectile diameter of 'x'
    '''
    return (29*np.pi/6*x**3*row['proj_density']*vel*np.cos(anglerad)*row['thickness']**-2+0.185*x*row['proj_density']-msheff)
    
# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def fprime(x,row,vel,anglerad,msheff):
    '''
    Calculates Eq. (9) from [2], the derivative of the projectile diameter function with respect to the projectile diameter
    '''
    return (29*np.pi/6*3*x**2*row['proj_density']*vel*np.cos(anglerad)*row['thickness']**-2+0.185)  

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def mli_performance(row):
    '''
    Baseline: 0.188 g/cm2 MLI blanket consisting of multiple aluminised Mylar or
      Kapton layers at 1.5 cm standoff to aluminium rear wall (see page 99 from [1])
    Toughened: 0.307 g/cm2 MLI blanket, consisting of the 'baseline' configuration
      with two layers of Nextel AF10 added under the outer cover and three layers
      of Kevlar KM2 CS-705 added to the back. 1.5 cm standoff to aluminium rear 
      wall (see page 100 from [1])
    Enhanced: consists of disrupter layers of beta cloth, standard MLI, open cell
      polymide foam, UHMWPE (Spectra) absorber layers, and a thickened Mylar rear
      cover (see [2] for details)
    '''

    ## convert the angle to radians
    anglerad = np.deg2rad(row['angle'])
    
    ## calculate the configuration-specific constants
    if row['type'] == 'Baseline':
        KL = 1.7
        QL = row['wall_thick']
        KH = 2.9
        vLV = 2.5/np.cos(anglerad)
        vHV = 6/(np.cos(anglerad))**0.5

    elif row['type'] == 'Toughened':
        KL = 1.7
        QL = row['wall_thick']
        KH = 1.34
        vLV = 2.5/np.cos(anglerad)
        vHV = 6.2/(np.cos(anglerad))**0.25
        
    elif row['type'] == 'Enhanced':
        KL = 2.7
        QL = 0.5*row['wall_AD']
        KH = 0
        vLV = 2.4/np.cos(anglerad)**0.5
        vHV = 6.4/(np.cos(anglerad))**0.25    

    ## Ballistic limit calculation
    if row['velocity'] <= vLV:  # low velocity regime
        dc = KL*(QL+0.37*row['bumper_AD'])/((np.cos(anglerad))**(4/3)*row['proj_density']**0.5*row['velocity']**(2/3))
    elif row['velocity'] >= vHV:  # hypervelocity regime
        if row['type'] == 'Enhanced':
            msheff = row['bumper_AD']+row['wall_AD']+0.25*row['MLI_AD']
            dc = optimize.newton(f,x0=0.5,fprime=fprime,args=(row,row['velocity'],anglerad,msheff),maxiter=1000)
        else:
            dc = KH*row['wall_thick']**(2/3)/(row['proj_density']**(1/3)*row['velocity']**(2/3)*(np.cos(anglerad))**(2/3))
    else:  # shatter regime
        dcLV = KL*(QL+0.37*row['bumper_AD'])/((np.cos(anglerad))**(4/3)*row['proj_density']**0.5*vLV**(2/3))
        if row['type'] == 'Enhanced':
            msheff = row['bumper_AD']+row['wall_AD']+0.25*row['MLI_AD']
            dcHV = optimize.newton(f,x0=0.5,fprime=fprime,args=(row,vHV,anglerad,msheff),maxiter=1000)  # Newton-Raphson numerical solver
        else:
            dcHV = KH*row['wall_thick']**(2/3)/(row['proj_density']**(1/3)*vHV**(2/3)*(np.cos(anglerad))**(2/3))
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
        df_plot['dc_BLE'] = df_plot.apply(mli_performance,axis=1)
        
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