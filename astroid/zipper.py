# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/master/COPYING.LESSER
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
        result = collections.deque((linked_list[0], ))
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
Path = collections.namedtuple('Path',
                              'left right parent_nodes parent_path changed')


class Zipper(wrapt.ObjectProxy):
    '''This an object-oriented version of a zipper with methods instead of
    functions.  All the methods return a new zipper or None, or
    iterate over zippers, and none of them mutate the underlying AST
    nodes.  They return None when the method is not valid for that
    zipper.  The zipper acts as a proxy so the underlying node's or
    sequence's methods and attributes are accessible through it.

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
            path = self._self_path._replace(
                left=left,
                right=(self.__wrapped__, self._self_path.right))
            return type(self)(focus=focus, path=path)

    def leftmost(self):
        '''Go to the leftmost sibling of the focus.

        This takes time linear in the number of left siblings.
        '''
        if self._self_path and self._self_path.left:
            focus, siblings = _last(self._self_path.left), _initial(
                self._self_path.left)
            right = _concatenate(_reverse(siblings),
                                 (self.__wrapped__, self._self_path.right))
            path = self._self_path._replace(left=(), right=right)
            return type(self)(focus=focus, path=path)

    def right(self):
        '''Go to the next sibling that's directly to the right of the focus.

        This takes constant time.
        '''
        if self._self_path and self._self_path.right:
            focus, right = self._self_path.right
            path = self._self_path._replace(
                left=(self.__wrapped__, self._self_path.left),
                right=right)
            return type(self)(focus=focus, path=path)

    def rightmost(self):
        '''Go to the rightmost sibling of the focus.

        This takes time linear in the number of right siblings.
        '''
        if self._self_path and self._self_path.right:
            siblings, focus = _initial(self._self_path.right), _last(
                self._self_path.right)
            left = _concatenate(_reverse(siblings),
                                (self.__wrapped__, self._self_path.left))
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
                    focus_node = _concatenate(_reverse(left),
                                              (self.__wrapped__, right))
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
            self_ancestors = _reverse(
                (self.__wrapped__, self._self_path.parent_nodes))
        else:
            self_ancestors = (self.__wrapped__, ())
        if other._self_path:
            other_ancestors = _reverse(
                (other.__wrapped__, other._self_path.parent_nodes))
        else:
            other_ancestors = (other.__wrapped__, ())
        ancestor = None
        for self_ancestor, other_ancestor in zip(_iterate(self_ancestors),
                                                 _iterate(other_ancestors)):
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

    # Iterative algorithms for these two methods avoid the problem of
    # `yield from` only being available on Python 3 and ensure that no
    # AST will overflow the call stack.  On CPython, avoiding the
    # extra function calls necessary for a recursive algorithm will
    # probably make them faster too.
    def preorder_descendants(self, dont_recurse_on=None):
        '''Iterates over the descendants of the focus in prefix order.

        In addition to iterating over a tree without changing it,
        calling send() with a zipper as an argument will replace the
        node the generator just returned with the focus of the new
        zipper, and the iteration will continue from the replaced
        zipper.  For instance, given a starting zippered list of,

        foo = [Const(1), FunctionDef(f, ...), Const(2)]

        The following code will print Const(1), FunctionDef(f, ...),
        and Const(2), without recursing into the FunctionDef node, and
        going up() from the final node, Const(2), would return the list
        [Const(1), Const('f'), Const(2)].

        iterator = foo.preorder_descendants():
        node = next(iterator)
        while True:
            print(node)
            if isinstance(node, node_classes.FunctionDef):
                node = iterator.send(Const(node.name))
            else:
                node = next(iterator)

        Arguments:
            dont_recurse_on (Callable[base.BaseNode] -> bool): If this returns
                True for a node, this function will not iterate over that node
                or any of its descendants.
        '''

        # Start at the given node.
        location = Zipper(self.__wrapped__)
        while location is not None:
            if not callable(dont_recurse_on) or not dont_recurse_on(location):
                new_location = yield location
                if new_location is not None:
                    location = new_location
                # Move down if possible.  Yield that node.  Continue until
                # moving down is no longer possible.
                if location.down() is not None:
                    location = location.down()
                    continue
            # Move right if possible.  Yield that node.  Repeat as above,
            # going down if possible and yielding.
            if location._self_path and location._self_path.right:
                location = location.right()
            # Go up until it's possible to move right again, don't yield
            # any nodes (they've already been yielded).
            else:
                while location is not None:
                    location = location.up()
                    if (location is not None and location._self_path and
                        location._self_path.right):
                        location = location.right()
                        break

    def postorder_descendants(self, dont_recurse_on=None):
        '''Iterates over the descendants of the focus in postfix order.

        See preorder_descendants() for how to use send() to edit a
        zipper while traversing and arguments.

        '''
        location = Zipper(self.__wrapped__)
        # Start at the leftmost descendant of the given node.
        while (((isinstance(location, base.BaseNode) and
                 location._astroid_fields) or location) and
               (not callable(dont_recurse_on) or not dont_recurse_on(location))
               ):
            location = location.down()
        while location is not None:
            if not callable(dont_recurse_on) or not dont_recurse_on(location):
                new_location = yield location
                if new_location is not None:
                    location = new_location
            # It's not possible to move down, so move right, then try
            # to move down again.
            if location._self_path and location._self_path.right:
                location = location.right()
                # Move down until it's no longer possible to move down, then
                # yield that node.
                while (((isinstance(location, base.BaseNode) and
                         location._astroid_fields) or location) and
                       (not callable(dont_recurse_on) or
                        not dont_recurse_on(location))):
                    location = location.down()
            else:
                # Once it's no longer possible to move down or right, move up,
                # yield that node.
                location = location.up()

    # def postorder_next(self):
    #     if location.up() is None:
    #         return
    #     else:
    #         if location._self_path and location._self_path.right:
    #             if location.right().down():
    #                 location = location.right().down()
    #                 while ((isinstance(location, base.BaseNode) and location._astroid_fields) or location):
    #                     location = location.down()
    #                 return location
    #             else:
    #                 return location.right()
    #         else:
    #             return location.up()

    def find_descendants_of_type(self, cls, dont_recurse_on=()):
        '''Iterates over the descendants of the focus of a given type in
        prefix order.

        Arguments:
            skip_class (base.BaseNode, tuple(base.BaseNode)): If not None, will
                not include nodes of this type or types or any of the
                descendants of those nodes.
        '''
        return (d for d in self.preorder_descendants(
            lambda n: isinstance(n, dont_recurse_on)) if isinstance(d, cls))

    # Editing
    def replace(self, new_focus):
        '''Replaces the existing node at the focus.

        This takes constant time.

        Arguments:
            new_focus (base.BaseNode, collections.Sequence): The object to
                replace the focus with.
        '''
        if self._self_path:
            new_path = self._self_path._replace(changed=True)
        else:
            new_path = None
        return type(self)(focus=new_focus, path=new_path)

    def edit(self, *args, **kws):
        '''Creates a new node from the existing node at the focus.

        If the focus is a node, this calls recreate() on the existing
        node, passing it the variadic arguments.  If the focus is a
        sequence, it calls the sequence's constructor with the
        variadic arguments.  (For ordinary tuples and lists, passing
        keyword arguments to this method will raise an exception.)

        This takes constant time.

        Arguments:
            args (Tuple[Any]): Values to pass to recreate() or a sequence
                constructor.
            kws (Dict[str, Any]): The fields to replace in the new node using
                recreate().

        '''
        if self._self_path:
            new_path = self._self_path._replace(changed=True)
        else:
            new_path = None
        if isinstance(self.__wrapped__, base.BaseNode):
            new_focus = self.__wrapped__.recreate(*args, **kws)
        else:
            new_focus = self.__wrapped__.__class__(*args, **kws)
        return type(self)(focus=new_focus, path=new_path)

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

    def frame(self):
        '''Go to the first ancestor of the focus that creates a new frame.

        This takes time linear in the number of ancestors of the focus.
        '''
        location = self
        while (location is not None and
               not isinstance(location.__wrapped__,
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

    # Deprecated APIs
    def last_child(self):
        return self.rightmost()

    def next_sibling(self):
        return self.right()

    def previous_sibling(self):
        return self.left()

    def nodes_of_class(self, cls, skip_class=()):
        return self.find_descendants_of_type(cls, skip_class)
