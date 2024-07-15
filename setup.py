from setuptools import setup


setup(
    name="twined-gcp",
    version="0.6.1",
    author="Marcus Lugg <marcus@octue.com>",
    install_requires=[
        "setuptools",
        # Requirements duplicated from cloud functions.
        "functions-framework==3.*",
        "google-cloud-bigquery>=3.18.0,<=4",
    ],
    packages=["functions"],
)
