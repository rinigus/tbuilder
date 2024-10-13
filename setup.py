#!/usr/bin/env python3

from setuptools import setup

setup(
    name="tbuilder",
    description="TBuilder: builder for Sailfish OS projects",
    author="rinigus",
    license="GPLv3",
    version="1.0",
    url="https://github.com/rinigus/tbuilder",
    packages=[
        "tbuilder",
    ],
    entry_points={
        "console_scripts": [
            "tbuilder = tbuilder.app:main",
        ],
    },
    package_data={
        'tbuilder': ['scripts/*.sh'],
    },
    install_requires=[
        "pyyaml",
        "GitPython"
    ],
    language_level="3",
)
