from distutils.core import setup

setup(
	name='scanning_control',
	version='0.1',
	packages=['scanning', 'scanning.procedures',],
	description='stepper control and measurement package.',
	long_description=open('README.rst').read(),
	install_requires = ["pymeasure > =0.5.1"
	]
)