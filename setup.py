from setuptools import find_packages, setup

setup(
    name="supertunnel",
    version="1.0",
    author="Alex Rudy",
    author_email="alex.rudy@gmail.com",
    description="SuperTunnel makes for easy, long-lived SSH tunneling!",
    packages=find_packages(),
    entry_points={"console_scripts": ["st = supertunnel.command:main"]},
    install_requires=["click"],
)
