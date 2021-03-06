# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/master/COPYING.LESSER

"""Implements logic for determing the scope of a node."""

import itertools

import six

from astroid import node_classes
from astroid import util


@util.singledispatch
def _scope_by_parent(parent, node):
    """Detect the scope of the *node* by parent's rules.

    The scope for certain kind of nodes depends on the
    parent, as it is the case for default values of arguments
    and function annotation, where the scope is not the scope of
    the parent, but the parent scope of the parent.
    """
    # This is separated in multiple dispatch methods on parents,
    # in order to decouple the implementation for the normal cases.


def _node_arguments(node):
    for arg in itertools.chain(node.positional_and_keyword, node.keyword_only,
                               (node.vararg, ), (node.kwarg, )):
        if arg and arg.annotation:
            yield arg


@_scope_by_parent.register(node_classes.Arguments)
def _scope_by_argument_parent(parent, node):
    args = parent
    for param in itertools.chain(args.positional_and_keyword, args.keyword_only):
        if param.default == node:
            return args.parent.parent.scope()

    if six.PY3 and node in _node_arguments(args):
        return args.parent.parent.scope()


@_scope_by_parent.register(node_classes.FunctionDef)
def _scope_by_function_parent(parent, node):
    # Verify if the node is the return annotation of a function,
    # in which case the scope is the parent scope of the function.
    if six.PY3 and node == parent.returns:
        return parent.parent.scope()


@_scope_by_parent.register(node_classes.Parameter)
def _scope_by_parameter_parent(parent, node):
    # Defaults and annotations are scoped outside the function.
    if node == parent.default:
        return parent.parent.parent.parent.scope()
    if node == parent.annotation:
        return parent.parent.parent.parent.scope()


@_scope_by_parent.register(node_classes.Comprehension)
def _scope_by_comprehension_parent(parent, node):
    # Get the scope of a node which has a comprehension
    # as a parent. The rules are a bit hairy, but in essence
    # it is simple enough: list comprehensions leaks variables
    # on Python 2, so they have the parent scope of the list comprehension
    # itself. The iter part of the comprehension has almost always
    # another scope than the comprehension itself, but only for the
    # first generator (the outer one). Other comprehensions don't leak
    # variables on Python 2 and 3.

    comprehension = parent_scope = parent.parent
    generators = comprehension.down()

    # The first outer generator always has a different scope
    first_iter = generators.down().down().right()
    if node == first_iter:
        return parent_scope.parent.scope()

    # This might not be correct for all the cases, but it
    # should be enough for most of them.
    if six.PY2 and isinstance(parent_scope, node_classes.ListComp):
        return parent_scope.parent.scope()
    return parent.scope()


@util.singledispatch
def node_scope(node):
    """Get the scope of the given node."""
    scope = _scope_by_parent(node.parent, node)
    return scope or node.parent.scope()


@node_scope.register(node_classes.Decorators)
def _decorators_scope(node):
    return node.parent.parent.scope()


@node_scope.register(node_classes.Module)
@node_scope.register(node_classes.GeneratorExp)
@node_scope.register(node_classes.DictComp)
@node_scope.register(node_classes.SetComp)
@node_scope.register(node_classes.Lambda)
@node_scope.register(node_classes.FunctionDef)
@node_scope.register(node_classes.ClassDef)
def _scoped_nodes(node):
    return node

if six.PY3:
    node_scope.register(node_classes.ListComp, _scoped_nodes)


@util.singledispatch
def assign_type(node):
    '''Get the assign type of the given node.

    The assign type is the node which introduces this node as name binding
    node. For instance, the assign type of the iteration step in a for loop
    is the for itself.
    '''
    return node


@assign_type.register(node_classes.DelName)
@assign_type.register(node_classes.AssignAttr)
@assign_type.register(node_classes.DelAttr)
@assign_type.register(node_classes.Starred)
@assign_type.register(node_classes.WithItem)
@assign_type.register(node_classes.AssignName)
@assign_type.register(node_classes.Parameter)
@assign_type.register(node_classes.List)
@assign_type.register(node_classes.Set)
@assign_type.register(node_classes.Tuple)
@assign_type.register(node_classes.Dict)
def _parent_assign_type(node):
    '''Get the assign type of the parent instead.'''
    return assign_type(node.parent)


def qname(node):
    """Return the 'qualified' name of the node."""
    if not isinstance(node, (node_classes.ClassDef,
                             node_classes.Module,
                             node_classes.LambdaFunctionMixin)):
        raise TypeError('This node has no qualified name.')
    if not node.parent:
        return node.name
    return '%s.%s' % (qname(node.parent.frame()), node.name)
