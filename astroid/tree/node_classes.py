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
from astroid.tree import base
from astroid import util


@six.add_metaclass(abc.ABCMeta)
class BaseContainer(base.BaseNode):
    """Base class for Set, FrozenSet, Tuple and List."""

    _astroid_fields = ('elts',)

    def __init__(self, lineno=None, col_offset=None, parent=None):
        self.elts = []
        super(BaseContainer, self).__init__(lineno, col_offset, parent)

    def postinit(self, elts):
        self.elts = elts


class Statement(base.BaseNode):
    """Statement node adding a few attributes"""
    is_statement = True

    # TODO: is this equivalent to zipper's next/previous sibling?
    def next_sibling(self):
        """return the next sibling statement"""
        stmts = self.parent.child_sequence(self)
        index = stmts.index(self)
        try:
            return stmts[index + 1]
        except IndexError:
            pass

    def previous_sibling(self):
        """return the previous sibling statement"""
        stmts = self.parent.child_sequence(self)
        index = stmts.index(self)
        if index >= 1:
            return stmts[index - 1]



class BaseAssignName(base.BaseNode):
    _other_fields = ('name',)

    def __init__(self, name=None, lineno=None, col_offset=None, parent=None):
        self.name = name
        super(BaseAssignName, self).__init__(lineno, col_offset, parent)


class AssignName(BaseAssignName):
    pass


class Parameter(BaseAssignName):

    _astroid_fields = ('default', 'annotation')
    _other_fields = ('name', )

    def __init__(self, name=None, lineno=None, col_offset=None, parent=None):
        super(Parameter, self).__init__(name=name, lineno=lineno,
                                        col_offset=col_offset, parent=parent)

    def postinit(self, default, annotation):
        self.default = default
        self.annotation = annotation


class DelName(base.BaseNode):

    _other_fields = ('name',)

    def __init__(self, name=None, lineno=None, col_offset=None, parent=None):
        self.name = name
        super(DelName, self).__init__(lineno, col_offset, parent)


class Name(base.BaseNode):

    _other_fields = ('name',)

    def __init__(self, name=None, lineno=None, col_offset=None, parent=None):
        self.name = name
        super(Name, self).__init__(lineno, col_offset, parent)
    

class Arguments(base.BaseNode):

    _astroid_fields = ('args', 'vararg', 'kwarg', 'keyword_only', 'positional_only')

    def __init__(self, parent=None):
        # We don't want lineno and col_offset from the parent's __init__.
        super(Arguments, self).__init__(parent=parent)

    def postinit(self, args, vararg, kwarg, keyword_only, positional_only):
        self.args = args
        self.vararg = vararg
        self.kwarg = kwarg
        self.keyword_only = keyword_only
        self.positional_only = positional_only
        self.positional_and_keyword = self.args + self.positional_only

    @property
    def fromlineno(self):
        # Let the Function's lineno be the lineno for this.
        if self.parent.fromlineno:
            return self.parent.fromlineno

        return super(Arguments, self).fromlineno

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

    def get_children(self):
        """override get_children to skip over None elements in kw_defaults"""
        for child in super(Arguments, self).get_children():
            if child is not None:
                yield child



class AssignAttr(base.BaseNode):

    _astroid_fields = ('expr',)
    _other_fields = ('attrname',)
    expr = base.Empty

    def __init__(self, attrname=None, lineno=None, col_offset=None, parent=None):
        self.attrname = attrname
        super(AssignAttr, self).__init__(lineno, col_offset, parent)

    def postinit(self, expr=base.Empty):
        self.expr = expr


class Assert(Statement):

    _astroid_fields = ('test', 'fail',)
    test = base.Empty
    fail = base.Empty

    def postinit(self, test=base.Empty, fail=base.Empty):
        self.fail = fail
        self.test = test


class Assign(Statement):

    _astroid_fields = ('targets', 'value',)
    targets = base.Empty
    value = base.Empty

    def postinit(self, targets=base.Empty, value=base.Empty):
        self.targets = targets
        self.value = value


class AugAssign(Statement):

    _astroid_fields = ('target', 'value')
    _other_fields = ('op',)
    target = base.Empty
    value = base.Empty

    def __init__(self, op=None, lineno=None, col_offset=None, parent=None):
        self.op = op
        super(AugAssign, self).__init__(lineno, col_offset, parent)

    def postinit(self, target=base.Empty, value=base.Empty):
        self.target = target
        self.value = value


class Repr(base.BaseNode):

    _astroid_fields = ('value',)
    value = base.Empty

    def postinit(self, value=base.Empty):
        self.value = value


class BinOp(base.BaseNode):

    _astroid_fields = ('left', 'right')
    _other_fields = ('op',)
    left = base.Empty
    right = base.Empty

    def __init__(self, op=None, lineno=None, col_offset=None, parent=None):
        self.op = op
        super(BinOp, self).__init__(lineno, col_offset, parent)

    def postinit(self, left=base.Empty, right=base.Empty):
        self.left = left
        self.right = right


class BoolOp(base.BaseNode):

    _astroid_fields = ('values',)
    _other_fields = ('op',)
    values = base.Empty

    def __init__(self, op=None, lineno=None, col_offset=None, parent=None):
        self.op = op
        super(BoolOp, self).__init__(lineno, col_offset, parent)

    def postinit(self, values=base.Empty):
        self.values = values


class Break(Statement):
    pass


class Call(base.BaseNode):

    _astroid_fields = ('func', 'args', 'keywords')
    func = base.Empty
    args = base.Empty
    keywords = base.Empty

    def postinit(self, func=base.Empty, args=base.Empty, keywords=base.Empty):
        self.func = func
        self.args = args
        self.keywords = keywords

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
    left = base.Empty
    comparators = base.Empty

    def __init__(self, ops, lineno=None, col_offset=None, parent=None):
        self.comparators = []
        self.ops = ops
        super(Compare, self).__init__(lineno, col_offset, parent)

    def postinit(self, left=base.Empty, comparators=base.Empty):
        self.left = left
        self.comparators = comparators

    def get_children(self):
        yield self.left
        for comparator in self.comparators:
            yield comparator

    def last_child(self):
        return self.comparators[-1]


class Comprehension(base.BaseNode):

    _astroid_fields = ('target', 'iter', 'ifs')
    target = base.Empty
    iter = base.Empty
    ifs = base.Empty

    def __init__(self, parent=None):
        self.parent = parent

    def postinit(self, target=base.Empty, iter=base.Empty, ifs=base.Empty):
        self.target = target
        self.iter = iter
        self.ifs = ifs


class Const(base.BaseNode):
    """Represent a constant node like num, str, bytes."""
    _other_fields = ('value',)

    def __init__(self, value, lineno=None, col_offset=None, parent=None):
        self.value = value
        super(Const, self).__init__(lineno, col_offset, parent)

    
class NameConstant(Const):
    """Represents a builtin singleton, at the moment True, False, None and NotImplemented."""


class Continue(Statement):
    pass


class Decorators(base.BaseNode):

    _astroid_fields = ('nodes',)
    nodes = base.Empty

    def postinit(self, nodes):
        self.nodes = nodes


class DelAttr(base.BaseNode):

    _astroid_fields = ('expr',)
    _other_fields = ('attrname',)
    expr = base.Empty

    def __init__(self, attrname=None, lineno=None, col_offset=None, parent=None):
        self.attrname = attrname
        super(DelAttr, self).__init__(lineno, col_offset, parent)

    def postinit(self, expr=base.Empty):
        self.expr = expr


class Delete(Statement):

    _astroid_fields = ('targets',)
    targets = base.Empty

    def postinit(self, targets=base.Empty):
        self.targets = targets


class Dict(base.BaseNode):

    _astroid_fields = ('keys', 'values')

    def __init__(self, lineno=None, col_offset=None, parent=None):
        self.keys = []
        self.values = []
        super(Dict, self).__init__(lineno, col_offset, parent)

    def postinit(self, keys, values):
        self.keys = keys
        self.values = values

    @property
    def items(self):
        return list(zip(self.keys, self.values))

    def get_children(self):
        """get children of a Dict node"""
        # overrides get_children
        for key, value in zip(self.keys, self.values):
            yield key
            yield value

    def last_child(self):
        """override last_child"""
        if self.values:
            return self.values[-1]
        return None


class Expr(Statement):

    _astroid_fields = ('value',)
    value = base.Empty

    def postinit(self, value=base.Empty):
        self.value = value


class Ellipsis(base.BaseNode): # pylint: disable=redefined-builtin
    pass


class ExceptHandler(Statement):

    _astroid_fields = ('type', 'name', 'body',)
    type = base.Empty
    name = base.Empty
    body = base.Empty

    def postinit(self, type=base.Empty, name=base.Empty, body=base.Empty):
        self.type = type
        self.name = name
        self.body = body

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
    expr = base.Empty
    globals = base.Empty
    locals = base.Empty

    def postinit(self, expr=base.Empty, globals=base.Empty, locals=base.Empty):
        self.expr = expr
        self.globals = globals
        self.locals = locals


class ExtSlice(base.BaseNode):

    _astroid_fields = ('dims',)
    dims = base.Empty

    def postinit(self, dims=base.Empty):
        self.dims = dims


class For(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('target', 'iter', 'body', 'orelse',)
    target = base.Empty
    iter = base.Empty
    body = base.Empty
    orelse = base.Empty

    def postinit(self, target=base.Empty, iter=base.Empty, body=base.Empty, orelse=base.Empty):
        self.target = target
        self.iter = iter
        self.body = body
        self.orelse = orelse

    optional_assign = True

    @property
    def blockstart_tolineno(self):
        return self.iter.tolineno


class AsyncFor(For):
    """Asynchronous For built with `async` keyword."""


class Await(base.BaseNode):
    """Await node for the `await` keyword."""

    _astroid_fields = ('value', )
    value = base.Empty

    def postinit(self, value=base.Empty):
        self.value = value


class ImportFrom(Statement):

    _other_fields = ('modname', 'names', 'level')

    def __init__(self, fromname, names, level=0, lineno=None,
                 col_offset=None, parent=None):
        self.modname = fromname
        self.names = names
        self.level = level
        super(ImportFrom, self).__init__(lineno, col_offset, parent)


class Attribute(base.BaseNode):

    _astroid_fields = ('expr',)
    _other_fields = ('attrname',)
    expr = base.Empty

    def __init__(self, attrname=None, lineno=None, col_offset=None, parent=None):
        self.attrname = attrname
        super(Attribute, self).__init__(lineno, col_offset, parent)

    def postinit(self, expr=base.Empty):
        self.expr = expr


class Global(Statement):

    _other_fields = ('names',)

    def __init__(self, names, lineno=None, col_offset=None, parent=None):
        self.names = names
        super(Global, self).__init__(lineno, col_offset, parent)


class If(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('test', 'body', 'orelse')
    test = base.Empty
    body = base.Empty
    orelse = base.Empty

    def postinit(self, test=base.Empty, body=base.Empty, orelse=base.Empty):
        self.test = test
        self.body = body
        self.orelse = orelse

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
    test = base.Empty
    body = base.Empty
    orelse = base.Empty

    def postinit(self, test=base.Empty, body=base.Empty, orelse=base.Empty):
        self.test = test
        self.body = body
        self.orelse = orelse


class Import(Statement):

    _other_fields = ('names',)

    def __init__(self, names=None, lineno=None, col_offset=None, parent=None):
        self.names = names
        super(Import, self).__init__(lineno, col_offset, parent)


class Index(base.BaseNode):

    _astroid_fields = ('value',)
    value = base.Empty

    def postinit(self, value=base.Empty):
        self.value = value


class Keyword(base.BaseNode):

    _astroid_fields = ('value',)
    _other_fields = ('arg',)
    value = base.Empty

    def __init__(self, arg=None, lineno=None, col_offset=None, parent=None):
        self.arg = arg
        super(Keyword, self).__init__(lineno, col_offset, parent)

    def postinit(self, value=base.Empty):
        self.value = value


class List(BaseContainer):

    _other_fields = ('ctx',)

    def __init__(self, ctx=None, lineno=None,
                 col_offset=None, parent=None):
        self.ctx = ctx
        super(List, self).__init__(lineno, col_offset, parent)


class Nonlocal(Statement):

    _other_fields = ('names',)

    def __init__(self, names, lineno=None, col_offset=None, parent=None):
        self.names = names
        super(Nonlocal, self).__init__(lineno, col_offset, parent)


class Pass(Statement):
    pass


class Print(Statement):

    _astroid_fields = ('dest', 'values',)
    dest = base.Empty
    values = base.Empty

    def __init__(self, nl=None, lineno=None, col_offset=None, parent=None):
        self.nl = nl
        super(Print, self).__init__(lineno, col_offset, parent)

    def postinit(self, dest=base.Empty, values=base.Empty):
        self.dest = dest
        self.values = values


class Raise(Statement):

    _astroid_fields = ('exc', 'cause', 'traceback')

    def postinit(self, exc=base.Empty, cause=base.Empty, traceback=base.Empty):
        self.exc = exc
        self.cause = cause
        self.traceback = traceback


class Return(Statement):

    _astroid_fields = ('value',)
    value = base.Empty

    def postinit(self, value=base.Empty):
        self.value = value


class Set(BaseContainer):
    pass
    

class Slice(base.BaseNode):

    _astroid_fields = ('lower', 'upper', 'step')
    lower = base.Empty
    upper = base.Empty
    step = base.Empty

    def postinit(self, lower=base.Empty, upper=base.Empty, step=base.Empty):
        self.lower = lower
        self.upper = upper
        self.step = step


class Starred(base.BaseNode):

    _astroid_fields = ('value',)
    _other_fields = ('ctx', )
    value = base.Empty

    def __init__(self, ctx=None, lineno=None, col_offset=None, parent=None):
        self.ctx = ctx
        super(Starred, self).__init__(lineno=lineno,
                                      col_offset=col_offset, parent=parent)

    def postinit(self, value=base.Empty):
        self.value = value


class Subscript(base.BaseNode):

    _astroid_fields = ('value', 'slice')
    _other_fields = ('ctx', )
    value = base.Empty
    slice = base.Empty

    def __init__(self, ctx=None, lineno=None, col_offset=None, parent=None):
        self.ctx = ctx
        super(Subscript, self).__init__(lineno=lineno,
                                        col_offset=col_offset, parent=parent)

    def postinit(self, value=base.Empty, slice=base.Empty):
        self.value = value
        self.slice = slice


class TryExcept(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('body', 'handlers', 'orelse',)
    body = base.Empty
    handlers = base.Empty
    orelse = base.Empty

    def postinit(self, body=base.Empty, handlers=base.Empty, orelse=base.Empty):
        self.body = body
        self.handlers = handlers
        self.orelse = orelse

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
    body = base.Empty
    finalbody = base.Empty

    def postinit(self, body=base.Empty, finalbody=base.Empty):
        self.body = body
        self.finalbody = finalbody

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

    def __init__(self, ctx=None, lineno=None,
                 col_offset=None, parent=None):
        self.ctx = ctx
        super(Tuple, self).__init__(lineno, col_offset, parent)


class UnaryOp(base.BaseNode):

    _astroid_fields = ('operand',)
    _other_fields = ('op',)
    operand = base.Empty

    def __init__(self, op=None, lineno=None, col_offset=None, parent=None):
        self.op = op
        super(UnaryOp, self).__init__(lineno, col_offset, parent)

    def postinit(self, operand=base.Empty):
        self.operand = operand


class While(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('test', 'body', 'orelse',)
    test = base.Empty
    body = base.Empty
    orelse = base.Empty

    def postinit(self, test=base.Empty, body=base.Empty, orelse=base.Empty):
        self.test = test
        self.body = body
        self.orelse = orelse

    @property
    def blockstart_tolineno(self):
        return self.test.tolineno

    def block_range(self, lineno):
        """handle block line numbers range for for and while statements"""
        return self._elsed_block_range(lineno, self.orelse)


class With(base.BlockRangeMixIn, Statement):

    _astroid_fields = ('items', 'body')

    def __init__(self, lineno=None, col_offset=None, parent=None):
        self.items = []
        self.body = []
        super(With, self).__init__(lineno, col_offset, parent)

    def postinit(self, items=base.Empty, body=base.Empty):
        self.items = items
        self.body = body

    @property
    def blockstart_tolineno(self):
        return self.items[-1].context_expr.tolineno


class WithItem(base.BaseNode):
    _astroid_fields = ('context_expr', 'optional_vars')
    context_expr = base.Empty
    optional_vars = base.Empty

    def postinit(self, context_expr=base.Empty, optional_vars=base.Empty):
        self.context_expr = context_expr
        self.optional_vars = optional_vars


class AsyncWith(With):
    """Asynchronous `with` built with the `async` keyword."""


class Yield(base.BaseNode):

    _astroid_fields = ('value',)
    value = base.Empty

    def postinit(self, value=base.Empty):
        self.value = value


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

    def postinit(self, body=()):
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


class ComprehensionScope(base.BaseNode):

    def frame(self):
        return self.parent.frame()


class GeneratorExp(ComprehensionScope):
    _astroid_fields = ('elt', 'generators')
    elt = base.Empty
    generators = base.Empty

    def __init__(self, lineno=None, col_offset=None, parent=None):
        super(GeneratorExp, self).__init__(lineno, col_offset, parent)

    def postinit(self, elt=base.Empty, generators=base.Empty):
        self.elt = elt
        if generators is base.Empty:
            self.generators = []
        else:
            self.generators = generators


class DictComp(ComprehensionScope):
    _astroid_fields = ('key', 'value', 'generators')
    key = base.Empty
    value = base.Empty
    generators = base.Empty

    def __init__(self, lineno=None, col_offset=None, parent=None):
        super(DictComp, self).__init__(lineno, col_offset, parent)

    def postinit(self, key=base.Empty, value=base.Empty, generators=base.Empty):
        self.key = key
        self.value = value
        if generators is base.Empty:
            self.generators = []
        else:
            self.generators = generators


class SetComp(ComprehensionScope):
    _astroid_fields = ('elt', 'generators')
    elt = None
    generators = None
    elt = base.Empty
    generators = base.Empty

    def __init__(self, lineno=None, col_offset=None, parent=None):
        super(SetComp, self).__init__(lineno, col_offset, parent)

    def postinit(self, elt=base.Empty, generators=base.Empty):
        self.elt = elt
        if generators is base.Empty:
            self.generators = []
        else:
            self.generators = generators


class _ListComp(base.BaseNode):

    _astroid_fields = ('elt', 'generators')
    elt = base.Empty
    generators = base.Empty

    def postinit(self, elt=base.Empty, generators=base.Empty):
        self.elt = elt
        self.generators = generators


if six.PY3:
    class ListComp(_ListComp, ComprehensionScope):

        # _other_other_fields = ('locals',)

        def __init__(self, lineno=None, col_offset=None, parent=None):
            super(ListComp, self).__init__(lineno, col_offset, parent)
else:
    class ListComp(_ListComp):
        pass


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

    def __init__(self, lineno=None, col_offset=None, parent=None):
        self.args = []
        self.body = []
        super(Lambda, self).__init__(lineno, col_offset, parent)

    def postinit(self, args, body):
        self.args = args
        self.body = body


class FunctionDef(LambdaFunctionMixin, Statement):

    _astroid_fields = ('decorators', 'args', 'body', 'returns')
    _other_fields = ('name', 'doc')
    decorators = base.Empty

    def __init__(self, name=None, doc=None, lineno=None,
                 col_offset=None, parent=None):
        self.name = name
        self.doc = doc
        super(FunctionDef, self).__init__(lineno, col_offset, parent)

    def postinit(self, args, body, decorators=base.Empty, returns=base.Empty):
        self.args = args
        self.body = body
        self.decorators = decorators
        self.returns = returns

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
        yield_nodes = (Yield, YieldFrom)
        return next(self.nodes_of_class(yield_nodes,
                                        skip_klass=(FunctionDef, Lambda)), False)


class AsyncFunctionDef(FunctionDef):
    """Asynchronous function created with the `async` keyword."""


class ClassDef(Statement):

    _astroid_fields = ('decorators', 'bases', 'body', 'keywords')
    _other_fields = ('name', 'doc')
    decorators = base.Empty

    def __init__(self, name=None, doc=None, lineno=None,
                 col_offset=None, parent=None):
        self.bases = []
        self.body = []
        self.name = name
        self.doc = doc
        super(ClassDef, self).__init__(lineno, col_offset, parent)

    def postinit(self, bases, body=[], decorators=[], keywords=[]):
        self.bases = bases
        self.body = body
        self.decorators = decorators
        self.keywords = keywords

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
