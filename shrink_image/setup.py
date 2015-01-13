#!/usr/bin/env python
import setuptools

VERSION = '0.4'

setuptools.setup(
    author='Tyler Daniel North',
    author_email='tylernorth18@gmail.com',
    description='OpenStack Shrink Images',
    install_requires=[
        'python-cinderclient >= 1.0.9',
        'python-glanceclient >= 0.13.1',
        'python-keystoneclient >= 0.10.1',
    ],
    entry_points={
        'console_scripts' : [
            'shrink-image = shrink_image.cli:main',
        ]
    },
    packages=[
        'shrink_image'
    ],
    name='shrink_image',
    version=VERSION,
)
