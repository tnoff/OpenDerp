#!/usr/bin/env python
import setuptools

VERSION = '0.2'

setuptools.setup(
    author='Tyler Daniel North',
    author_email='ty_north@yahoo.com',
    description='Command Line Client For S3 Client Against OpenStack Swift',
    install_requires=[
        'python-keystoneclient >= 0.9.0',
        'boto >= 2.31.1',
    ],
    entry_points={
        'console_scripts' : [
            'boyo = boyo.command_line:main',
        ]
    },
    packages=setuptools.find_packages(),
    name='boyo',
    version=VERSION,
)
