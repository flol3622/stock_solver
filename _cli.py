"""
Entry point for uvx / pipx invocation.
Installed as the `stock-solver` console script by pyproject.toml.
"""
import pathlib
import subprocess
import sys


def run() -> None:
    app = pathlib.Path(__file__).with_name("app.py")
    sys.exit(subprocess.call(["streamlit", "run", str(app), *sys.argv[1:]]))
