# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
#
# The code in this file was originally part of logilab-common, licensed under
# the same license.

import importlib
import platform
import sys
import warnings

import lazy_object_proxy
import six
import wrapt

JYTHON = True if platform.python_implementation() == 'Jython' else False

try:
    from functools import singledispatch as _singledispatch
except ImportError:
    from singledispatch import singledispatch as _singledispatch


def singledispatch(func):
    '''Modified singledispatch decorator that doesn't crash on old-style classes.

    This is a workaround in particular for the Python 2 standard
    library, because some modules export old-style classes that cause
    raw_building.py to crash.  Old-style classes themselves (not their
    instances) have no __class__ attribute, so the standard
    library/backport singledispatch decorator raises an
    AttributeError.  For forward compatibility, in particular for
    proxy objects like the zipper, the wrapper function tries
    __class__ first and if that fails, falls back to calling type(),
    which doesn't raise an exception on old-style classes.  This new
    wrapped function is then used to replace the singledispatch
    wrapper function, avoiding the overhead of another function call.
    This will be slightly slower than the standard library/backport
    function because of the try/except block, but hopefully not enough
    to matter.

    '''
    
    old_generic_func = _singledispatch(func)
    @wrapt.decorator
    def wrapper(func, instance, args, kws):
        try:
            return old_generic_func.dispatch(args[0].__class__)(*args, **kws)
        except AttributeError:
            return old_generic_func.dispatch(type(args[0]))(*args, **kws)
    new_generic_func = wrapper(func)
    new_generic_func.register = old_generic_func.register
    new_generic_func.dispatch = old_generic_func.dispatch
    new_generic_func.registry = old_generic_func.registry
    new_generic_func._clear_cache = old_generic_func._clear_cache
    return new_generic_func


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