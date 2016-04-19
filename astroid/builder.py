# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of astroid.
#
# astroid is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation, either version 2.1 of the License, or (at your
# option) any later version.
#
# astroid is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License
# for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with astroid. If not, see <http://www.gnu.org/licenses/>.
"""The AstroidBuilder makes astroid from living object and / or from _ast

The builder is not thread safe and can't be used to parse different sources
at the same time.
"""

import ast
import os
import textwrap

from astroid import exceptions
from astroid.tree import rebuilder
from astroid.tree import zipper
from astroid import util


def _parse(string):
    return compile(string, "<string>", 'exec', ast.PyCF_ONLY_AST)


def _data_build(data, modname, path):
    """Build tree node from data and add some informations"""
    try:
        node = _parse(data + '\n')
    except (TypeError, ValueError, SyntaxError) as exc:
        util.reraise(exceptions.AstroidSyntaxError(
            'Parsing Python code failed:\n{error}',
            source=data, modname=modname, path=path, error=exc))
    if path is not None:
        node_file = os.path.abspath(path)
    else:
        node_file = '<?>'
    if modname.endswith('.__init__'):
        modname = modname[:-9]
        package = True
    else:
        package = path and path.find('__init__.py') > -1 or False
    builder = rebuilder.TreeRebuilder()
    module = builder.visit_module(node, modname, node_file, package)
    return module


def parse(code, module_name='', path=None):
    """Parses a source string in order to obtain an astroid AST from it

    :param str code: The code for the module.
    :param str module_name: The name for the module, if any
    :param str path: The path for the module
    """
    code = textwrap.dedent(code)
    module = _data_build(code, module_name, path)
    module.source_code = code.encode('utf-8')
    module.file_encoding = 'utf-8'
    return zipper.Zipper(module)
