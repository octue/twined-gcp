# This setup.py file is for development. Production dependencies are specified in each cloud function's requirements
# file.
from setuptools import setup

setup(
    name="twined-gcp",
    version="0.7.0",
    author="Marcus Lugg <marcus@octue.com>",
    install_requires=[
        "setuptools",
        "pre-commit==4.*",
        # These requirements are duplicated from the cloud functions.
        "functions-framework==3.*",
        "google-cloud-bigquery>=3.18.0,<=4",
        "kubernetes==31.*",
        "google-cloud-container==2.*",
        "google-cloud-artifact-registry==1.*",
    ],
    packages=["functions"],
)
