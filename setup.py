import io
import re
from setuptools import setup

with io.open("README.rst", "rt", encoding="utf8") as f:
    readme = f.read()

setup(
    name="serial_uploader",
    version="0.1",
    author="David Caro",
    author_email="david@dcaro.es",
    maintainer="David Caro",
    maintainer_email="david@dcaro.es",
    description="Simple serial console switch configuration uploader.",
    long_description=readme,
    packages=["serial_uploader"],
    entry_points={
        "console_scripts": [
            "serial-uploader = serial_uploader:upload_config",
        ]
    },
    install_requires=["pyserial", "click"],
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
    ],
)
