# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/master/COPYING.LESSER


import abc
import pprint

import six

from astroid import as_string
from astroid import exceptions
from astroid import util


# The maximum number of characters to print for a field in a string
# representation of a node.
FIELD_CHARACTERS_LIMIT = 160

class BaseNode(object):
    """Base Class for all Astroid node classes.

    It represents a node of the new abstract syntax tree.
    """
    is_statement = False
    optional_assign = False # True for For (and for Comprehension if py <3.0)
    is_function = False # True for FunctionDef nodes
    # attributes below are set by the builder module or by raw factories
    lineno = None
    col_offset = None
    # parent node in the tree
    parent = None
    # attributes containing child node(s) redefined in most concrete classes:
    _astroid_fields = ()
    # attributes containing non-nodes:
    _other_fields = ()
    # attributes containing AST-dependent fields:
    _other_other_fields = ()
    # instance specific inference function infer(node, context)
    _explicit_inference = None

    def __init__(self, lineno=None, col_offset=None):
        self.lineno = lineno
        self.col_offset = col_offset
 
    def __iter__(self):
        for field in self._astroid_fields:
            yield getattr(self, field)

    def __eq__(self, other):
        if self.__class__ is other.__class__:
            return (all(getattr(self, f) == getattr(other, f)
                       for f in self._astroid_fields) and
                    all(getattr(self, f) == getattr(other, f)
                        for f in self._other_fields))
        else:
            return False

    def __ne__(self, other):
        return not self == other

    # Must be defined to retain object.__hash__, see
    # https://docs.python.org/3/reference/datamodel.html#object.__hash__
    __hash__ = object.__hash__

    def _repr_name(self):
        """return self.name or self.attrname or '' for nice representation"""
        return getattr(self, 'name', getattr(self, 'attrname', ''))

    def __str__(self):
        rname = self._repr_name()
        cname = self.__class__.__name__
        if rname:
            string = '%(cname)s.%(rname)s(%(fields)s)'
            alignment = len(cname) + len(rname) + 2
        else:
            string = '%(cname)s(%(fields)s)'
            alignment = len(cname) + 1
        result = []
        for field in self._other_fields + self._astroid_fields:
            value = getattr(self, field)
            width = 80 - len(field) - alignment
            lines = pprint.pformat(value, indent=2,
                                   width=width).splitlines(True)

            # Some fields, notably source_code for Module nodes, are
            # too long to display comfortably, so this limits them.
            if len(lines[0]) > FIELD_CHARACTERS_LIMIT:
                lines[0] = lines[0][:160] + '...'
            inner = [lines[0]]
            for line in lines[1:]:
                inner.append(' ' * alignment + line)
            result.append('%s=%s' % (field, ''.join(inner)))

        return string % {'cname': cname,
                         'rname': rname,
                         'fields': (',\n' + ' ' * alignment).join(result)}

    def __repr__(self):
        rname = self._repr_name()
        if rname:
            string = '<%(cname)s.%(rname)s l.%(lineno)s at 0x%(id)x>'
        else:
            string = '<%(cname)s l.%(lineno)s at 0x%(id)x>'
        return string % {'cname': self.__class__.__name__,
                         'rname': rname,
                         'lineno': self.fromlineno,
                         'id': id(self)}

    def accept(self, visitor):
        func = getattr(visitor, "visit_" + self.__class__.__name__.lower())
        return func(self)

    @property
    def fromlineno(self):
        return self.lineno

    @property
    def tolineno(self):
        last_child = self
        while last_child:
            for child in reversed(tuple(last_child)):
                if child:
                    last_child = child
                    break
            else:
                break
        return last_child.lineno

    def block_range(self, lineno):
        """handle block line numbers range for non block opening statements
        """
        return lineno, self.tolineno

    def as_string(self):
        return as_string.to_code(self)

    def repr_tree(self, ids=False, include_linenos=False,
                  ast_state=False, indent='   ', max_depth=0, max_width=80):
        """Returns a string representation of the AST from this node.

        Args:
            ids (bool): If true, includes the ids with the node type names.
            include_linenos (bool): If true, includes the line numbers and
                column offsets.
            ast_state (bool): If true, includes information derived from
                the whole AST like local and global variables.
            indent (str): A string to use to indent the output string.
            max_depth (int): If set to a positive integer, won't return
                nodes deeper than max_depth in the string.
            max_width (int): Only positive integer values are valid, the
                default is 80.  Attempts to format the output string to stay
                within max_width characters, but can exceed it under some
                circumstances.
        """
        @util.singledispatch
        def _repr_tree(node, result, done, cur_indent='', depth=1):
            """Outputs a representation of a non-tuple/list, non-node that's
            contained within an AST, including strings.
            """
            lines = pprint.pformat(node,
                                   width=max(max_width - len(cur_indent),
                                             1)).splitlines(True)
            result.append(lines[0])
            result.extend([cur_indent + line for line in lines[1:]])
            return len(lines) != 1

        # pylint: disable=unused-variable; doesn't understand singledispatch
        @_repr_tree.register(tuple)
        @_repr_tree.register(list)
        def _repr_seq(node, result, done, cur_indent='', depth=1):
            """Outputs a representation of a sequence that's contained within an AST."""
            cur_indent += indent
            result.append('[')
            if len(node) == 0:
                broken = False
            elif len(node) == 1:
                broken = _repr_tree(node[0], result, done, cur_indent, depth)
            elif len(node) == 2:
                broken = _repr_tree(node[0], result, done, cur_indent, depth)
                if not broken:
                    result.append(', ')
                else:
                    result.append(',\n')
                    result.append(cur_indent)
                broken = (_repr_tree(node[1], result, done, cur_indent, depth)
                          or broken)
            else:
                result.append('\n')
                result.append(cur_indent)
                for child in node[:-1]:
                    _repr_tree(child, result, done, cur_indent, depth)
                    result.append(',\n')
                    result.append(cur_indent)
                _repr_tree(node[-1], result, done, cur_indent, depth)
                broken = True
            result.append(']')
            return broken
        
        # pylint: disable=unused-variable; doesn't understand singledispatch
        @_repr_tree.register(BaseNode)
        def _repr_node(node, result, done, cur_indent='', depth=1):
            """Outputs a strings representation of an astroid node."""
            if node in done:
                result.append('<Recursion on %s with id=%s>' %
                              (node.__class__.__name__, id(node)))
                return False
            else:
                done.add(node)
            if max_depth and depth > max_depth:
                result.append('...')
                return False
            depth += 1
            cur_indent += indent
            if ids:
                result.append('%s<0x%x>(\n' %
                              (node.__class__.__name__, id(node)))
            else:
                result.append('%s(' % node.__class__.__name__)
            fields = []
            if include_linenos:
                fields.extend(('lineno', 'col_offset'))
            fields.extend(node._other_fields)
            fields.extend(node._astroid_fields)
            if ast_state:
                fields.extend(node._other_other_fields)
            if len(fields) == 0:
                broken = False
            elif len(fields) == 1:
                result.append('%s=' % fields[0])
                broken = _repr_tree(getattr(node, fields[0]), result, done,
                                    cur_indent, depth)
            else:
                result.append('\n')
                result.append(cur_indent)
                for field in fields[:-1]:
                    result.append('%s=' % field)
                    _repr_tree(getattr(node, field), result, done, cur_indent,
                               depth)
                    result.append(',\n')
                    result.append(cur_indent)
                result.append('%s=' % fields[-1])
                _repr_tree(getattr(node, fields[-1]), result, done, cur_indent,
                           depth)
                broken = True
            result.append(')')
            return broken

        # pylint: disable=unused-variable; doesn't understand singledispatch
        @_repr_tree.register(type(Empty))
        def _repr_empty(node, result, done, cur_indent='', depth=1):
            result.append('Empty')
            return False

        result = []
        _repr_tree(self, result, set())
        return ''.join(result)

    def print_tree(self, *args, **kws):
        """Shortcut method to print the result of repr_tree()."""
        print(self.repr_tree(*args, **kws))


class BlockRangeMixIn(object):
    """override block range """

    @property
    def blockstart_tolineno(self):
        return self.lineno

    def _elsed_block_range(self, lineno, orelse, last=None):
        """handle block line numbers range for try/finally, for, if and while
        statements
        """
        if lineno == self.fromlineno:
            return lineno, lineno
        if orelse:
            if lineno >= orelse[0].fromlineno:
                return lineno, orelse[-1].tolineno
            return lineno, orelse[0].fromlineno - 1
        return lineno, last or self.tolineno


@object.__new__
class Empty(BaseNode):
    """Empty nodes represents the lack of something

    For instance, they can be used to represent missing annotations
    or defaults for arguments or anything where None is a valid
    value.
    """

    def __bool__(self):
        return False

    __nonzero__ = __bool__
