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
"""Module for some node classes. More nodes in scoped_nodes.py
"""
import abc
import functools
import io
import warnings
import sys

import six

from astroid import exceptions
from astroid import base
from astroid import util


@six.add_metaclass(abc.ABCMeta)
class BaseContainer(base.BaseNode):
    """Base class for Set, FrozenSet, Tuple and List."""

    _astroid_fields = ('elts',)

    def __init__(self, elts, lineno=None, col_offset=None):
        self.elts = elts
        super(BaseContainer, self).__init__(lineno, col_offset)


class Statement(base.BaseNode):
    """Statement node adding a few attributes"""
    is_statement = True


class BaseAssignName(base.BaseNode):
    _other_fields = ('name',)

    def __init__(self, name, lineno=None, col_offset=None):
        self.name = name
        super(BaseAssignName, self).__init__(lineno, col_offset)


class AssignName(BaseAssignName):
    pass


class Parameter(BaseAssignName):

    _astroid_fields = ('default', 'annotation')
    _other_fields = ('name', )

    def __init__(self, name, default, annotation, lineno=None, col_offset=None):
        self.name = name
        self.default = default
        self.annotation = annotation
        super(Parameter, self).__init__(name=name, lineno=lineno, col_offset=col_offset)


class DelName(base.BaseNode):

    _other_fields = ('name',)

    def __init__(self, name, lineno=None, col_offset=None):
        self.name = name
        super(DelName, self).__init__(lineno, col_offset)


class Name(base.BaseNode):

    _other_fields = ('name',)

    def __init__(self, name, lineno=None, col_offset=None):
        self.name = name
        super(Name, self).__init__(lineno, col_offset)


class Arguments(base.BaseNode):

    _astroid_fields = ('args', 'vararg', 'kwarg', 'keyword_only', 'positional_only')

    def __init__(self, args, vararg, kwarg, keyword_only, positional_only):
        self.args = args
        self.vararg = vararg
        self.kwarg = kwarg
        self.keyword_only = keyword_only
        self.positional_only = positional_only
        self.positional_and_keyword = self.args + self.positional_only
        super(Arguments, self).__init__(None, None)

    @staticmethod
    def _format_args(args):
        values = []
        if not args:
            return ''
        for i, arg in enumerate(args):
            if isinstance(arg, Tuple):
                values.append('(%s)' % self._format_args(arg.elts))
            else:
                argname = arg.name
                annotation = arg.annotation
                if annotation:
                    argname += ':' + annotation.as_string()
                values.append(argname)
                
                default = arg.default
                if default:
                    values[-1] += '=' + default.as_string()

        return ', '.join(values)

    def format_args(self):
        """return arguments formatted as string"""
        result = []
        if self.positional_and_keyword:
            result.append(self._format_args(self.positional_and_keyword))
        if self.vararg:
            result.append('*%s' % self._format_args((self.vararg, )))
        if self.keyword_only:
            if not self.vararg:
                result.append('*')
            result.append(self._format_args(self.keyword_only))
        if self.kwarg:
            result.append('**%s' % self._format_args((self.kwarg, )))
        return ', '.join(result)

    @staticmethod
    def _find_arg(argname, args, rec=False):
        for i, arg in enumerate(args):
            if isinstance(arg, Tuple):
                if rec:
                    found = self._find_arg(argname, arg.elts)
                    if found[0] is not None:
                        return found
            elif arg.name == argname:
                return i, arg
        return None, None

    def default_value(self, argname):
        """return the default value for an argument

        :raise `NoDefault`: if there is no default value defined
        """
        for place in (self.positional_and_keyword, self.keyword_only):
            i = self._find_arg(argname, place)[0]
            if i is not None:
                value = place[i]
                if not value.default:
                    continue
                return value.default

        raise exceptions.NoDefault(func=self.parent, name=argname)

    def is_argument(self, name):
        """return True if the name is defined in arguments"""
        if self.vararg and name == self.vararg.name:
            return True
        if self.kwarg and name == self.kwarg.name:
            return True
        return self.find_argname(name, True)[1] is not None

    def find_argname(self, argname, rec=False):
        """return index and Name node with given name"""
        if self.positional_and_keyword: # self.args may be None in some cases (builtin function)
            return _find_arg(argname, self.positional_and_keyword, rec)
        return None, None


class AssignAttr(base.BaseNode):

    _astroid_fields = ('expr',)
    _other_fields = ('attrname',)

    def __init__(self, attrname, expr, lineno=None, col_offset=None):
        self.attrname = attrname
        self.expr = expr
        super(AssignAttr, self).__init__(lineno, col_offset)


class Assert(Statement):

    _astroid_fields = ('test', 'fail',)

    def __init__(self, test, fail, lineno=None, col_offset=None):
        self.test = test
        self.fail = fail
        super(Assert, self).__init__(lineno, col_offset)


class Assign(Statement):

    _astroid_fields = ('targets', 'value',)

    def __init__(self, targets, value, lineno=None, col_offset=None):
        self.targets = targets
        self.value = value
        super(Assign, self).__init__(lineno, col_offset)


class AugAssign(Statement):

    _astroid_fields = ('target', 'value')
    _other_fields = ('op',)

    def __init__(self, op, target, value, lineno=None, col_offset=None):
        self.op = op
        self.target = target
        self.value = value
        super(AugAssign, self).__init__(lineno, col_offset)


class Repr(base.BaseNode):

    _astroid_fields = ('value',)

    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        super(Repr, self).__init__(lineno, col_offset)


class BinOp(base.BaseNode):

    _astroid_fields = ('left', 'right')
    _other_fields = ('op',)

    def __init__(self, op, left, right, lineno=None, col_offset=None):
        self.op = op
        self.left = left
        self.right = right
        super(BinOp, self).__init__(lineno, col_offset)


class BoolOp(base.BaseNode):

    _astroid_fields = ('values',)
    _other_fields = ('op',)

    def __init__(self, op, values, lineno=None, col_offset=None):
        self.op = op
        self.values = values
        super(BoolOp, self).__init__(lineno, col_offset)


class Break(Statement):
    pass


class Call(base.BaseNode):

    _astroid_fields = ('func', 'args', 'keywords')

    def __init__(self, func, args, keywords, lineno=None, col_offset=None):
        self.func = func
        self.args = args
        self.keywords = keywords
        super(Call, self).__init__(lineno, col_offset)

    @property
    def starargs(self):
        args = self.args or []
        return [arg for arg in args if isinstance(arg, Starred)]

    @property
    def kwargs(self):
        keywords = self.keywords or []
        return [keyword for keyword in keywords if keyword.arg is base.Empty]


class Compare(base.BaseNode):

    _astroid_fields = ('left', 'comparators')
    _other_fields = ('ops',)

    def __init__(self, ops, left, comparators, lineno=None, col_offset=None):
        self.ops = ops
        self.left = left
        self.comparators = comparators
        super(Compare, self).__init__(lineno, col_offset)


class Comprehension(base.BaseNode):

    _astroid_fields = ('target', 'iter', 'ifs')

    def __init__(self, target, iter, ifs):
        self.target = target
        self.iter = iter


class Const(base.BaseNode):
    """Represent a constant node like num, str, bytes."""
    _other_fields = ('value',)

    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        super(Const, self).__init__(lineno, col_offset)


class NameConstant(Const):
    """Represents a builtin singleton, at the moment True, False, None and NotImplemented."""


class Continue(Statement):
    pass


class Decorators(base.BaseNode):

    _astroid_fields = ('nodes',)

    def __init__(self, nodes, lineno=None, col_offset=None):
        self.nodes = nodes
        super(Decorators, self).__init__(lineno, col_offset)


class DelAttr(base.BaseNode):

    _astroid_fields = ('expr',)
    _other_fields = ('attrname',)

    def __init__(self, attrname, expr, lineno=None, col_offset=None):
        self.attrname = attrname
        self.expr = expr
        super(DelAttr, self).__init__(lineno, col_offset)


class Delete(Statement):

    _astroid_fields = ('targets',)

    def __init__(self, targets, lineno=None, col_offset=None):
        self.targets = targets
        super(Delete, self).__init__(lineno, col_offset)


class Dict(base.BaseNode):

    _astroid_fields = ('keys', 'values')

    def __init__(self, keys, values, lineno=None, col_offset=None):
        self.keys = keys
        self.values = values
        super(Dict, self).__init__(lineno, col_offset)

    @property
    def items(self):
        return list(zip(self.keys, self.values))


class Expr(Statement):

    _astroid_fields = ('value',)

    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        super(Expr, self).__init__(lineno, col_offset)


class Ellipsis(base.BaseNode): # pylint: disable=redefined-builtin
    pass


class ExceptHandler(Statement):

    _astroid_fields = ('type', 'name', 'body',)

    def __init__(self, type, name, body, lineno=None, col_offset=None):
        self.type = type
        self.name = name
        self.body = body
        super(ExceptHandler, self).__init__(lineno, col_offset)

    @property
    def blockstart_tolineno(self):
        if self.name:
            return self.name.tolineno
        elif self.type:
            return self.type.tolineno
        else:
            return self.lineno


class Exec(Statement):

    _astroid_fields = ('expr', 'globals', 'locals')

    def __init__(self, expr, globals, locals, lineno=None, col_offset=None):
        self.expr = expr
        self.globals = globals
        self.locals = locals
        super(Exec, self).__init__(lineno, col_offset)


class ExtSlice(base.BaseNode):

    _astroid_fields = ('dims',)

    def __init__(self, dims, lineno=None, col_offset=None):
        self.dims = dims
        super(ExtSlice, self).__init__(lineno, col_offset)


class For(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('target', 'iter', 'body', 'orelse',)

    def __init__(self, target, iter, body, orelse, lineno=None, col_offset=None):
        self.target = target
        self.iter = iter
        self.body = body
        self.orelse = orelse
        super(For, self).__init__(lineno, col_offset)

    optional_assign = True

    @property
    def blockstart_tolineno(self):
        return self.iter.tolineno


class AsyncFor(For):
    """Asynchronous For built with `async` keyword."""


class Await(base.BaseNode):
    """Await node for the `await` keyword."""

    _astroid_fields = ('value', )

    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        super(Await, self).__init__(lineno, col_offset)


class ImportFrom(Statement):

    _other_fields = ('modname', 'names', 'level')

    def __init__(self, modname, names, level, lineno=None, col_offset=None):
        self.modname = modname
        self.names = names
        self.level = level
        super(ImportFrom, self).__init__(lineno, col_offset)


class Attribute(base.BaseNode):

    _astroid_fields = ('expr',)
    _other_fields = ('attrname',)

    def __init__(self, attrname, expr, lineno=None, col_offset=None):
        self.attrname = attrname
        self.expr = expr
        super(Attribute, self).__init__(lineno, col_offset)


class Global(Statement):

    _other_fields = ('names',)

    def __init__(self, names, lineno=None, col_offset=None):
        self.names = names
        super(Global, self).__init__(lineno, col_offset)


class If(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('test', 'body', 'orelse')

    def __init__(self, test, body, orelse, lineno=None, col_offset=None):
        self.test = test
        self.body = body
        self.orelse = orelse
        super(If, self).__init__(lineno, col_offset)

    @property
    def blockstart_tolineno(self):
        return self.test.tolineno

    def block_range(self, lineno):
        """handle block line numbers range for if statements"""
        if lineno == self.body[0].fromlineno:
            return lineno, lineno
        if lineno <= self.body[-1].tolineno:
            return lineno, self.body[-1].tolineno
        return self._elsed_block_range(lineno, self.orelse,
                                       self.body[0].fromlineno - 1)


class IfExp(base.BaseNode):

    _astroid_fields = ('test', 'body', 'orelse')

    def __init__(self, test, body, orelse, lineno=None, col_offset=None):
        self.test = test
        self.body = body
        self.orelse = orelse
        super(IfExp, self).__init__(lineno, col_offset)


class Import(Statement):

    _other_fields = ('names',)

    def __init__(self, names, lineno=None, col_offset=None):
        self.names = names
        super(Import, self).__init__(lineno, col_offset)


class Index(base.BaseNode):

    _astroid_fields = ('value',)

    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        super(Index, self).__init__(lineno, col_offset)


class Keyword(base.BaseNode):

    _astroid_fields = ('value',)
    _other_fields = ('arg',)

    def __init__(self, arg, value, lineno=None, col_offset=None):
        self.arg = arg
        self.value = value
        super(Keyword, self).__init__(lineno, col_offset)


class List(BaseContainer):

    _other_fields = ('ctx',)

    def __init__(self, ctx, elts, lineno=None, col_offset=None):
        self.ctx = ctx
        super(List, self).__init__(elts, lineno, col_offset)


class Nonlocal(Statement):

    _other_fields = ('names',)

    def __init__(self, names, lineno=None, col_offset=None):
        self.names = names
        super(Nonlocal, self).__init__(lineno, col_offset)


class Pass(Statement):
    pass


class Print(Statement):

    _astroid_fields = ('dest', 'values')
    _other_fields = ('nl',)

    def __init__(self, nl, dest, values, lineno=None, col_offset=None):
        self.nl = nl
        self.dest = dest
        self.values = values
        super(Print, self).__init__(lineno, col_offset)


class Raise(Statement):

    _astroid_fields = ('exc', 'cause', 'traceback')

    def __init__(self, exc, cause, traceback, lineno=None, col_offset=None):
        self.exc = exc
        self.cause = cause
        self.traceback = traceback
        super(Raise, self).__init__(lineno, col_offset)


class Return(Statement):

    _astroid_fields = ('value',)

    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        super(Return, self).__init__(lineno, col_offset)


class Set(BaseContainer):
    pass
    

class Slice(base.BaseNode):

    _astroid_fields = ('lower', 'upper', 'step')

    def __init__(self, lower, upper, step, lineno=None, col_offset=None):
        self.lower = lower
        self.upper = upper
        self.step = step
        super(Slice, self).__init__(lineno, col_offset)


class Starred(base.BaseNode):

    _astroid_fields = ('value',)
    _other_fields = ('ctx', )

    def __init__(self, ctx, value, lineno=None, col_offset=None):
        self.ctx = ctx
        self.value = value
        super(Starred, self).__init__(lineno=lineno, col_offset=col_offset)


class Subscript(base.BaseNode):

    _astroid_fields = ('value', 'slice')
    _other_fields = ('ctx', )

    def __init__(self, ctx, value, slice, lineno=None, col_offset=None):
        self.ctx = ctx
        self.value = value
        self.slice = slice
        super(Subscript, self).__init__(lineno=lineno, col_offset=col_offset)


class TryExcept(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('body', 'handlers', 'orelse',)

    def __init__(self, body, handlers, orelse, lineno=None, col_offset=None):
        self.body = body
        self.handlers = handlers
        self.orelse = orelse
        super(TryExcept, self).__init__(lineno, col_offset)

    def block_range(self, lineno):
        """handle block line numbers range for try/except statements"""
        last = None
        for exhandler in self.handlers:
            if exhandler.type and lineno == exhandler.type.fromlineno:
                return lineno, lineno
            if exhandler.body[0].fromlineno <= lineno <= exhandler.body[-1].tolineno:
                return lineno, exhandler.body[-1].tolineno
            if last is None:
                last = exhandler.body[0].fromlineno - 1
        return self._elsed_block_range(lineno, self.orelse, last)


class TryFinally(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('body', 'finalbody',)

    def __init__(self, body, finalbody, lineno=None, col_offset=None):
        self.body = body
        self.finalbody = finalbody
        super(TryFinally, self).__init__(lineno, col_offset)

    def block_range(self, lineno):
        """handle block line numbers range for try/finally statements"""
        child = self.body[0]
        # py2.5 try: except: finally:
        if (isinstance(child, TryExcept) and child.fromlineno == self.fromlineno
                and lineno > self.fromlineno and lineno <= child.tolineno):
            return child.block_range(lineno)
        return self._elsed_block_range(lineno, self.finalbody)


class Tuple(BaseContainer):

    _other_fields = ('ctx',)

    def __init__(self, ctx, elts, lineno=None, col_offset=None):
        self.ctx = ctx
        super(Tuple, self).__init__(elts, lineno, col_offset)


class UnaryOp(base.BaseNode):

    _astroid_fields = ('operand',)
    _other_fields = ('op',)

    def __init__(self, op, operand, lineno=None, col_offset=None):
        self.op = op
        self.operand = operand
        super(UnaryOp, self).__init__(lineno, col_offset)


class While(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('test', 'body', 'orelse',)

    def __init__(self, test, body, orelse, lineno=None, col_offset=None):
        self.test = test
        self.body = body
        self.orelse = orelse
        super(While, self).__init__(lineno, col_offset)

    @property
    def blockstart_tolineno(self):
        return self.test.tolineno

    def block_range(self, lineno):
        """handle block line numbers range for for and while statements"""
        return self._elsed_block_range(lineno, self.orelse)


class With(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('items', 'body')

    def __init__(self, items, body, lineno=None, col_offset=None):
        self.items = items
        self.body = body
        super(With, self).__init__(lineno, col_offset)

    @property
    def blockstart_tolineno(self):
        return self.items[-1].context_expr.tolineno


class WithItem(base.BaseNode):
    _astroid_fields = ('context_expr', 'optional_vars')

    def __init__(self, context_expr, optional_vars, lineno=None, col_offset=None):
        self.context_expr = context_expr
        self.optional_vars = optional_vars
        super(WithItem, self).__init__(lineno, col_offset)


class AsyncWith(With):
    """Asynchronous `with` built with the `async` keyword."""


class Yield(base.BaseNode):

    _astroid_fields = ('value',)

    def __init__(self, value, lineno=None, col_offset=None):
        self.value = value
        super(Yield, self).__init__(lineno, col_offset)


class YieldFrom(Yield):
    pass


class DictUnpack(base.BaseNode):
    """Represents the unpacking of dicts into dicts using PEP 448."""



class Module(base.BaseNode):
    _astroid_fields = ('body',)

    fromlineno = 0
    lineno = 0

    if six.PY2:
        _other_fields = ('name', 'doc', 'file_encoding', 'package',
                         'pure_python', 'source_code', 'source_file')
    else:
        _other_fields = ('name', 'doc', 'package', 'pure_python',
                         'source_code', 'source_file')

    def __init__(self, name, doc, file_encoding, package, pure_python, source_code, source_file, body, lineno=None, col_offset=None):
        self.name = name
        self.doc = doc
        self.file_encoding = file_encoding
        self.package = package
        self.pure_python = pure_python
        self.source_code = source_code
        self.source_file = source_file
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
            if (isinstance(self.body[index], ImportFrom)
                and self.body[index].modname == '__future__'):
                # This is a `from __future__ import` statement.
                future_imports.extend(n[0] for n in getattr(self.body[index],
                                                            'names', ()))
            elif (index == 0 and isinstance(self.body[0], Expr)):
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

    if six.PY2:
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


class BaseComprehension(base.BaseNode):
    _astroid_fields = ('generators', 'elt')

    def __init__(self, generators, elt, lineno=None, col_offset=None):
        self.generators = generators
        self.elt = elt
        super(BaseComprehension, self).__init__(lineno, col_offset)


class GeneratorExp(BaseComprehension):
    pass


class DictComp(BaseComprehension):
    _astroid_fields = ('generators', 'key', 'value')

    def __init__(self, generators, key, value, lineno=None, col_offset=None):
        self.generators = generators
        self.key = key
        self.value = value
        # TODO: figure out a better solution here to inheritance for DictComp.
        
        # super(DictComp, self).__init__(lineno, col_offset)
        self.lineno = lineno
        self.col_offset = col_offset


class SetComp(BaseComprehension):
    pass


class _ListComp(base.BaseNode):
    pass

if six.PY3:
    class ListComp(_ListComp, BaseComprehension):
        pass
else:
    class ListComp(_ListComp):
        _astroid_fields = ('generators', 'elt')

        # TODO: this still duplicates code in base comprehension.
        def __init__(self, generators, elt, lineno=None, col_offset=None):
            self.generators = generators
            self.elt = elt
            super(_ListComp, self).__init__(lineno, col_offset)


class LambdaFunctionMixin(base.BaseNode):
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
        if isinstance(arg, Tuple):
            _rec_get_names(arg.elts, names)
        else:
            names.append(arg.name)
    return names


class Lambda(LambdaFunctionMixin):
    _astroid_fields = ('args', 'body',)
    _other_fields = ('name',)
    name = '<lambda>'

    def __init__(self, args, body, lineno=None, col_offset=None):
        self.args = args
        self.body = body
        super(Lambda, self).__init__(lineno, col_offset)


class FunctionDef(LambdaFunctionMixin, Statement):

    _astroid_fields = ('decorators', 'args', 'body', 'returns')
    _other_fields = ('name', 'doc')

    def __init__(self, name, doc, args, body, decorators, returns, lineno=None, col_offset=None):
        self.name = name
        self.doc = doc
        self.args = args
        self.body = body
        self.decorators = decorators
        self.returns = returns
        super(FunctionDef, self).__init__(lineno, col_offset)

    @property
    def fromlineno(self):
        # lineno is the line number of the first decorator, we want the def
        # statement lineno
        lineno = self.lineno
        if self.decorators:
            lineno += sum(node.tolineno - node.lineno + 1
                          for node in self.decorators.nodes)

        return lineno

    @property
    def blockstart_tolineno(self):
        return self.args.tolineno

    def block_range(self, lineno):
        """return block line numbers.

        start from the "def" position whatever the given lineno
        """
        return self.fromlineno, self.tolineno

    def is_generator(self):
        """return true if this is a generator function"""
        to_visit = list(self)
        to_visit.reverse()
        while to_visit:
            descendant = to_visit.pop()
            if isinstance(descendant, (Yield, YieldFrom)):
                return True
            if not isinstance(descendant, (FunctionDef, Lambda)):
                to_visit.extend(reversed(tuple(descendant)))
        return False


class AsyncFunctionDef(FunctionDef):
    """Asynchronous function created with the `async` keyword."""


class ClassDef(Statement):

    _astroid_fields = ('decorators', 'bases', 'body', 'keywords')
    _other_fields = ('name', 'doc')

    def __init__(self, name, doc, bases, body, decorators, keywords, lineno=None, col_offset=None):
        self.name = name
        self.doc = doc
        self.bases = bases
        self.body = body
        self.decorators = decorators
        self.keywords = keywords
        super(ClassDef, self).__init__(lineno, col_offset)

    @property
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
