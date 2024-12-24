from setuptools import setup, find_packages

setup(
    name="raptor",
    version="0.1",
    packages=find_packages(where="src") + ['data'],
    package_dir={"": "src", "data": "data"},
    package_data={
        "data": ["canbus/*.eds"]
    }
)
