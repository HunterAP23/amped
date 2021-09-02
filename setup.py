# Copyright (C) 2020-2028 HunterAP23.

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="AMPED",
    version="0.0.1",
    author="HunterAP",
    author_email="hunterap23@gmail.com",
    description="Python library for easy creation and management of asynchronous thread and process pools.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HunterAP23/AsyncMultiProcThread",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
)
