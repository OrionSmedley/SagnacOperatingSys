from distutils.core import setup

setup(
    name='sagnac_control',
    version='0.1',
    packages=['sagnac','sagnac.procedures','sagnac.custom_instruments'],
    description='sagnac measurement package.',
    long_description=open('README.rst').read(),
    install_requires = [
        "pymeasure >= 0.5.1"
    ]
)