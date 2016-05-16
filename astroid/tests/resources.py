# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/master/COPYING.LESSER

import os

import pkg_resources
import six

from astroid import builder
from astroid import test_utils

DATA_DIR = 'testdata'
BUILTINS = six.moves.builtins.__name__


def find(name):
    return pkg_resources.resource_filename(
        'astroid.tests',
        os.path.normpath(os.path.join(DATA_DIR, name)))


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
