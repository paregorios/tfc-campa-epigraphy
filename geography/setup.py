import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="campa.geographer",
    version="0.0.1",
    author="Tom Elliott",
    author_email="tom.elliott@nyu.edu",
    description="Convert Campā Inscriptions metadata for geospatial use.",
    license='MIT',
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.9.1",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=['airtight'],
    python_requires='>=3.9.1'
)
