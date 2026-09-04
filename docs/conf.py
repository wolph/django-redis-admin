"""Configuration file for the Sphinx documentation builder."""

from __future__ import annotations

import os
import sys
from datetime import date

import django

sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_redis_admin.settings')
django.setup()

from redis_admin import __about__  # noqa: E402

# -- Project information ------------------------------------------------------

project: str = 'Django Redis Admin'
author: str = __about__.__author__
copyright: str = f'{date.today().year}, {author}'  # noqa: A001

release: str = __about__.__version__
version: str = '.'.join(release.split('.')[:2])

# -- General configuration ----------------------------------------------------

extensions: list[str] = [
    'myst_parser',
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
]

napoleon_google_docstring: bool = True
napoleon_numpy_docstring: bool = False

autodoc_typehints: str = 'description'

suppress_warnings: list[str] = ['ref.python']

templates_path: list[str] = []
exclude_patterns: list[str] = [
    '_build',
    'Thumbs.db',
    '.DS_Store',
    'superpowers',
    'superpowers/**',
]

intersphinx_mapping: dict[str, tuple[str, None]] = {
    'python': ('https://docs.python.org/3', None),
}

# -- HTML output --------------------------------------------------------------

html_theme: str = 'furo'
