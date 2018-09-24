# foamMon
![](https://badge.fury.io/py/foamMon.svg)
![](https://travis-ci.org/greole/foamMon.svg?branch=master)


A simple tool for monitoring the progress of OpenFOAM simulations

![screenshot](https://github.com/greole/foamMon/blob/master/.assets/screen.png)

# Installation

foamMon can be installed from the Pypi repositories

    pip3 install foamMon

or directly from this repo

    python3 setup.py install --user

or

    pip install foamMon

## Ubuntu

If installing under ubuntu with user privileges make sure that
'$HOME/.local/bin' is added to your '$PATH'. If necessary
add

    export PATH=$PATH:$HOME/.local/bin

to your ~/.bashrc file

# Usage

To monitor the progress of simulations simply run 'foamMon' in a parent directory. Check
'foamMon --help' for further options.

## Customisation

Fields displayed by default can be hidden by setting the corresponding flag to "False"

        --progressbar (True|False) Display the progressbar [default: True]
        --folder (True|False)      Display the foldername  [default: True]
        --logfile (True|False)     Display the filename of the logfile [default: True]
        --time (True|False)        Display the the current simulation time [default: True]
        --writeout (True|False)    Display expected writeout [default: True]
        --remaining (True|False)   Display expected remaining simulation time [default: True]

Custom fields can be added by setting the '--custom_filter' argument.

    --custom_filter '{"Temperature": "T gas min/max  = ([0-9,. ]*)", "deltaT": "deltaT = ([0-9.e-]*)"}'



# Logfiles

The log files need to have *log* in the filename.

