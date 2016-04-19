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
from textwrap import dedent
import unittest

from astroid import builder
from astroid import nodes
from astroid import scope
from astroid.tree.node_classes import (Assign, Expr, YieldFrom, Name,
                                       Const, ClassDef, FunctionDef)
from astroid import test_utils


class Python3TC(unittest.TestCase):

    @test_utils.require_version('3.0')
    def test_starred_notation(self):
        astroid = builder.parse("*a, b = [1, 2, 3]", 'test', 'test')

        # Get the star node
        node = next(next(next(astroid.get_children()).get_children()).get_children())

        self.assertTrue(isinstance(scope.assign_type(node), Assign))

    @test_utils.require_version('3.3')
    def test_yield_from(self):
        body = dedent("""
        def func():
            yield from iter([1, 2])
        """)
        astroid = builder.parse(body)
        func = astroid.body[0]
        self.assertIsInstance(func, FunctionDef)
        yieldfrom_stmt = func.body[0]

        self.assertIsInstance(yieldfrom_stmt, Expr)
        self.assertIsInstance(yieldfrom_stmt.value, YieldFrom)
        self.assertEqual(yieldfrom_stmt.as_string(),
                         'yield from iter([1, 2])')

    @test_utils.require_version('3.3')
    def test_yield_from_is_generator(self):
        body = dedent("""
        def func():
            yield from iter([1, 2])
        """)
        astroid = builder.parse(body)
        func = astroid.body[0]
        self.assertIsInstance(func, FunctionDef)
        self.assertTrue(func.is_generator())

    @test_utils.require_version('3.3')
    def test_yield_from_as_string(self):
        body = dedent("""
        def func():
            yield from iter([1, 2])
            value = yield from other()
        """)
        astroid = builder.parse(body)
        func = astroid.body[0]
        self.assertEqual(func.as_string().strip(), body.strip())

    # metaclass tests

    @test_utils.require_version('3.0')
    def test_as_string(self):
        body = dedent("""
        from abc import ABCMeta 
        class Test(metaclass=ABCMeta): pass""")
        astroid = builder.parse(body)
        klass = astroid.body[1]

        self.assertEqual(klass.as_string(),
                         '\n\nclass Test(metaclass=ABCMeta):\n    pass\n')

    @test_utils.require_version('3.0')
    def test_metaclass_is_defined(self):
        klass = test_utils.extract_node("""
        from abc import ABCMeta
        class Test(metaclass=ABCMeta): pass
        """)
        metaclass = klass.metaclass
        self.assertEqual(metaclass.name, 'ABCMeta')

    @test_utils.require_version('3.0')
    def test_annotation_support(self):
        func = test_utils.extract_node("""
        def test(a: int, b: str, c: None, d, e,
                 *args: float, **kwargs: int)->int:
            pass
        """)
        self.assertIsInstance(func.args.vararg.annotation, Name)
        self.assertEqual(func.args.vararg.annotation.name, 'float')
        self.assertIsInstance(func.args.kwarg.annotation, Name)
        self.assertEqual(func.args.kwarg.annotation.name, 'int')
        self.assertIsInstance(func.returns, Name)
        self.assertEqual(func.returns.name, 'int')
        arguments = func.args
        self.assertIsInstance(arguments.args[0].annotation, Name)
        self.assertEqual(arguments.args[0].annotation.name, 'int')
        self.assertIsInstance(arguments.args[1].annotation, Name)
        self.assertEqual(arguments.args[1].annotation.name, 'str')
        self.assertIsInstance(arguments.args[2].annotation, Const)
        self.assertIsNone(arguments.args[2].annotation.value)
        self.assertIs(arguments.args[3].annotation, nodes.Empty)
        self.assertIs(arguments.args[4].annotation, nodes.Empty)

        func = test_utils.extract_node("""
        def test(a: int=1, b: str=2): #@
            pass
        """)
        self.assertIsInstance(func.args.args[0].annotation, Name)
        self.assertEqual(func.args.args[0].annotation.name, 'int')
        self.assertIsInstance(func.args.args[1].annotation, Name)
        self.assertEqual(func.args.args[1].annotation.name, 'str')
        self.assertIs(func.returns, nodes.Empty)

    @test_utils.require_version('3.0')
    def test_annotation_as_string(self):
        code1 = dedent('''
        def test(a, b:int=4, c=2, f:'lala'=4)->2:
            pass''')
        code2 = dedent('''
        def test(a:typing.Generic[T], c:typing.Any=24)->typing.Iterable:
            pass''')
        for code in (code1, code2):
            func = test_utils.extract_node(code)
            self.assertEqual(func.as_string(), code)

    @test_utils.require_version('3.5')
    def test_unpacking_in_dicts(self):
        code = "{'x': 1, **{'y': 2}}"
        node = test_utils.extract_node(code)
        self.assertEqual(node.as_string(), code)
        keys = [key for (key, _) in node.items]
        self.assertIsInstance(keys[0], nodes.Const)
        self.assertIsInstance(keys[1], nodes.DictUnpack)

    @test_utils.require_version('3.5')
    def test_nested_unpacking_in_dicts(self):
        code = "{'x': 1, **{'y': 2, **{'z': 3}}}"
        node = test_utils.extract_node(code)
        self.assertEqual(node.as_string(), code)


if __name__ == '__main__':
    unittest.main()
