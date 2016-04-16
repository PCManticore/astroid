# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

"""
This module contains the classes for "scoped" node, i.e. which are opening a
new local scope in the language definition : Module, ClassDef, FunctionDef (and
Lambda, GeneratorExp, DictComp and SetComp to some extent).
"""

import collections
import io
import itertools
import warnings

try:
    from functools import singledispatch as _singledispatch
except ImportError:
    from singledispatch import singledispatch as _singledispatch

import six

from astroid.tree import base
from astroid import context as contextmod
from astroid import exceptions
from astroid import decorators as decorators_mod
from astroid.interpreter import lookup
from astroid.interpreter import objects
from astroid.interpreter import objectmodel
from astroid.interpreter import runtimeabc
from astroid.interpreter.util import infer_stmts
from astroid import manager
from astroid.tree import base as treebase
from astroid.tree import node_classes
from astroid.tree import treeabc
from astroid import util

class QualifiedNameMixin(object):

    def qname(node):
        """Return the 'qualified' name of the node."""
        if node.parent is None:
            return node.name
        return '%s.%s' % (node.parent.frame().qname(), node.name)


@util.register_implementation(treeabc.Module)
class Module(QualifiedNameMixin, lookup.LocalsDictNode):
    _astroid_fields = ('body',)

    fromlineno = 0
    lineno = 0

    if six.PY2:
        _other_fields = ('name', 'doc', 'file_encoding', 'package',
                         'pure_python', 'source_code', 'source_file')
    else:
        _other_fields = ('name', 'doc', 'package', 'pure_python',
                         'source_code', 'source_file')

    def __init__(self, name, doc, package=None, parent=None,
                 pure_python=True, source_code=None, source_file=None):
        self.name = name
        self.doc = doc
        self.package = package
        self.parent = parent
        self.pure_python = pure_python
        self.source_code = source_code
        self.source_file = source_file
        self.body = []

    def postinit(self, body=None):
        self.body = body

    @property
    def future_imports(self):
        index = 0
        future_imports = []

        # The start of a Python module has an optional docstring
        # followed by any number of `from __future__ import`
        # statements.  This doesn't try to test for incorrect ASTs,
        # but should function on all correct ones.
        while (index < len(self.body)):
            if (isinstance(self.body[index], node_classes.ImportFrom)
                and self.body[index].modname == '__future__'):
                # This is a `from __future__ import` statement.
                future_imports.extend(n[0] for n in getattr(self.body[index],
                                                            'names', ()))
            elif (index == 0 and isinstance(self.body[0], node_classes.Expr)):
                # This is a docstring, so do nothing.
                pass
            else:
                # This is some other kind of statement, so the future
                # imports must be finished.
                break
            index += 1
        return frozenset(future_imports)

    def _get_stream(self):
        if self.source_code is not None:
            return io.BytesIO(self.source_code)
        if self.source_file is not None:
            stream = open(self.source_file, 'rb')
            return stream
        return None

    def stream(self):
        """Get a stream to the underlying file or bytes."""
        return self._get_stream()

    def block_range(self, lineno):
        """return block line numbers.

        start from the beginning whatever the given lineno
        """
        return self.fromlineno, self.tolineno

    def fully_defined(self):
        """return True if this module has been built from a .py file
        and so contains a complete representation including the code
        """
        return self.file is not None and self.file.endswith('.py')

    def statement(self):
        """return the first parent node marked as statement node
        consider a module as a statement...
        """
        return self

    def previous_sibling(self):
        """module has no sibling"""
        return

    def next_sibling(self):
        """module has no sibling"""
        return

    if six.PY2:
        @decorators_mod.cachedproperty
        def _absolute_import_activated(self):
            return 'absolute_import' in self.future_imports
    else:
        _absolute_import_activated = True

    def absolute_import_activated(self):
        return self._absolute_import_activated

    def relative_to_absolute_name(self, modname, level):
        """return the absolute module name for a relative import.

        The relative import can be implicit or explicit.
        """
        # XXX this returns non sens when called on an absolute import
        # like 'pylint.checkers.astroid.utils'
        # XXX doesn't return absolute name if self.name isn't absolute name
        if self.absolute_import_activated() and level is None:
            return modname
        if level:
            if self.package:
                level = level - 1
            if level and self.name.count('.') < level:
                raise exceptions.TooManyLevelsError(
                    level=level, name=self.name)

            package_name = self.name.rsplit('.', level)[0]
        elif self.package:
            package_name = self.name
        else:
            package_name = self.name.rsplit('.', 1)[0]
        if package_name:
            if not modname:
                return package_name
            return '%s.%s' % (package_name, modname)
        return modname

    def public_names(self):
        """Get the list of the names which are publicly available in this module."""
        return [name for name in self.keys() if not name.startswith('_')]


class ComprehensionScope(lookup.LocalsDictNode):

    def frame(self):
        return self.parent.frame()


@util.register_implementation(treeabc.GeneratorExp)
class GeneratorExp(ComprehensionScope):
    _astroid_fields = ('elt', 'generators')

    def __init__(self, lineno=None, col_offset=None, parent=None):
        super(GeneratorExp, self).__init__(lineno, col_offset, parent)

    def postinit(self, elt=None, generators=None):
        self.elt = elt
        if generators is None:
            self.generators = []
        else:
            self.generators = generators


@util.register_implementation(treeabc.DictComp)
class DictComp(ComprehensionScope):
    _astroid_fields = ('key', 'value', 'generators')

    def __init__(self, lineno=None, col_offset=None, parent=None):
        super(DictComp, self).__init__(lineno, col_offset, parent)

    def postinit(self, key=None, value=None, generators=None):
        self.key = key
        self.value = value
        if generators is None:
            self.generators = []
        else:
            self.generators = generators


@util.register_implementation(treeabc.SetComp)
class SetComp(ComprehensionScope):
    _astroid_fields = ('elt', 'generators')
    # _other_other_fields = ('locals',)
    elt = None
    generators = None

    def __init__(self, lineno=None, col_offset=None, parent=None):
        super(SetComp, self).__init__(lineno, col_offset, parent)

    def postinit(self, elt=None, generators=None):
        self.elt = elt
        if generators is None:
            self.generators = []
        else:
            self.generators = generators


@util.register_implementation(treeabc.ListComp)
class _ListComp(treebase.NodeNG):
    """class representing a ListComp node"""
    _astroid_fields = ('elt', 'generators')
    elt = None
    generators = None

    def postinit(self, elt=None, generators=None):
        self.elt = elt
        self.generators = generators


if six.PY3:
    class ListComp(_ListComp, ComprehensionScope):
        """class representing a ListComp node"""
        # _other_other_fields = ('locals',)

        def __init__(self, lineno=None, col_offset=None, parent=None):
            super(ListComp, self).__init__(lineno, col_offset, parent)
else:
    class ListComp(_ListComp):
        """class representing a ListComp node"""


class LambdaFunctionMixin(QualifiedNameMixin, base.FilterStmtsMixin):
    """Common code for lambda and functions."""

    def argnames(self):
        """return a list of argument names"""
        if self.args.positional_and_keyword: # maybe None with builtin functions
            names = _rec_get_names(self.args.positional_and_keyword)
        else:
            names = []
        if self.args.vararg:
            names.append(self.args.vararg.name)
        if self.args.kwarg:
            names.append(self.args.kwarg.name)
        if self.args.keyword_only:
            names.extend([arg.name for arg in self.keyword_only])
        return names


def _rec_get_names(args, names=None):
    """return a list of all argument names"""
    if names is None:
        names = []
    for arg in args:
        if isinstance(arg, node_classes.Tuple):
            _rec_get_names(arg.elts, names)
        else:
            names.append(arg.name)
    return names


@util.register_implementation(treeabc.Lambda)
class Lambda(LambdaFunctionMixin, lookup.LocalsDictNode):
    _astroid_fields = ('args', 'body',)

    def __init__(self, lineno=None, col_offset=None, parent=None):
        self.args = []
        self.body = []
        super(Lambda, self).__init__(lineno, col_offset, parent)

    def postinit(self, args, body):
        self.args = args
        self.body = body


# TODO: what baseclasses to keep?
@util.register_implementation(treeabc.FunctionDef)
class FunctionDef(LambdaFunctionMixin, lookup.LocalsDictNode,
                  node_classes.Statement):

    # TODO: this should look the same
    if six.PY3:
        _astroid_fields = ('decorators', 'args', 'body', 'returns')
    else:
        _astroid_fields = ('decorators', 'args', 'body')
    _other_fields = ('name', 'doc')

    def __init__(self, name=None, doc=None, lineno=None,
                 col_offset=None, parent=None):
        self.name = name
        self.doc = doc
        super(FunctionDef, self).__init__(lineno, col_offset, parent)

    # pylint: disable=arguments-differ; different than Lambdas
    def postinit(self, args, body, decorators=None, returns=None):
        self.args = args
        self.body = body
        self.decorators = decorators
        self.returns = returns

    @decorators_mod.cachedproperty
    def fromlineno(self):
        # lineno is the line number of the first decorator, we want the def
        # statement lineno
        lineno = self.lineno
        if self.decorators is not None:
            lineno += sum(node.tolineno - node.lineno + 1
                          for node in self.decorators.nodes)

        return lineno

    @decorators_mod.cachedproperty
    def blockstart_tolineno(self):
        return self.args.tolineno

    def block_range(self, lineno):
        """return block line numbers.

        start from the "def" position whatever the given lineno
        """
        return self.fromlineno, self.tolineno

    def is_generator(self):
        """return true if this is a generator function"""
        yield_nodes = (node_classes.Yield, node_classes.YieldFrom)
        return next(self.nodes_of_class(yield_nodes,
                                        skip_klass=(FunctionDef, Lambda)), False)


@util.register_implementation(treeabc.AsyncFunctionDef)
class AsyncFunctionDef(FunctionDef):
    """Asynchronous function created with the `async` keyword."""


# TODO: what base classes to keep?
class ClassDef(QualifiedNameMixin, base.FilterStmtsMixin,
               lookup.LocalsDictNode,
               node_classes.Statement):

    _astroid_fields = ('decorators', 'bases', 'body')
    _other_fields = ('name', 'doc')

    def __init__(self, name=None, doc=None, lineno=None,
                 col_offset=None, parent=None):
        self.bases = []
        self.body = []
        self.name = name
        self.doc = doc
        super(ClassDef, self).__init__(lineno, col_offset, parent)

    def postinit(self, bases, body, decorators):
        self.bases = bases
        self.body = body
        self.decorators = decorators

    @decorators_mod.cachedproperty
    def blockstart_tolineno(self):
        if self.bases:
            return self.bases[-1].tolineno
        else:
            return self.fromlineno

    def block_range(self, lineno):
        """return block line numbers.

        start from the "class" position whatever the given lineno
        """
        return self.fromlineno, self.tolineno

    @property
    def basenames(self):
        """Get the list of parent class names, as they appear in the class definition."""
        return [bnode.as_string() for bnode in self.bases]

    def has_base(self, node):
        return node in self.bases
