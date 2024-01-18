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
Modifications to the original JSC Whipple shield equation:
1- simple linear interpolation of tb/dp,crit for S/dp values between 15 - 30
2- tb/dp,crit includes projectile to bumper density ratio
3- in the hypervelocity regime F2* is calculated using a rS/D coefficient that 
uses the actual impact velocity rather than fixed v = vHV, as proposed by Squire et al.
in NASA/TM-2015-218780  

'''


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def JSCwhipple_performance_mod(row):
    '''
    Function to calculate the critical projectile diameter using the JSC Whipple shield performance BLE
    '''    

    ## define the remaining variables
    row['angle'] = 65 if row['angle'] > 65 else row['angle']
    anglerad = np.deg2rad(row['angle'])
    vn = row['velocity'] * np.cos(anglerad)     # Normalized impact velocity
    vLV = vLV_solve_piek(row['bumper_thick'],row['wall_thick'],row['proj_density'],row['wall_yield'],anglerad)
    vHV = 7

    ## calculate the ballistic limit
    if vn <= vLV:  # low velocity regime
        dc = ((row['wall_thick']*(row['wall_yield']/40)**0.5+row['bumper_thick'])/(0.6*(np.cos(anglerad))**(5/3)*row['proj_density']**0.5*row['velocity']**(2/3)))**(18/19)
    elif vn >= vHV:  # hypervelocity regime
        dc = dc_HV(row['bumper_thick'],row['wall_thick'],row['standoff'],row['wall_yield'],row['proj_density'],row['bumper_density'],anglerad,row['velocity'])
    else:  # shatter regime
        dcLV = ((row['wall_thick']*(row['wall_yield']/40)**0.5+row['bumper_thick'])/(0.6*(np.cos(anglerad))**(5/3)*row['proj_density']**0.5*(vLV/np.cos(anglerad))**(2/3)))**(18/19)
        dcHV = dc_HV(row['bumper_thick'],row['wall_thick'],row['standoff'],row['wall_yield'],row['proj_density'],row['bumper_density'],anglerad,vHV/np.cos(anglerad))
        dc = dcLV+(dcHV-dcLV)/(vHV/np.cos(anglerad)-vLV/np.cos(anglerad))*(row['velocity']-vLV/np.cos(anglerad))        

    return dc


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def vLV_solve_piek(tb,tw,rhop,sigyksi,anglerad):
    '''
    Function to calculate the low-to-shatter regime transition velocity
    '''    
      
    func = lambda x: np.sqrt(((tb/(x/1.436)**(1/3))**2-\
          (((tw*(sigyksi/40)**0.5+tb)/(0.6*(np.cos(anglerad))**(5/3)*rhop**0.5*np.abs(x)**(2/3)))**(18/19))**2)**2)
            
    vLV = fmin_slsqp(func,3.0, bounds=[(1.854,50.0)],disp=False)[0]
    dpLV = tb/(vLV/1.436)**(1/3)
    v1 = 2.60 if (tb/dpLV) >= 0.16 else 1.436*(tb/dpLV)**(-1/3)

    return v1


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def dc_HV(tb,tw,S,sigyksi,rhop,rhob,anglerad,v):
    """
    Function to calculate critical projectile diameter in the hypervelocity regime
    """
    
    func = lambda x: (x-F2star(S,x,tb,anglerad,rhop,rhob,sigyksi,v)**(-2/3)*\
              (3.918*tw**(2/3)*S**(1/3)*(sigyksi/70)**(1/3))/(rhop**(1/3)*rhob**(1/9)*(v*np.cos(anglerad))**(2/3)))**2
    dp0 = 3.918*tw**(2/3)*S**(1/3)*(sigyksi/70)**(1/3)/(rhop**(1/3)*rhob**(1/9)*(v*np.cos(anglerad))**(2/3))
    dc = fmin_slsqp(func,dp0,disp=False)[0]
       
    return dc


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
def F2star(S,dp,tb,anglerad,rhop,rhob,sigyksi,V):
    """
    Function to calculate the de-rating factor F2*
    """

    twtb0 = ((0.6*dp**(19/18)*(np.cos(anglerad))**(5/3)*rhop**0.5*V**(2/3)-0)/(sigyksi/40)**0.5)       
    twtbcrit = 0.16*dp**0.5*(rhop*rhob)**(1/6)*(np.pi*(dp/2)**3*rhop)**(1/3)*(V*np.cos(anglerad))*S**(-1/2)*(70/sigyksi)**(1/2)
    rSD = twtb0/twtbcrit

    if S/dp >= 30:
        tbondp_crit = 0.20*rhop/rhob
    elif S/dp <= 15:
        tbondp_crit = 0.25*rhop/rhob            
    else:
        tbondp_crit = (0.25-(0.25-0.20)/(30-15)*(S/dp-15))*rhop/rhob
        
    if tb/dp >= tbondp_crit:
        F2star = 1.0
    else:
        F2star = rSD-2*(tb/dp)/tbondp_crit*(rSD-1)+((tb/dp)/tbondp_crit)**2*(rSD-1)

    return F2star


# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
## run the code to calculate ballistic limit curves for a specific configuration
if __name__ == "__main__":
        
    ## import the data
    root_dir = os.path.dirname(os.getcwd())
    filename = sys.argv[1]
    df_data = pd.read_csv(os.path.join(root_dir,'data',filename))
        
    ## assess the BLE performance
    dc = np.array([])
    for index,row in df_data.iterrows():
        dc = np.append(dc,JSCwhipple_performance_mod(row))
        
    df_data.insert(loc=df_data.shape[1],column='dc_JSCwhipple-mod',value=dc)
       
    ## save the output
    df_data.to_csv(os.path.join(root_dir,'results',f'eval-JSCwhipple_mod-{filename}'),index=False)
    
    ## perforation & non-perforation results
    df_P = df_data.loc[df_data['perforated_class'] == 1]
    df_NP = df_data.loc[df_data['perforated_class'] == 0]
    
    ## generate ballistic limit curves
    V_plot = np.linspace(0.1,15,150)
    df_plot = pd.DataFrame()
    df_temp = pd.Series(df_data.iloc[0])
    for vel in V_plot:
        df_temp['velocity'] = vel
        df_temp['dc'] = JSCwhipple_performance_mod(df_temp)
        df_plot = pd.concat([df_plot,df_temp],ignore_index=True,axis=1)
    
    df_plot = df_plot.transpose()
    
    ## save the plot data to file
    df_plot.to_csv(os.path.join(root_dir,'results',f'result-JSCwhipple_mod-{filename}'),index=False)
    
    plt.figure()
    plt.plot(df_plot['velocity'],df_plot['dc'],label='JSC Whipple (mod)')
    plt.scatter(df_P['velocity'],df_P['proj_diam'],c='w',edgecolors='k',label='P')
    plt.scatter(df_NP['velocity'],df_NP['proj_diam'],c='k',edgecolors='k',label='NP')
    plt.xlabel('Velocity (km/s)')
    plt.ylabel('Projectile diameter (cm)')
    plt.ylim(0.0,2.0*df_plot['dc'][71])
    plt.legend()
        
    # plt.show()
    plt.savefig(os.path.join(root_dir,'plots',f'plot-JSCwhipple_mod-{filename.split(".")[0]}.png'))






