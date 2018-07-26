import sys

from setuptools import setup

package_name = 'FoamMon'
config = {
    'author'                 : 'Gregor Olenik',
    'author_email'           : 'go@hpsim.de',
    'description'            : '',
    'license'                : 'MIT',
    'version'                : "0.1",
    'packages'               : ["FoamMon"],
    'install_requires'       : [
         'docopt',
         'colorama',
    ],
   'name'                    : 'foamMon',
   'scripts': ["bin/foamMon"]}


setup(**config)
