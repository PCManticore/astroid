'''This contains an implementation of a zipper for astroid ASTs.

A zipper is a data structure for traversing and editing immutable
recursive data types that can act as a doubly-linked structure without
actual double links.
http://blog.ezyang.com/2010/04/you-could-have-invented-zippers/ has a
brief introduction to zippers as a whole.  This implementation is
based on the Clojure implementation,
https://github.com/clojure/clojure/blob/master/src/clj/clojure/zip.clj .

'''
import collections

import wrapt

from astroid import scope
from astroid import base
from astroid import node_classes


# The following are helper functions for working with singly-linked
# lists made with two-tuples.  The empty tuple is used to denote the
# end of a linked list.  The zipper needs singly-linked lists for most
# of its operations to take constant time.
def _linked_list(*values):
    '''Builds a new linked list of tuples out of its arguments.'''
    tail = ()
    for value in reversed(values):
        tail = (value, tail)
    return tail


def _reverse(linked_list):
    '''Reverses an existing linked list of tuples.'''
    if linked_list:
        result = collections.deque((linked_list[0],))
        tail = linked_list[1]
        while tail:
            result.appendleft(tail[0])
            tail = tail[1]
        tail = (result.pop(), ())
        while result:
            tail = (result.pop(), tail)
        return tail


def _iterate(linked_list):
    '''Return an iterator over a linked list of tuples.'''
    node = linked_list
    while node:
        yield node[0]
        node = node[1]


def _concatenate(left, right):
    '''Concatenate the first linked lists of tuples onto the second.'''
    if not left:
        return right
    elif not right:
        return left
    else:
        result = [left[0]]
        tail = left[1]
        while tail:
            result.append(tail[0])
            tail = tail[1]
        tail = (result.pop(), right)
        while result:
            tail = (result.pop(), tail)
        return tail


def _last(linked_list):
    '''Returns the last element of a linked list of tuples.'''
    node = linked_list
    while node[1]:
        node = node[1]
    return node[0]


def _initial(linked_list):
    '''Returns a linked list of tuples containing all elements but the last.'''
    result = [linked_list[0]]
    tail = linked_list[1]
    while tail:
        result.append(tail[0])
        tail = tail[1]
    result.pop()
    while result:
        tail = (result.pop(), tail)
    return tail


# Attributes:
#     left (linked list): The siblings to the left of the zipper's focus.
#     right (linked list): The siblings to the right of the zipper's focus.
#     parent_nodes (linked list): The ancestors of the zipper's focus
#     parent_path (Path): The Path from the zipper that created this zipper.
#     changed (bool): Whether this zipper has been edited or not.
Path = collections.namedtuple('Path', 'left right parent_nodes parent_path changed')


class Zipper(wrapt.ObjectProxy):
    '''This an object-oriented version of a zipper with methods instead of
    functions.  All the methods return a new zipper or None, and none
    of them mutate the underlying AST nodes.  They return None when
    the method is not valid for that zipper.  The zipper acts as a
    proxy so the underlying node's or sequence's methods and
    attributes are accessible through it.

    Attributes:
        __wrapped__ (base.BaseNode, collections.Sequence): The AST node or
            sequence at the zipper's focus.
        _self_path (Path): The Path tuple containing information about the
            zipper's history.  This must be accessed as ._self_path.

    '''

    __slots__ = ('path')

    # Setting wrapt.ObjectProxy.__init__ as a default value turns it
    # into a local variable, avoiding a super() call, two globals
    # lookups, and two dict lookups (on wrapt's and ObjectProxy's
    # dicts) in the most common zipper operation on CPython.
    def __init__(self, focus, path=None, _init=wrapt.ObjectProxy.__init__):
        '''Make a new zipper.

        Arguments:
            focus (base.BaseNode, collections.Sequence): The focus for this
                zipper, will be assigned to self.__wrapped__ by
                wrapt.ObjectProxy's __init__.
            path: The path of the zipper used to create the new zipper, if any.

        Returns:
            A new zipper object.
        '''
        _init(self, focus)
        self._self_path = path


    # Traversal
    def left(self):
        '''Go to the next sibling that's directly to the left of the focus.

        This takes constant time.
        '''
        if self._self_path and self._self_path.left:
            focus, left = self._self_path.left
            path = self._self_path._replace(left=left,
                                            right=(self.__wrapped__,
                                                   self._self_path.right))
            return type(self)(focus=focus, path=path)

    def leftmost(self):
        '''Go to the leftmost sibling of the focus.

        This takes time linear in the number of left siblings.
        '''
        if self._self_path and self._self_path.left:
            focus, siblings = _last(self._self_path.left), _initial(self._self_path.left)
            right = _concatenate(_reverse(siblings), (self.__wrapped__, self._self_path.right))
            path = self._self_path._replace(left=(), right=right)
            return type(self)(focus=focus, path=path)

    def right(self):
        '''Go to the next sibling that's directly to the right of the focus.

        This takes constant time.
        '''
        if self._self_path and self._self_path.right:
            focus, right = self._self_path.right
            path = self._self_path._replace(left=(self.__wrapped__,
                                                  self._self_path.left),
                                            right=right)
            return type(self)(focus=focus, path=path)

    def rightmost(self):
        '''Go to the rightmost sibling of the focus.

        This takes time linear in the number of right siblings.
        '''
        if self._self_path and self._self_path.right:
            siblings, focus = _initial(self._self_path.right), _last(self._self_path.right)
            left = _concatenate(_reverse(siblings), (self.__wrapped__, self._self_path.left))
            path = self._self_path._replace(left=left, right=())
            return type(self)(focus=focus, path=path)

    def down(self):
        '''Go to the leftmost child of the focus.

        This takes constant time.
        '''
        try:
            children = iter(self.__wrapped__)
            first = next(children)
        except StopIteration:
            return
        if self._self_path:
            parent_nodes = (self.__wrapped__, self._self_path.parent_nodes)
        else:
            parent_nodes = (self.__wrapped__, ())
        path = Path(left=(),
                    right=_linked_list(*children),
                    parent_nodes=parent_nodes,
                    parent_path=self._self_path,
                    changed=False)
        return type(self)(focus=first, path=path)

    def up(self):
        '''Go to the parent of the focus.

        This takes time linear in the number of left siblings if the
        focus has been edited or constant time if it hasn't been
        edited.
        '''
        if self._self_path:
            left, right, parent_nodes, parent_path, changed = self._self_path
            if parent_nodes:
                focus = parent_nodes[0]
                # This conditional uses parent_nodes to make going up
                # take constant time if the focus hasn't been edited.
                if changed:
                    focus_node = _concatenate(_reverse(left), (self.__wrapped__, right))
                    return type(self)(
                        focus=focus.make_node(focus_node),
                        path=parent_path and parent_path._replace(changed=True))
                else:
                    return type(self)(focus=focus, path=parent_path)

    def root(self):
        '''Go to the root of the AST for the focus.

        This takes time linear in the number of ancestors of the focus.
        '''
        location = self
        while location._self_path:
            location = location.up()
        return location

    def common_ancestor(self, other):
        '''Find the most recent common ancestor of two different zippers.

        This takes time linear in the number of ancestors of both foci
        and will return None for zippers from two different ASTs.  The
        new zipper is derived from the zipper the method is called on,
        so edits in the second argument will not be included in the
        new zipper.

        '''
        if self._self_path:
            self_ancestors = _reverse((self.__wrapped__, self._self_path.parent_nodes))
        else:
            self_ancestors = (self.__wrapped__, ())
        if other._self_path:
            other_ancestors = _reverse((other.__wrapped__, other._self_path.parent_nodes))
        else:
            other_ancestors = (other.__wrapped__, ())
        ancestor = None
        for self_ancestor, other_ancestor in zip(_iterate(self_ancestors), _iterate(other_ancestors)):
            # This is a kludge to work around the problem of two Empty
            # nodes in different parts of an AST.  Empty nodes can
            # never be ancestors, so they can be safely skipped.
            if self_ancestor is other_ancestor and self_ancestor is not base.Empty:
                ancestor = self_ancestor
            else:
                break
        if ancestor is None:
            return None
        else:
            location = self
            while location.__wrapped__ is not ancestor:
                location = location.up()
        return location

    def children(self):
        '''Iterates over the children of the focus.'''
        child = self.down()
        while child is not None:
            yield child
            child = child.right()

    # Iterative algorithms for these two methods, with explicit
    # stacks, avoid the problem of yield from only being available on
    # Python 3 and ensure that no AST will overflow the call stack.
    # On CPython, avoiding the extra function calls necessary for a
    # recursive algorithm will probably make them faster too.
    def preorder_descendants(self, dont_recurse_on=None):
        '''Iterates over the descendants of the focus in prefix order.

        Arguments:
            dont_recurse_on (base.BaseNode): If not None, will not include nodes
                of this type or types or any of the descendants of those nodes.
        '''
        to_visit = [self]
        while to_visit:
            location = to_visit.pop()
            yield location
            if dont_recurse_on is None:
                to_visit.extend(c for c in
                                reversed(tuple(location.children())))
            else:
                to_visit.extend(c for c in
                                reversed(tuple(location.children()))
                                if not isinstance(c, dont_recurse_on))

    def postorder_descendants(self, dont_recurse_on=None):
        '''Iterates over the descendants of the focus in postfix order.

        Arguments:
            dont_recurse_on (base.BaseNode): If not None, will not include nodes
                of this type or types or any of the descendants of those nodes.
        '''
        to_visit = [self]
        visited_ancestors = []
        while to_visit:
            location = to_visit[-1]
            if not visited_ancestors or visited_ancestors[-1] is not location:
                visited_ancestors.append(location)
                if dont_recurse_on is None:
                    to_visit.extend(c for c in
                                    reversed(tuple(location.children())))
                else:
                    to_visit.extend(c for c in
                                    reversed(tuple(location.children()))
                                    if not isinstance(c, dont_recurse_on))
                continue
            visited_ancestors.pop()
            yield location
            to_visit.pop()

    def find_descendants_of_type(self, cls, skip_class=None):
        '''Iterates over the descendants of the focus of a given type in
        prefix order.

        Arguments:
            skip_class (base.BaseNode, tuple(base.BaseNode)): If not None, will
                not include nodes of this type or types or any of the
                descendants of those nodes.
        '''
        return (d for d in self.preorder_descendants(skip_class) if isinstance(d, cls))

    # Editing
    def replace(self, focus):
        '''Replaces the existing node at the focus.

        Arguments:
            focus (base.BaseNode, collections.Sequence): The object to replace
                the focus with.
        '''
        return type(self)(focus=focus, path=self._self_path._replace(changed=True))

    # def edit(self, *args, **kws):
    #     return type(self)(focus=self.__wrapped__.make_focus(*args, **kws),
    #                       path=self._self_path._replace(changed=True))

    # Legacy APIs
    @property
    def parent(self):
        '''Goes up to the next ancestor of the focus that's a node, not a sequence.'''
        location = self.up()
        if isinstance(location, collections.Sequence):
            return location.up()
        else:
            return location

    def get_children(self):
        '''Iterates over nodes that are children or grandchildren, no sequences.'''
        child = self.down()
        while child is not None:
            if isinstance(child, collections.Sequence):
                grandchild = child.down()
                for _ in range(len(child)):
                    yield grandchild
                    grandchild = grandchild.right()
            else:
                yield child
            child = child.right()

    def last_child(self):
        return self.rightmost()

    def next_sibling(self):
        return self.right()

    def previous_sibling(self):
        return self.left()

    def nodes_of_class(self, cls, skip_class=None):
        return self.find_descendants_of_type(cls, skip_class)

    def frame(self):
        '''Go to the first ancestor of the focus that creates a new frame.

        This takes time linear in the number of ancestors of the focus.
        '''
        location = self
        while (location is not None and not
               isinstance(location.__wrapped__,
                          (node_classes.FunctionDef, node_classes.Lambda,
                           node_classes.ClassDef, node_classes.Module))):
            location = location.up()
        return location

    def scope(self):
        """Get the first node defining a new scope

        Scopes are introduced in Python 3 by Module, FunctionDef,
        ClassDef, Lambda, GeneratorExp, and comprehension nodes.  On
        Python 2, the same is true except that list comprehensions
        don't generate a new scope.
        """
        return scope.node_scope(self)

    def statement(self):
        '''Go to the first ancestor of the focus that's a Statement.

        This takes time linear in the number of ancestors of the focus.
        '''
        location = self
        while (location is not None and
               not isinstance(location.__wrapped__,
                              (node_classes.Module, node_classes.Statement))):
            location = location.up()
        return location
