from setuptools import setup


setup(
    name="twined-gcp",
    version="0.2.0",
    author="cortadocodes <cortado.codes@protonmail.com>",
    install_requires=[
        "setuptools",
        # Requirements duplicated from cloud functions.
        "functions-framework==3.*",
        "google-cloud-bigquery>=3.18.0,<=4",
    ],
)
