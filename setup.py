"""Setup file for creating the RsInstrument package."""

import pathlib
from setuptools import setup, find_packages

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
	name="RsInstrument",
	version="1.19.0.75",
	description="VISA or Socket Communication Module for Rohde & Schwarz Instruments",
	long_description=README,
	long_description_content_type="text/markdown",
	author="Rohde & Schwarz GmbH & Co. KG",
	copyright="Copyright © Rohde & Schwarz GmbH & Co. KG 2020",
	url="https://github.com/Rohde-Schwarz/RsInstrument",
	license="MIT",
	classifiers=[
		"License :: OSI Approved :: MIT License",
		"Programming Language :: Python :: 3.6",
	],
	packages=(find_packages(include=['RsInstrument', 'RsInstrument.*'])),
	install_requires=["PyVisa"]
)
