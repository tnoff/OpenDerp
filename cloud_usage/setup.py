#!/usr/bin/env python
import setuptools

VERSION = '0.4'

setuptools.setup(
    author='Tyler Daniel North',
    author_email='tylernorth18@gmail.com',
    description='OpenStack Cloud Usage Script',
    install_requires=[
        'python-cinderclient >= 1.0.9',
        'python-glanceclient >= 0.13.1',
        'python-keystoneclient >= 0.10.1',
        'python-novaclient >= 2.18.1',
        'python-swiftclient >= 2.2.0',
    ],
    entry_points={
        'console_scripts' : [
            'cloud-usage = cloud_usage.cli:main',
        ]
    },
    packages=[
        'cloud_usage'
    ],
    name='cloud_usage',
    version=VERSION,
)
