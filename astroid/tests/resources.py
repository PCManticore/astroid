# Copyright 2014 Google, Inc. All rights reserved.
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
import binascii
import contextlib
import os
import sys
import shutil
import tempfile

import pkg_resources
import six

from astroid import builder
from astroid import MANAGER
from astroid import test_utils

DATA_DIR = 'testdata'
BUILTINS = six.moves.builtins.__name__


@contextlib.contextmanager
def _temporary_file():
    name = binascii.hexlify(os.urandom(5)).decode()
    path = find(name)
    try:
        yield path
    finally:
        os.remove(path)

@contextlib.contextmanager
def tempfile_with_content(content):
    with _temporary_file() as tmp:
        with open(tmp, 'wb') as stream:
            stream.write(content)
        yield tmp


def find(name):
    return pkg_resources.resource_filename(
        'astroid.tests',
        os.path.normpath(os.path.join(DATA_DIR, name)))


def build_file(path, modname=None):
    return builder.AstroidBuilder().file_build(find(path), modname)


def module():
    # TODO: there needs to be consistency in the AST produced by
    # different calls.  I've hacked this for now to make the calls the
    # same.
    module = builder.parse(
        # open('astroid/tests/testdata/data/module.py', 'r').read(), 'data.module')
        open(find('data/module.py'), 'r').read(), 'data.module')
    # module = resources.build_file('data/module.py', 'data.module')
    nodes = test_utils.extract_node(
        # open('astroid/tests/testdata/data/module.py', 'r').read(), 'data.module')
        open(find('data/module.py'), 'r').read(), 'data.module')
    names = ['NameNode', 'modutils', 'os.path', 'global_access',
             'YO', 'YOUPI', 'method', 'static_method',
             'class_method', 'four_args']
    return module, dict(zip(names, nodes))

def module2():
    module = builder.parse(
        open(find('data/module2.py'), 'r').read(), 'data.module2')
        # open('astroid/tests/testdata/data/module2.py', 'r').read(), 'data.module2')
    nodes = test_utils.extract_node(
        # open('astroid/tests/testdata/data/module2.py', 'r').read(), 'data.module2')
        open(find('data/module2.py'), 'r').read(), 'data.module2')
    names = ['YO', 'make_class', 'generator', 'not_a_generator',
             'with_metaclass']
    return module, dict(zip(names, nodes))

class SysPathSetup(object):
    def setUp(self):
        sys.path.insert(0, find(''))

    def tearDown(self):
        del sys.path[0]
        datadir = find('')
        for key in list(sys.path_importer_cache):
            if key.startswith(datadir):
                del sys.path_importer_cache[key]


class AstroidCacheSetupMixin(object):
    """Mixin for handling the astroid cache problems.

    When clearing the astroid cache, some tests fails due to
    cache inconsistencies, where some objects had a different
    builtins object referenced.
    This saves the builtins module and makes sure to add it
    back to the astroid_cache after the tests finishes.
    The builtins module is special, since some of the
    transforms for a couple of its objects (str, bytes etc)
    are executed only once, so astroid_bootstrapping will be
    useless for retrieving the original builtins module.
    """

    @classmethod
    def setUpClass(cls):
        cls._builtins = MANAGER.astroid_cache.get(BUILTINS)

    @classmethod
    def tearDownClass(cls):
        if cls._builtins:
            MANAGER.astroid_cache[BUILTINS] = cls._builtins
