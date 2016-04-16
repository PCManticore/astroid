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

import functools
import warnings
import sys

import six

from astroid import context as contextmod
from astroid import decorators
from astroid import exceptions
from astroid import inference
from astroid.interpreter import runtimeabc
from astroid.interpreter import objects
from astroid import manager
from astroid import protocols
from astroid.tree import base
from astroid.tree import treeabc
from astroid import util


@util.register_implementation(treeabc.Statement)
class Statement(base.NodeNG):
    """Statement node adding a few attributes"""
    is_statement = True

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



class BaseAssignName(base.LookupMixIn, base.ParentAssignTypeMixin,
                     AssignedStmtsMixin, base.NodeNG):
    _other_fields = ('name',)

    def __init__(self, name=None, lineno=None, col_offset=None, parent=None):
        self.name = name
        super(BaseAssignName, self).__init__(lineno, col_offset, parent)



class AssignName(BaseAssignName):
    """class representing an AssignName node"""


class Parameter(BaseAssignName):

    _astroid_fields = ('default', 'annotation')
    _other_fields = ('name', )

    def __init__(self, name=None, lineno=None, col_offset=None, parent=None):
        super(Parameter, self).__init__(name=name, lineno=lineno,
                                        col_offset=col_offset, parent=parent)

    def postinit(self, default, annotation):
        self.default = default
        self.annotation = annotation


class DelName(base.LookupMixIn, base.ParentAssignTypeMixin, base.NodeNG):
    """class representing a DelName node"""
    _other_fields = ('name',)

    def __init__(self, name=None, lineno=None, col_offset=None, parent=None):
        self.name = name
        super(DelName, self).__init__(lineno, col_offset, parent)


class Name(base.LookupMixIn, base.NodeNG):
    """class representing a Name node"""
    _other_fields = ('name',)

    def __init__(self, name=None, lineno=None, col_offset=None, parent=None):
        self.name = name
        super(Name, self).__init__(lineno, col_offset, parent)
    

class Arguments(base.AssignTypeMixin, AssignedStmtsMixin, base.NodeNG):
    """class representing an Arguments node"""

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

    @decorators.cachedproperty
    def fromlineno(self):
        # Let the Function's lineno be the lineno for this.
        if self.parent.fromlineno:
            return self.parent.fromlineno

        return super(Arguments, self).fromlineno

    def _format_args(args):
        values = []
        if not args:
            return ''
        for i, arg in enumerate(args):
            if isinstance(arg, Tuple):
                values.append('(%s)' % _format_args(arg.elts))
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
            result.append(_format_args(self.positional_and_keyword))
        if self.vararg:
            result.append('*%s' % _format_args((self.vararg, )))
        if self.keyword_only:
            if not self.vararg:
                result.append('*')
            result.append(_format_args(self.keyword_only))
        if self.kwarg:
            result.append('**%s' % _format_args((self.kwarg, )))
        return ', '.join(result)


    def _find_arg(argname, args, rec=False):
        for i, arg in enumerate(args):
            if isinstance(arg, Tuple):
                if rec:
                    found = _find_arg(argname, arg.elts)
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
            i = _find_arg(argname, place)[0]
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



class AssignAttr(base.ParentAssignTypeMixin,
                 AssignedStmtsMixin, base.NodeNG):
    """class representing an AssignAttr node"""
    _astroid_fields = ('expr',)
    _other_fields = ('attrname',)

    def __init__(self, attrname=None, lineno=None, col_offset=None, parent=None):
        self.attrname = attrname
        super(AssignAttr, self).__init__(lineno, col_offset, parent)

    def postinit(self, expr=None):
        self.expr = expr


class Assert(Statement):
    """class representing an Assert node"""
    _astroid_fields = ('test', 'fail',)

    def postinit(self, test=None, fail=None):
        self.fail = fail
        self.test = test


class Assign(base.AssignTypeMixin, AssignedStmtsMixin, Statement):
    """class representing an Assign node"""
    _astroid_fields = ('targets', 'value',)

    def postinit(self, targets=None, value=None):
        self.targets = targets
        self.value = value


class AugAssign(base.AssignTypeMixin, AssignedStmtsMixin, Statement):
    """class representing an AugAssign node"""
    _astroid_fields = ('target', 'value')
    _other_fields = ('op',)

    def __init__(self, op=None, lineno=None, col_offset=None, parent=None):
        self.op = op
        super(AugAssign, self).__init__(lineno, col_offset, parent)

    def postinit(self, target=None, value=None):
        self.target = target
        self.value = value


class Repr(base.NodeNG):
    """class representing a Repr node"""
    _astroid_fields = ('value',)

    def postinit(self, value=None):
        self.value = value


class BinOp(base.NodeNG):
    """class representing a BinOp node"""
    _astroid_fields = ('left', 'right')
    _other_fields = ('op',)
    left = None
    right = None

    def __init__(self, op=None, lineno=None, col_offset=None, parent=None):
        self.op = op
        super(BinOp, self).__init__(lineno, col_offset, parent)

    def postinit(self, left=None, right=None):
        self.left = left
        self.right = right


class BoolOp(base.NodeNG):
    """class representing a BoolOp node"""
    _astroid_fields = ('values',)
    _other_fields = ('op',)

    def __init__(self, op=None, lineno=None, col_offset=None, parent=None):
        self.op = op
        super(BoolOp, self).__init__(lineno, col_offset, parent)

    def postinit(self, values=None):
        self.values = values


class Break(Statement):
    """class representing a Break node"""


class Call(base.NodeNG):
    """class representing a Call node"""
    _astroid_fields = ('func', 'args', 'keywords')
    func = None
    args = None
    keywords = None

    def postinit(self, func=None, args=None, keywords=None):
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
        return [keyword for keyword in keywords if keyword.arg is None]


class Compare(base.NodeNG):
    """class representing a Compare node"""
    _astroid_fields = ('left', 'comparators')
    _other_fields = ('ops',)

    def __init__(self, ops, lineno=None, col_offset=None, parent=None):
        self.comparators = []
        self.ops = ops
        super(Compare, self).__init__(lineno, col_offset, parent)

    def postinit(self, left=None, comparators=None):
        self.left = left
        self.comparators = comparators

    def get_children(self):
        """override get_children for tuple fields"""
        yield self.left
        for comparator in self.comparators:
            yield comparator

    def last_child(self):
        """override last_child"""
        return self.comparators[-1]


class Comprehension(AssignedStmtsMixin, base.NodeNG):
    """class representing a Comprehension node"""
    _astroid_fields = ('target', 'iter', 'ifs')

    def __init__(self, parent=None):
        self.parent = parent

    def postinit(self, target=None, iter=None, ifs=None):
        self.target = target
        self.iter = iter
        self.ifs = ifs

   # TODO: check if we have assign_type for all other nodes that creates scope.
    def assign_type(self):
        return self


class Const(base.NodeNG, objects.BaseInstance):
    """represent a constant node like num, str, bytes"""
    _other_fields = ('value',)

    def __init__(self, value, lineno=None, col_offset=None, parent=None):
        self.value = value
        super(Const, self).__init__(lineno, col_offset, parent)

    
@util.register_implementation(treeabc.NameConstant)
class NameConstant(Const):
    """Represents a builtin singleton, at the moment True, False, None,
    and NotImplemented.

    """


# TODO: check if needed
class ReservedName(base.NodeNG):
    '''Used in the builtins AST to assign names to singletons.'''
    _astroid_fields = ('value',)
    _other_fields = ('name',)

    def __init__(self, name, lineno=None, col_offset=None, parent=None):
        self.name = name
        super(ReservedName, self).__init__(lineno, col_offset, parent)

    def postinit(self, value):
        self.value = value


class Continue(Statement):
    """class representing a Continue node"""


class Decorators(base.NodeNG):
    """class representing a Decorators node"""
    _astroid_fields = ('nodes',)

    def postinit(self, nodes):
        self.nodes = nodes


class DelAttr(base.ParentAssignTypeMixin, base.NodeNG):
    """class representing a DelAttr node"""
    _astroid_fields = ('expr',)
    _other_fields = ('attrname',)

    def __init__(self, attrname=None, lineno=None, col_offset=None, parent=None):
        self.attrname = attrname
        super(DelAttr, self).__init__(lineno, col_offset, parent)

    def postinit(self, expr=None):
        self.expr = expr


class Delete(base.AssignTypeMixin, Statement):
    """class representing a Delete node"""
    _astroid_fields = ('targets',)

    def postinit(self, targets=None):
        self.targets = targets


class Dict(base.NodeNG):
    """class representing a Dict node"""
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
    """class representing a Expr node"""
    _astroid_fields = ('value',)

    def postinit(self, value=None):
        self.value = value


class Ellipsis(base.NodeNG): # pylint: disable=redefined-builtin
    """class representing an Ellipsis node"""


class ExceptHandler(base.AssignTypeMixin, AssignedStmtsMixin, Statement):
    """class representing an ExceptHandler node"""
    _astroid_fields = ('type', 'name', 'body',)

    def postinit(self, type=None, name=None, body=None):
        self.type = type
        self.name = name
        self.body = body

    @decorators.cachedproperty
    def blockstart_tolineno(self):
        if self.name:
            return self.name.tolineno
        elif self.type:
            return self.type.tolineno
        else:
            return self.lineno

    def catch(self, exceptions):
        if self.type is None or exceptions is None:
            return True
        for node in self.type.nodes_of_class(Name):
            if node.name in exceptions:
                return True


class Exec(Statement):
    """class representing an Exec node"""
    _astroid_fields = ('expr', 'globals', 'locals')

    def postinit(self, expr=None, globals=None, locals=None):
        self.expr = expr
        self.globals = globals
        self.locals = locals


class ExtSlice(base.NodeNG):
    """class representing an ExtSlice node"""
    _astroid_fields = ('dims',)

    def postinit(self, dims=None):
        self.dims = dims


class For(base.BlockRangeMixIn, base.AssignTypeMixin,
          AssignedStmtsMixin, Statement):
    """class representing a For node"""
    _astroid_fields = ('target', 'iter', 'body', 'orelse',)

    def postinit(self, target=None, iter=None, body=None, orelse=None):
        self.target = target
        self.iter = iter
        self.body = body
        self.orelse = orelse

    optional_assign = True

    def blockstart_tolineno(self):
        return self.iter.tolineno


class AsyncFor(For):
    """Asynchronous For built with `async` keyword."""


class Await(base.NodeNG):
    """Await node for the `await` keyword."""

    _astroid_fields = ('value', )

    def postinit(self, value=None):
        self.value = value


class ImportFrom(base.FilterStmtsMixin, Statement):
    """class representing a ImportFrom node"""
    _other_fields = ('modname', 'names', 'level')

    def __init__(self, fromname, names, level=0, lineno=None,
                 col_offset=None, parent=None):
        self.modname = fromname
        self.names = names
        self.level = level
        super(ImportFrom, self).__init__(lineno, col_offset, parent)


class Attribute(base.NodeNG):
    """class representing a Attribute node"""
    _astroid_fields = ('expr',)
    _other_fields = ('attrname',)

    def __init__(self, attrname=None, lineno=None, col_offset=None, parent=None):
        self.attrname = attrname
        super(Attribute, self).__init__(lineno, col_offset, parent)

    def postinit(self, expr=None):
        self.expr = expr


class Global(Statement):
    """class representing a Global node"""
    _other_fields = ('names',)

    def __init__(self, names, lineno=None, col_offset=None, parent=None):
        self.names = names
        super(Global, self).__init__(lineno, col_offset, parent)


class If(base.BlockRangeMixIn, Statement):
    """class representing an If node"""
    _astroid_fields = ('test', 'body', 'orelse')
    test = None
    body = None
    orelse = None

    def postinit(self, test=None, body=None, orelse=None):
        self.test = test
        self.body = body
        self.orelse = orelse

    @decorators.cachedproperty
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


@util.register_implementation(treeabc.IfExp)
class IfExp(base.NodeNG):
    """class representing an IfExp node"""
    _astroid_fields = ('test', 'body', 'orelse')

    def postinit(self, test=None, body=None, orelse=None):
        self.test = test
        self.body = body
        self.orelse = orelse


@util.register_implementation(treeabc.Import)
class Import(base.FilterStmtsMixin, Statement):
    """class representing an Import node"""
    _other_fields = ('names',)

    def __init__(self, names=None, lineno=None, col_offset=None, parent=None):
        self.names = names
        super(Import, self).__init__(lineno, col_offset, parent)


@util.register_implementation(treeabc.Index)
class Index(base.NodeNG):
    """class representing an Index node"""
    _astroid_fields = ('value',)

    def postinit(self, value=None):
        self.value = value


@util.register_implementation(treeabc.Keyword)
class Keyword(base.NodeNG):
    """class representing a Keyword node"""
    _astroid_fields = ('value',)
    _other_fields = ('arg',)

    def __init__(self, arg=None, lineno=None, col_offset=None, parent=None):
        self.arg = arg
        super(Keyword, self).__init__(lineno, col_offset, parent)

    def postinit(self, value=None):
        self.value = value


class List(base.BaseContainer, AssignedStmtsMixin, objects.BaseInstance):
    """class representing a List node"""
    _other_fields = ('ctx',)

    def __init__(self, ctx=None, lineno=None,
                 col_offset=None, parent=None):
        self.ctx = ctx
        super(List, self).__init__(lineno, col_offset, parent)


class Nonlocal(Statement):
    """class representing a Nonlocal node"""
    _other_fields = ('names',)

    def __init__(self, names, lineno=None, col_offset=None, parent=None):
        self.names = names
        super(Nonlocal, self).__init__(lineno, col_offset, parent)


class Pass(Statement):
    """class representing a Pass node"""


class Print(Statement):
    """class representing a Print node"""
    _astroid_fields = ('dest', 'values',)

    def __init__(self, nl=None, lineno=None, col_offset=None, parent=None):
        self.nl = nl
        super(Print, self).__init__(lineno, col_offset, parent)

    def postinit(self, dest=None, values=None):
        self.dest = dest
        self.values = values


class Raise(Statement):
    """class representing a Raise node"""
    # TODO: should look the same for both Python 2 and 3
    if six.PY2:
        _astroid_fields = ('exc', 'inst', 'tback')
        inst = None
        tback = None

        def postinit(self, exc=None, inst=None, tback=None):
            self.exc = exc
            self.inst = inst
            self.tback = tback
    else:
        _astroid_fields = ('exc', 'cause')

        def postinit(self, exc=None, cause=None):
            self.exc = exc
            self.cause = cause

    def raises_not_implemented(self):
        if not self.exc:
            return
        for name in self.exc.nodes_of_class(Name):
            if name.name == 'NotImplementedError':
                return True


class Return(Statement):
    """class representing a Return node"""
    _astroid_fields = ('value',)

    def postinit(self, value=None):
        self.value = value


# TODO: check BaseCOntainer
class Set(base.BaseContainer, objects.BaseInstance):
    """class representing a Set node"""
    

class Slice(base.NodeNG):
    """class representing a Slice node"""
    _astroid_fields = ('lower', 'upper', 'step')

    def postinit(self, lower=None, upper=None, step=None):
        self.lower = lower
        self.upper = upper
        self.step = step


class Starred(base.ParentAssignTypeMixin, AssignedStmtsMixin, base.NodeNG):
    """class representing a Starred node"""
    _astroid_fields = ('value',)
    _other_fields = ('ctx', )

    def __init__(self, ctx=None, lineno=None, col_offset=None, parent=None):
        self.ctx = ctx
        super(Starred, self).__init__(lineno=lineno,
                                      col_offset=col_offset, parent=parent)

    def postinit(self, value=None):
        self.value = value


class Subscript(base.NodeNG):
    """class representing a Subscript node"""
    _astroid_fields = ('value', 'slice')
    _other_fields = ('ctx', )

    def __init__(self, ctx=None, lineno=None, col_offset=None, parent=None):
        self.ctx = ctx
        super(Subscript, self).__init__(lineno=lineno,
                                        col_offset=col_offset, parent=parent)

    def postinit(self, value=None, slice=None):
        self.value = value
        self.slice = slice


class TryExcept(base.BlockRangeMixIn, Statement):
    """class representing a TryExcept node"""
    _astroid_fields = ('body', 'handlers', 'orelse',)
    body = None
    handlers = None
    orelse = None

    def postinit(self, body=None, handlers=None, orelse=None):
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


@util.register_implementation(treeabc.TryFinally)
class TryFinally(base.BlockRangeMixIn, Statement):
    """class representing a TryFinally node"""
    _astroid_fields = ('body', 'finalbody',)
    body = None
    finalbody = None

    def postinit(self, body=None, finalbody=None):
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


class Tuple(base.BaseContainer, AssignedStmtsMixin, objects.BaseInstance):
    """class representing a Tuple node"""

    _other_fields = ('ctx',)

    def __init__(self, ctx=None, lineno=None,
                 col_offset=None, parent=None):
        self.ctx = ctx
        super(Tuple, self).__init__(lineno, col_offset, parent)


class UnaryOp(base.NodeNG):
    """class representing an UnaryOp node"""
    _astroid_fields = ('operand',)
    _other_fields = ('op',)

    def __init__(self, op=None, lineno=None, col_offset=None, parent=None):
        self.op = op
        super(UnaryOp, self).__init__(lineno, col_offset, parent)

    def postinit(self, operand=None):
        self.operand = operand


class While(base.BlockRangeMixIn, Statement):
    """class representing a While node"""
    _astroid_fields = ('test', 'body', 'orelse',)
    test = None
    body = None
    orelse = None

    def postinit(self, test=None, body=None, orelse=None):
        self.test = test
        self.body = body
        self.orelse = orelse

    @decorators.cachedproperty
    def blockstart_tolineno(self):
        return self.test.tolineno

    def block_range(self, lineno):
        """handle block line numbers range for for and while statements"""
        return self._elsed_block_range(lineno, self.orelse)


class With(base.BlockRangeMixIn, base.AssignTypeMixin,
           AssignedStmtsMixin, Statement):
    """class representing a With node"""
    _astroid_fields = ('items', 'body')

    def __init__(self, lineno=None, col_offset=None, parent=None):
        self.items = []
        self.body = []
        super(With, self).__init__(lineno, col_offset, parent)

    def postinit(self, items=None, body=None):
        self.items = items
        self.body = body

    @decorators.cachedproperty
    def blockstart_tolineno(self):
        return self.items[-1].context_expr.tolineno


class WithItem(base.ParentAssignTypeMixin, AssignedStmtsMixin, base.NodeNG):
    _astroid_fields = ('context_expr', 'optional_vars')

    def postinit(self, context_expr=None, optional_vars=None):
        self.context_expr = context_expr
        self.optional_vars = optional_vars


class AsyncWith(With):
    """Asynchronous `with` built with the `async` keyword."""


class Yield(base.NodeNG):
    """class representing a Yield node"""
    _astroid_fields = ('value',)

    def postinit(self, value=None):
        self.value = value


class YieldFrom(Yield):
    """ Class representing a YieldFrom node. """


class DictUnpack(base.NodeNG):
    """Represents the unpacking of dicts into dicts using PEP 448."""


@object.__new__
class Empty(base.NodeNG):
    """Empty nodes represents the lack of something

    For instance, they can be used to represent missing annotations
    or defaults for arguments or anything where None is a valid
    value.
    """

    def __bool__(self):
        return False

    __nonzero__ = __bool__


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
