"""Configuration file for the Sphinx documentation builder.

This file only contains a selection of the most common options. For a full
list see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html

-- Path setup --------------------------------------------------------------

If extensions (or modules to document with autodoc) are in another directory,
add these directories to sys.path here. If the directory is relative to the
documentation root, use os.path.abspath to make it absolute, like shown here.
"""

import os
import sys

from docutils import nodes
from sphinx.addnodes import desc_parameter, desc_returns
from sphinx.writers.html5 import HTML5Translator

sys.path.insert(0, os.path.abspath('../..'))

# -- Project information -----------------------------------------------------

project = 'RsInstrument Python'
# noinspection PyShadowingBuiltins
copyright = '© Rohde & Schwarz 2026'
author = 'Rohde & Schwarz'
master_doc = 'index'

# The full version, including alpha/beta/rc tags
release = '1.131.0'

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx_copybutton',
    'recommonmark'
]

# Optional extras (mcp / otel) pull in third-party packages that are not part of the
# docs build environment (see docs/requirements.txt and the [mcp]/[otel] extras).
# Mock them so autodoc can import RsInstrument.mcp / RsInstrument.otel without failing.
autodoc_mock_imports = [
    'pydantic',
    'fastmcp',
    'zeroconf',
    'starlette',
    'opentelemetry',
]

add_module_names = False

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['Chapter_*.rst']
autoclass_content = 'both'
pygments_style = 'zenburn'

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
html_css_files = [
    'custom.css',
]


def _has_parameters(node):
    for child in node.children:
        if isinstance(child, nodes.Text):
            if child.astext().strip():
                return True
        elif child.astext().strip():
            return True
    return False


def _next_starts_with_space(node):
    """The return annotation keeps the space after ')' inside its own tag."""
    parent = node.parent
    if parent is None:
        return False
    index = parent.children.index(node)
    if index + 1 >= len(parent.children):
        return False
    following = parent.children[index + 1]
    if isinstance(following, desc_returns):
        return True
    text = following.astext()
    return bool(text) and text[0].isspace()


def _install_paren_spacing():
    """Space method parentheses: ``name ( ) → bool`` and ``name ( arg )``.

    An empty pair keeps one space between the brackets. The space after ')'
    is written inside the following element. A space between the ')' tag and
    the return tag is dropped, because the member bar is a table.
    """
    if getattr(HTML5Translator, '_paren_spacing_installed', False):
        return

    def visit_desc_parameterlist(self, node):
        if node.parent is None or node.parent.parent is None or node.parent.parent.get('domain') != 'py':
            self._visit_sig_parameter_list(node, desc_parameter, '(', ')')
            return
        opening = ' ( ' if _has_parameters(node) else ' ('
        closing = ' )' if _next_starts_with_space(node) else ' ) '
        self._visit_sig_parameter_list(node, desc_parameter, opening, closing)

    def visit_desc_returns(self, node):
        self.body.append('<span class="sig-return"> ')
        self.body.append('<span class="sig-return-icon">&#x2192;</span>')
        self.body.append(' <span class="sig-return-typehint">')

    HTML5Translator.visit_desc_parameterlist = visit_desc_parameterlist
    HTML5Translator.visit_desc_returns = visit_desc_returns
    HTML5Translator._paren_spacing_installed = True


def setup(app):
    _install_paren_spacing()
