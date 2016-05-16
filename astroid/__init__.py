# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/master/COPYING.LESSER

"""Python Abstract Syntax Tree New Generation

The aim of this module is to provide a common base representation of
python source code for projects such as pychecker, pyreverse,
pylint... Well, actually the development of this library is essentially
governed by pylint's needs.

It extends class defined in the python's _ast module with some
additional methods and attributes. Instance attributes are added by a
builder object, which can either generate extended ast (let's call
them astroid ;) by visiting an existent ast tree or by inspecting living
object. Methods are added by monkey patching ast classes.

Main modules are:

* nodes and scoped_nodes for more information about methods and
  attributes added to different node classes

* the manager contains a high level object to get astroid trees from
  source files and living objects. It maintains a cache of previously
  constructed tree for quick access

* builder contains the class responsible to build astroid trees
"""

import importlib
import re
import sys
from operator import attrgetter

import enum


_Context = enum.Enum('Context', 'Load Store Del')
Load = _Context.Load
Store = _Context.Store
Del = _Context.Del
del _Context


# WARNING: internal imports order matters !

# pylint: disable=redefined-builtin, wildcard-import

# make all exception classes accessible from astroid package
from astroid.exceptions import *

# make all node classes accessible from astroid package
from astroid.nodes import *

from astroid.builder import parse

# TODO
# from astroid import zipper
