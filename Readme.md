# foamMon

A simple tool for monitoring the progress of OpenFOAM simulations

![screenshot](https://github.com/greole/foamMon/blob/master/.assets/screen.png)

# Installation

foamMon can be installed from the Pypi repositories

    pip3 install foamMon

or direcetly from this repo

    python3 setup.py install --user


# Usage


To monitor the progress of multiple simulations simply run

    foamMon -m

in the parent directory. Furthermore to monitor a single case run

    foamMon

in the case directory. Filter the output of the current log by a given keyword.

    foamMon --filter="Time"

# Logfiles

The log files need to have *log* in the filename.

