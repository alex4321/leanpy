from pathlib import Path

from setuptools import find_packages, setup

ROOT = Path(__file__).resolve().parent

README = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").exists() else ""

setup(
    name="leanpy",
    version="0.1.0",
    description="Simple Lean/Lake project helper.",
    long_description=README,
    long_description_content_type="text/markdown",
    author="leanpy maintainers",
    url="https://github.com/",
    packages=find_packages(exclude=("tests", "tests.*")),
    python_requires=">=3.11",
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)

