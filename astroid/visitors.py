import abc
import collections
import inspect

import six

from astroid import base
from astroid import node_classes
from astroid import util


@six.add_metaclass(abc.ABCMeta)
class AbstractVisitor(object):
    '''The abstract base class for all visitors.'''

    @abc.abstractmethod
    def __init__(self):
        '''Abstract init method that sets up singledispatch for visit().'''
        # This is the implementation for object, which always raises
        # an error since no visitor operates over all types.
        def inappropriate_type(instance):
            raise TypeError('Inappropriate type %s for visitor %s.' %
                            (instance.__class__, self.__class__))
        self.visit = util.singledispatch(inappropriate_type)

    @abc.abstractmethod
    def visit_base(self, instance):
        '''Abstract visit method that should be overridden in subclasses.'''
        raise NotImplementedError


class AstroidVisitor(AbstractVisitor):
    '''An abstract visitor for astroid ASTs.'''
    NODE_TYPES = {name.lower(): node for name, node in
                  inspect.getmembers(node_classes, inspect.isclass) if not
                  name.startswith('_')}

    def __init__(self):
        super(AstroidVisitor, self).__init__()
        self.visit.register(base.BaseNode, self.visit_base)
        self.visit.register(collections.Sequence, self.visit_sequence)
        for name, method in inspect.getmembers(self, inspect.ismethod):
            if name.startswith('visit_') and not (name == 'visit_sequence' or name == 'visit_base'):
                try:
                    self.visit.register(self.NODE_TYPES[name[6:]], method)
                except KeyError:
                    raise ValueError('No node type corresponding to %s exists.'
                                     % method)

    @abc.abstractmethod
    def visit_sequence(self, focus):
        '''Abstract visit method for sequences in an astroid AST.'''
        raise NotImplementedError


class TransformVisitor(AstroidVisitor):

    def visit_base(self, focus):
        fields = {f: self.visit(c) for f, c in
                  zip(focus._astroid_fields, focus.children())}
        return focus.edit(**fields)

    def visit_sequence(self, focus):
        return focus.replace(focus.__class__(self.visit(child) for
                                             child in focus.children()))
