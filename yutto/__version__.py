import os
import toml

_here = os.path.abspath(os.path.dirname(__file__))
pyproject_filepath = os.path.join(os.path.dirname(_here), "pyproject.toml")

VERSION = toml.load(pyproject_filepath)["tool"]["poetry"]["version"].strip()
