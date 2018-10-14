#!/usr/bin/env python

from distutils.core import setup

setup(name='hs-maintainer-tools',
      version='1.0',
      description='Haskell maintainer utilities',
      author='Ben Gamari',
      author_email='ben@smart-cactus.org',
      py_modules=['cabal_bump'],
      install_requires = [ 'termcolor' ],
      entry_points={
          'console_scripts': [
              'cabal-bump=cabal_bump:main'
          ]
      }
)

