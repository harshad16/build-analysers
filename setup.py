#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from setuptools import setup

setup(
    name='thoth-build-analysers',
    version='0.1.0-dev',
    author='Christoph Görn',
    author_email='goern@redhat.com',
    packages=['thoth_build_analysers', ],
    license='GPLv3+',
    long_description=open('README.md').read(),
    classifiers=[
        'Development Status :: 2 - Pre - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
)
