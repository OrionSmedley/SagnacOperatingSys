from distutils.core import setup

setup(
    name='daedalus_control',
    version='0.1',
    packages=['daedalus','daedalus.procedures','daedalus.custom_instruments'],
    description='daedalus measurement package.',
    long_description=open('README.rst').read(),
)
