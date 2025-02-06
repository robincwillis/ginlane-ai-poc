from setuptools import setup, find_packages

setup(
    name="gin-lane-ai-poc",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
)
