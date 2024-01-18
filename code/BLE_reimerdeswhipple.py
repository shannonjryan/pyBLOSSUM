import numpy as np
from scipy.optimize import fmin_slsqp
import pandas as pd
import os
import sys
import seaborn as sns
from matplotlib import pyplot as plt
import warnings

plt.close('all')
sns.set()
warnings.filterwarnings("ignore", category=RuntimeWarning)  ## supress runtime warnings

'''
Reference: H.G. Reimerdes, D. Noelke, F.K. Schaefer, 
“Modified Cour-Palais/Christiansen Damage Equations for Double-Wall Structures”, 
International Journal of Impact Engineering; 33: 645-654, 2006.

Note: The code used in NASA/TM-2009-214789 calculates the S/dp,crit ratio in an 
initial step, from which the F2star calculation is influenced throughout the calculation. 
More correctly this should not be pre-defined but rather should be included in the
optimisation, as is done here. As a result, the ballistic limits calculated with this
code may vary slightly from those calculated using the Ballistic Limit Analysis Program
described in NASA/TM-2009-214789.
'''

## define global constants
K = 1.8
Kinf = 0.42

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def reimerdes_performance(row):
    '''
    Function to calculate the critical projectile diameter using the Reimerdes performance BLE
    '''

    row['angle'] = 65 if row['angle'] > 65 else row['angle']
    anglerad = np.deg2rad(row['angle'])
    vn = row['velocity'] * np.cos(anglerad)     # Normalized impact velocity
    vLV = vLV_solve_reim(row['bumper_thick'],row['wall_thick'],row['proj_density'],anglerad)
    vHV = 7
    
    ## Ballistic limit calculation        
    if vn <= vLV:  # low velocity regime
        dc = ((row['wall_thick']/K+row['bumper_thick'])/(0.796*Kinf*row['proj_density']**0.518*vn**(2/3)))**(18/19)
    elif vn >= vHV:  # hypervelocity regime
        dc = dc_HV(row['bumper_thick'],row['wall_thick'],row['standoff'],row['wall_yield'],row['proj_density'],row['bumper_density'],anglerad,row['velocity'],vHV)
    else:  # shatter regime
        dcLV = ((row['wall_thick']/K+row['bumper_thick'])/(0.796*Kinf*row['proj_density']**0.518*vLV**(2/3)))**(18/19)
        dcHV = dc_HV(row['bumper_thick'],row['wall_thick'],row['standoff'],row['wall_yield'],row['proj_density'],row['bumper_density'],anglerad,vHV/np.cos(anglerad),vHV)
        dc = dcLV+(dcHV-dcLV)/(vHV/np.cos(anglerad)-vLV/np.cos(anglerad))*(row['velocity']-vLV/np.cos(anglerad))        

    return dc


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def vLV_solve_reim(tb,tw,rhop,anglerad):
    '''
    Function to calculate the low-to-shatter regime transition velocity
    '''

    ## define the minimisation function, here x: vLV
    func = lambda x: np.sqrt(((tb/((x-1.853)/0.397)**(-1/0.565))**2-\
        (((tw/K+tb)/(0.796*Kinf*rhop**0.518*(x*np.cos(anglerad))**(2/3)))**(18/19))**2)**2)
            
    vLV = fmin_slsqp(func,3.0,bounds=[(1.854,50.0)],disp=False)[0]

    return vLV

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def dc_HV(tb,tw,S,sigyksi,rhop,rhob,anglerad,v,vHV):
    """
    Function to calculate critical projectile diameter in the hypervelocity regime
    """
    
    ## define the minimisation function, here x: dc
    func = lambda x: (x-3.918*F2star(tb,S,rhob,sigyksi,rhop,x,anglerad,vHV)**(-2/3)*\
        tw**(2/3)*S**(1/3)*(sigyksi/70)**(1/3)/(rhop**(1/3)*rhob**(1/9)*(v*np.cos(anglerad))**(2/3)))**2
    dp0 = 3.918*tw**(2/3)*S**(1/3)*(sigyksi/70)**(1/3)/(rhop**(1/3)*rhob**(1/9)*(v*np.cos(anglerad))**(2/3))
    dc = fmin_slsqp(func,dp0,disp=False)[0]
    
    return dc

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def F2star(tb,S,rhob,sigyksi,rhop,dp,anglerad,vHV):
    '''
    Function to calculate the de-rating factor F2*
    '''
    
    twtb0 = K*(Kinf*(np.pi*(dp/2)**3*rhop)**0.352*rhop**(1/6)*(vHV*np.cos(anglerad))**(2/3)-0)
    twtbcrit = 0.178*1*(np.pi*(dp/2)**3*rhop)**(1/2)*rhob**(1/6)*(vHV*np.cos(anglerad))*(70/sigyksi)**(1/2)*S**(-1/2)
    rSD = twtb0/twtbcrit  
    
    if S/dp >= 30:
        tbondp_crit = 0.20
    else:
        tbondp_crit = 0.25    
        
    if tb/dp >= tbondp_crit:
        F2star = 1
    else:
        F2star = rSD-2*(tb/dp)/tbondp_crit*(rSD-1)+((tb/dp)/tbondp_crit)**2*(rSD-1)

    return F2star


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
## run the code to calculate critical diameter and generate ballistic limit curve
if __name__ == "__main__":
        
    ## import the data
    root_dir = os.path.dirname(os.getcwd())
    filename = sys.argv[1]
    df_data = pd.read_csv(os.path.join(root_dir,'data',filename))
        
    ## assess the BLE performance
    dc = np.array([])
    for index,row in df_data.iterrows():
        dc = np.append(dc,reimerdes_performance(row))
        
    df_data.insert(loc=df_data.shape[1],column='dc_reimerdes',value=dc)
       
    ## save the output
    df_data.to_csv(os.path.join(root_dir,'results',f'eval-reimerdes-{filename}'),index=False)
    
    ## perforation & non-perforation results
    df_P = df_data.loc[df_data['perforated_class'] == 1]
    df_NP = df_data.loc[df_data['perforated_class'] == 0]
    
    ## generate ballistic limit curves
    V_plot = np.linspace(0.1,15,150)
    df_plot = pd.DataFrame()
    df_temp = pd.Series(df_data.iloc[0])
    for vel in V_plot:
        df_temp['velocity'] = vel
        df_temp['dc'] = reimerdes_performance(df_temp)
        df_plot = pd.concat([df_plot,df_temp],ignore_index=True,axis=1)
    
    df_plot = df_plot.transpose()
    
    ## save the plot data to file
    df_plot.to_csv(os.path.join(root_dir,'results',f'plotdata-reimerdes-{filename}'),index=False)
    
    plt.figure()
    plt.plot(df_plot['velocity'],df_plot['dc'],label='Reimerdes')
    plt.scatter(df_P['velocity'],df_P['proj_diam'],c='w',edgecolors='k',label='P')
    plt.scatter(df_NP['velocity'],df_NP['proj_diam'],c='k',edgecolors='k',label='NP')
    plt.xlabel('Velocity (km/s)')
    plt.ylabel('Projectile diameter (cm)')
    plt.ylim(0.0,2.0*df_plot['dc'][71])
    plt.legend()
        
    # plt.show()
    plt.savefig(os.path.join(root_dir,'plots',f'plot-reimerdes-{filename.split(".")[0]}.png'))

