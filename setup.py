#!/usr/bin/env python3
"""
Setup script for USIF package
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
if readme_file.exists():
    try:
        with open(readme_file, "r", encoding="utf-8") as f:
            long_description = f.read()
    except UnicodeDecodeError:
        # Fallback if encoding issues
        long_description = "USIF (Universal Structure Interchange Format) - Unified format for crystals and molecules with intelligent compression"
else:
    long_description = "USIF (Universal Structure Interchange Format) - Unified format for crystals and molecules with intelligent compression"

# Read version from package
version = "4.0"

setup(
    name="usif",
    version=version,
    author="haidi@hfut.edu.cn",
    author_email="haidi@hfut.edu.cn",
    description="Universal Structure Interchange Format for crystals and molecules",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/usif",
    packages=find_packages(exclude=["tests", "tests.*", "__pycache__"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Chemistry",
        "Topic :: Scientific/Engineering :: Physics",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.19.0",
        "pymatgen>=2022.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
        ],
        "all": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
        ],
    },
    entry_points={
        "console_scripts": [
            # Add console scripts here if needed
        ],
    },
    include_package_data=True,
    zip_safe=False,
)

