# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/master/COPYING.LESSER

#
# The code in this file was originally part of logilab-common, licensed under
# the same license.

import importlib
import sys
import warnings

import six
import wrapt

try:
    from functools import singledispatch
except ImportError:
    from singledispatch import singledispatch


def reraise(exception):
    '''Reraises an exception with the traceback from the current exception
    block.'''
    six.reraise(type(exception), exception, sys.exc_info()[2])


def get_wrapping_class(node):
    """Obtain the class that *wraps* this node

    We consider that a class wraps a node if the class
    is a parent for the said node.
    """

    klass = node.frame()
    while klass is not None and not isinstance(klass, ClassDef):
        if klass.parent is None:
            klass = None
        else:
            klass = klass.parent.frame()
    return klass
