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
    install_requires=[
        "pyyaml"
    ],
    language_level="3",
)
