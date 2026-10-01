"""Setup script for VeriAgent."""
from setuptools import setup, find_packages

setup(
    name="veriagent",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "scikit-learn>=1.4.0",
        "numpy>=1.26.0",
    ],
)
