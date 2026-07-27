"""
Legacy setup.py shim — all configuration lives in pyproject.toml.

This file exists only for compatibility with older pip versions (<21.3)
and tools that require a setup.py to be present.
"""

from setuptools import setup

if __name__ == "__main__":
    setup()
