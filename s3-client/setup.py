#!/usr/bin/env python
import setuptools

VERSION = '1.1'

setuptools.setup(
    author='Tyler Daniel North',
    author_email='tylernorth18@gmail.com',
    description='Command Line Client For S3 Client Against OpenStack Swift',
    install_requires=[
        'python-keystoneclient >= 0.9.0',
        'boto >= 2.31.1',
    ],
    entry_points={
        'console_scripts' : [
            's3-client = s3.client:main',
        ]
    },
    packages=setuptools.find_packages(),
    name='s3',
    version=VERSION,
)
