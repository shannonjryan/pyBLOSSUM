# pyBLOSSUM - a Python library for assessing the Ballistic Limit Of Spacecraft Structures Under Micrometeoroid and orbital debris impact

## Introduction
This library provides ballistic limit equations (BLEs) for calculating the performance of spacecraft structures under impact by micrometeoroid and orbital debris (MMOD) particles at hypervelocity.

## Getting started
To download this Git project open a terminal/command prompt and enter:
```
git clone https://github.com/shannonjryan/pyBLOSSUM.git
```
If you already have a previous version of the project you can simply update by doing:
```
git pull
```

## Setup
Requirements:
- Anaconda (https://www.anaconda.com/download)
- Python 3.8
	
The pre-requisite python packages are included in the 'environment.yml' file. To create an Anaconda environment based on the yml file browse to the directory in which you cloned this repository and enter the following command:
```
conda env create --file environment.yml
```

To activate the enviroment type:
```
conda activate pyBLOSSUM
```

## Instructions for use
This code can be used in two ways: (1) to generate ballistic limit curves for a defined Whipple shield configuration, and (2) to compare experimental data to a ballistic limit curve for a defined Whipple shield configuration.

### Generating ballistic curves
To generate performance curves run the following command from the 'code' directory:
```
python pyBLOSSUM_performance.py filename BLE1 BLE2 BLE3
```
where filename should be replaced by the name of a csv file that defines the Whipple shield configuration and BLE1, BLE2, BLE3, etc. define the ballistic limit equations that should be included in the calculation. The list of available Whipple shield BLEs include:
* NNO: the 'new non-optimum' equation from Christiansen (1993) [1]
* modNNO: the modified NNO equation from Christiansen and Kerr (2001) [2]
* reimerdes: the modified NNO equation from Reimerdes et al. (2006) [3]
* JSCwhipple: the modified NNO equation from Ryan et al. (2011) [4]
* JSCwhipple_mod: an unpublished update to the JSC Whipple BLE

An example input file, 'BLC_example.csv', is provided in the 'data' directory.

Example commands are:
```
python pyBLOSSUM_performance.py BLC_example.csv NNO
```
To perform the analysis using the NNO BLE. 

```
python pyBLOSSUM_performance.py BLC_example.csv reimerdes JSCwhipple
```
To perform the analysis using the Reimerdes and JSC Whipple BLEs. 

'all' can also be specified for the BLE input to generate ballistic limit curves from all BLEs, i.e.:
```
python pyBLOSSUM_performance.py BLC_example.csv all
```

The output is a ballistic limit plot, saved to the 'plots' directory with 'plot' appended to the input filename, e.g., 'plot-BLC_example.png' for analysis of input file 'BLC_example.csv'. Additionally, the plot data is saved to the 'results' directory with 'result' appended to the input filename, e.g., 'result-BLC_example.csv' for analysis of the input file 'BLC_example.csv'.

### Comparing experimental data and BLE predictions
Each of the BLEs can also be plotted together with experimental data provided in a csv file format (only one BLE per analysis). To perform this analysis run the following command from the 'code' directory:
```
python BLE_NNO.py filename
```
where filename is a csv input file that lists experimental data for a specific Whipple shield configuration. An example input file, 'eval_example.csv' is provided in the 'data' directory. 

The following files are output:
1. A ballistic limit plot, saved to the 'plots' directory with 'plot' and the BLE used in the assessment appended to the input filename, e.g., 'plot-NNO-eval_example.png' for analysis of input file 'eval_example.csv' with the NNO BLE.
2. The plot data is saved to the 'results' directory with 'plotdata' appended to the input filename, e.g., 'plotdata-NNO-eval_example.csv' for analysis of the input file 'eval_example.csv' with the NNO BLE.
3. The critical projectile diameter, dc, calculated for each of the experimental data points. 'dc' is appended to the input data file and saved in the results directory with 'eval' appended to the input filename, e.g., 'eval-NNO-eval_example.csv' for analysis of the input file 'eval_example.csv' with the NNO BLE.
