# Always prefer setuptools over distutils
from os import path

from setuptools import find_packages
from setuptools import setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="supertunnel",
    version="0.1rc2",
    author="Alex Rudy",
    author_email="alex.rudy@gmail.com",
    description="SuperTunnel makes for easy, long-lived SSH tunneling!",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/alexrudy/supertunnel",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Environment :: Console",
        "License :: OSI Approved :: BSD License",
        "Operating System :: Unix",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Utilities",
    ],
    keywords="utilties ssh networking",
    packages=find_packages(),
    python_requires=">=3.7, <4",
    entry_points={"console_scripts": ["st = supertunnel.command:main"]},
    install_requires=["click"],
)
