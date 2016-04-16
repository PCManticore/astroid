# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""tests for specific behaviour of astroid scoped nodes (i.e. module, class and
function)
"""
import os
import sys
from functools import partial
import unittest
import warnings

import six

from astroid import builder
from astroid import nodes
from astroid.tree import scoped_nodes
from astroid import util
from astroid.exceptions import (
    InferenceError, AttributeInferenceError,
    NoDefault, ResolveError, MroError,
    InconsistentMroError, DuplicateBasesError,
    TooManyLevelsError,
)
from astroid import test_utils
from astroid.tests import resources


BUILTINS = six.moves.builtins.__name__


def _test_dict_interface(self, node, test_attr):
    self.assertIs(node[test_attr], node[test_attr])
    self.assertIn(test_attr, node)
    node.keys()
    node.values()
    node.items()
    iter(node)


class ModuleLoader(resources.SysPathSetup):
    def setUp(self):
        super(ModuleLoader, self).setUp()
        self.module = resources.build_file('data/module.py', 'data.module')
        self.module2 = resources.build_file('data/module2.py', 'data.module2')
        self.nonregr = resources.build_file('data/nonregr.py', 'data.nonregr')
        self.pack = resources.build_file('data/__init__.py', 'data')


class ModuleNodeTest(ModuleLoader, unittest.TestCase):

    def test_dict_interface(self):
        _test_dict_interface(self, self.module, 'YO')

    def test_public_names(self):
        m = builder.parse('''
        name = 'a'
        _bla = 2
        other = 'o'
        class Aaa: pass
        def func(): print('yo')
        __all__ = 'Aaa', '_bla', 'name'
        ''')
        values = sorted(['Aaa', 'name', 'other', 'func'])
        self.assertEqual(sorted(m.public_names()), values)
        m = builder.parse('''
        name = 'a'
        _bla = 2
        other = 'o'
        class Aaa: pass

        def func(): return 'yo'
        ''')
        res = sorted(m.public_names())
        self.assertEqual(res, values)

        m = builder.parse('''
            from missing import tzop
            trop = "test"
            __all__ = (trop, "test1", tzop, 42)
        ''')
        res = sorted(m.public_names())
        self.assertEqual(res, ["trop", "tzop"])

        m = builder.parse('''
            test = tzop = 42
            __all__ = ('test', ) + ('tzop', )
        ''')
        res = sorted(m.public_names())
        self.assertEqual(res, ['test', 'tzop'])

    def test_relative_to_absolute_name(self):
        # package
        mod = nodes.Module('very.multi.package', 'doc')
        mod.package = True
        modname = mod.relative_to_absolute_name('utils', 1)
        self.assertEqual(modname, 'very.multi.package.utils')
        modname = mod.relative_to_absolute_name('utils', 2)
        self.assertEqual(modname, 'very.multi.utils')
        modname = mod.relative_to_absolute_name('utils', 0)
        self.assertEqual(modname, 'very.multi.package.utils')
        modname = mod.relative_to_absolute_name('', 1)
        self.assertEqual(modname, 'very.multi.package')
        # non package
        mod = nodes.Module('very.multi.module', 'doc')
        mod.package = False
        modname = mod.relative_to_absolute_name('utils', 0)
        self.assertEqual(modname, 'very.multi.utils')
        modname = mod.relative_to_absolute_name('utils', 1)
        self.assertEqual(modname, 'very.multi.utils')
        modname = mod.relative_to_absolute_name('utils', 2)
        self.assertEqual(modname, 'very.utils')
        modname = mod.relative_to_absolute_name('', 1)
        self.assertEqual(modname, 'very.multi')

    def test_relative_to_absolute_name_beyond_top_level(self):
        mod = nodes.Module('a.b.c', '')
        mod.package = True
        for level in (5, 4):
            with self.assertRaises(TooManyLevelsError) as cm:
                mod.relative_to_absolute_name('test', level)

            expected = ("Relative import with too many levels "
                        "({level}) for module {name!r}".format(
                        level=level - 1, name=mod.name))
            self.assertEqual(expected, str(cm.exception))

    def test_file_stream_in_memory(self):
        data = '''irrelevant_variable is irrelevant'''
        astroid = builder.parse(data, 'in_memory')
        with warnings.catch_warnings(record=True):
            with astroid.stream() as stream:
                self.assertEqual(stream.read().decode(), data)

    def test_file_stream_physical(self):
        path = resources.find('data/absimport.py')
        astroid = builder.AstroidBuilder().file_build(path, 'all')
        with open(path, 'rb') as file_io:
            with astroid.stream() as stream:
                self.assertEqual(stream.read(), file_io.read())

    def test_stream_api(self):
        path = resources.find('data/absimport.py')
        astroid = builder.AstroidBuilder().file_build(path, 'all')
        stream = astroid.stream()
        self.assertTrue(hasattr(stream, 'close'))
        with stream:
            with open(path, 'rb') as file_io:
                self.assertEqual(stream.read(), file_io.read())


class FunctionNodeTest(ModuleLoader, unittest.TestCase):

    def test_dict_interface(self):
        _test_dict_interface(self, self.module['global_access'], 'local')

    def test_default_value(self):
        func = self.module2['make_class']
        self.assertIsInstance(func.args.default_value('base'), nodes.Attribute)
        self.assertRaises(NoDefault, func.args.default_value, 'args')
        self.assertRaises(NoDefault, func.args.default_value, 'kwargs')
        self.assertRaises(NoDefault, func.args.default_value, 'any')

    def test_navigation(self):
        function = self.module['global_access']
        self.assertEqual(function.statement(), function)
        l_sibling = function.previous_sibling()
        # check taking parent if child is not a stmt
        self.assertIsInstance(l_sibling, nodes.Assign)
        child = function.args.args[0]
        self.assertIs(l_sibling, child.previous_sibling())
        r_sibling = function.next_sibling()
        self.assertIsInstance(r_sibling, nodes.ClassDef)
        self.assertEqual(r_sibling.name, 'YO')
        self.assertIs(r_sibling, child.next_sibling())
        last = r_sibling.next_sibling().next_sibling().next_sibling()
        self.assertIsInstance(last, nodes.Assign)
        self.assertIsNone(last.next_sibling())
        first = l_sibling.root().body[0]
        self.assertIsNone(first.previous_sibling())

    def test_nested_args(self):
        if sys.version_info >= (3, 0):
            self.skipTest("nested args has been removed in py3.x")
        code = '''
            def nested_args(a, (b, c, d)):
                "nested arguments test"
        '''
        tree = builder.parse(code)
        func = tree['nested_args']
        self.assertEqual(sorted(func.locals), ['a', 'b', 'c', 'd'])
        self.assertEqual(func.args.format_args(), 'a, b, c, d')

    def test_four_args(self):
        func = self.module['four_args']
        #self.assertEqual(func.args.args, ['a', ('b', 'c', 'd')])
        local = sorted(func.keys())
        self.assertEqual(local, ['a', 'b', 'c', 'd'])
        self.assertEqual(func.type, 'function')

    def test_format_args(self):
        func = self.module2['make_class']
        self.assertEqual(func.args.format_args(),
                         'any, base=data.module.YO, *args, **kwargs')
        func = self.module['four_args']
        self.assertEqual(func.args.format_args(), 'a, b, c, d')

    def test_is_generator(self):
        self.assertTrue(self.module2['generator'].is_generator())
        self.assertFalse(self.module2['not_a_generator'].is_generator())
        self.assertFalse(self.module2['make_class'].is_generator())

        # TODO: enable?
##     def test_raises(self):
##         method = self.module2['AbstractClass']['to_override']
##         self.assertEqual([str(term) for term in method.raises()],
##                           ["Call(Name('NotImplementedError'), [], None, None)"] )

##     def test_returns(self):
##         method = self.module2['AbstractClass']['return_something']
##         # use string comp since Node doesn't handle __cmp__
##         self.assertEqual([str(term) for term in method.returns()],
##                           ["Const('toto')", "Const(None)"])

    def test_lambda_qname(self):
        astroid = builder.parse('lmbd = lambda: None', __name__)
        self.assertEqual('%s.<lambda>' % __name__, astroid['lmbd'].parent.value.qname())

    def test_argnames(self):
        if sys.version_info < (3, 0):
            code = 'def f(a, (b, c), *args, **kwargs): pass'
        else:
            code = 'def f(a, b, c, *args, **kwargs): pass'
        astroid = builder.parse(code, __name__)
        self.assertEqual(astroid['f'].argnames(), ['a', 'b', 'c', 'args', 'kwargs'])



class ClassNodeTest(ModuleLoader, unittest.TestCase):

    def test_navigation(self):
        klass = self.module['YO']
        self.assertEqual(klass.statement(), klass)
        l_sibling = klass.previous_sibling()
        self.assertTrue(isinstance(l_sibling, nodes.FunctionDef), l_sibling)
        self.assertEqual(l_sibling.name, 'global_access')
        r_sibling = klass.next_sibling()
        self.assertIsInstance(r_sibling, nodes.ClassDef)
        self.assertEqual(r_sibling.name, 'YOUPI')

    def test_function_with_decorator_lineno(self):
        data = '''
            @f(a=2,
               b=3)
            def g1(x):
                print(x)

            @f(a=2,
               b=3)
            def g2():
                pass
        '''
        astroid = builder.parse(data)
        self.assertEqual(astroid['g1'].fromlineno, 4)
        self.assertEqual(astroid['g1'].tolineno, 5)
        self.assertEqual(astroid['g2'].fromlineno, 9)
        self.assertEqual(astroid['g2'].tolineno, 10)


if __name__ == '__main__':
    unittest.main()
