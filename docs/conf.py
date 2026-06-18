# Configuration file for the Sphinx documentation builder.
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import sys
from pathlib import Path

# Add the backend module to the path for autodoc
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

# -- Project information
project = "Meta-vis"
copyright = "2026, Anders Lind"
author = "Anders Lind"
release = "0.1.0"

# -- General configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output
html_theme = "furo"
html_static_path = ["_static"]
html_title = "Meta-vis"
html_logo = "../assets/logo.svg"
html_favicon = "../assets/logo.svg"

# Furo theme options
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#0d47a1",
        "color-brand-content": "#1976d2",
    },
    "dark_css_variables": {
        "color-brand-primary": "#90caf9",
        "color-brand-content": "#64b5f6",
    },
}

# -- Options for autodoc
autodoc_typehints = "description"
autodoc_member_order = "bysource"

# -- Options for intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "fastapi": ("https://fastapi.tiangolo.com/", None),
}
