#!/usr/bin/env python
import setuptools

VERSION = 0.4

setuptools.setup(
    author='Tyler Daniel North',
    author_email='tylernorth18@gmail.com',
    description='OpenStack Bootable Volume',
    install_requires=[
        'python-cinderclient >= 1.0.9',
        'python-glanceclient >= 0.13.1',
        'python-keystoneclient >= 0.10.1',
        'python-novaclient >= 2.18.1',
    ],
    entry_points={
        'console_scripts' : [
            'volume-boot = volume_boot.cli:main',
        ]
    },
    packages=[
        'volume_boot'
    ],
    name='volume_boot',
    version=VERSION,
)
