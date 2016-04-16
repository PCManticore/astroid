# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""tests for the astroid builder and rebuilder module"""

import os
import sys
import unittest

import six

from astroid import builder
from astroid import exceptions
from astroid import manager
from astroid import nodes
from astroid import test_utils
from astroid import util
from astroid.tests import resources

MANAGER = manager.AstroidManager()
BUILTINS = six.moves.builtins.__name__


class FromToLineNoTest(unittest.TestCase):

    def setUp(self):
        self.astroid = builder.parse('''
        """A multiline string
        """

        function('aeozrijz\
        earzer', hop)
        # XXX write test
        x = [i for i in range(5)
             if i % 4]

        fonction(1,
                 2,
                 3,
                 4)

        def definition(a,
                       b,
                       c):
            return a + b + c

        class debile(dict,
                     object):
            pass

        if aaaa: pass
        else:
            aaaa,bbbb = 1,2
            aaaa,bbbb = bbbb,aaaa
        # XXX write test
        hop = \
            aaaa


        __revision__.lower();
        ''')

    def test_callfunc_lineno(self):
        stmts = self.astroid.body
        # on line 4:
        #    function('aeozrijz\
        #    earzer', hop)
        discard = stmts[0]
        self.assertIsInstance(discard, nodes.Expr)
        self.assertEqual(discard.fromlineno, 5)
        self.assertEqual(discard.tolineno, 5)
        callfunc = discard.value
        self.assertIsInstance(callfunc, nodes.Call)
        self.assertEqual(callfunc.fromlineno, 5)
        self.assertEqual(callfunc.tolineno, 5)
        name = callfunc.func
        self.assertIsInstance(name, nodes.Name)
        self.assertEqual(name.fromlineno, 5)
        self.assertEqual(name.tolineno, 5)
        strarg = callfunc.args[0]
        self.assertIsInstance(strarg, nodes.Const)
        if hasattr(sys, 'pypy_version_info'):
            lineno = 4
        else:
            lineno = 5 # no way for this one in CPython (is 4 actually)
        self.assertEqual(strarg.fromlineno, lineno)
        self.assertEqual(strarg.tolineno, lineno)
        namearg = callfunc.args[1]
        self.assertIsInstance(namearg, nodes.Name)
        self.assertEqual(namearg.fromlineno, 5)
        self.assertEqual(namearg.tolineno, 5)
        # on line 10:
        #    fonction(1,
        #             2,
        #             3,
        #             4)
        discard = stmts[2]
        self.assertIsInstance(discard, nodes.Expr)
        self.assertEqual(discard.fromlineno, 10)
        self.assertEqual(discard.tolineno, 13)
        callfunc = discard.value
        self.assertIsInstance(callfunc, nodes.Call)
        self.assertEqual(callfunc.fromlineno, 10)
        self.assertEqual(callfunc.tolineno, 13)
        name = callfunc.func
        self.assertIsInstance(name, nodes.Name)
        self.assertEqual(name.fromlineno, 10)
        self.assertEqual(name.tolineno, 10)
        for i, arg in enumerate(callfunc.args):
            self.assertIsInstance(arg, nodes.Const)
            self.assertEqual(arg.fromlineno, 10+i)
            self.assertEqual(arg.tolineno, 10+i)

    def test_function_lineno(self):
        stmts = self.astroid.body
        # on line 15:
        #    def definition(a,
        #                   b,
        #                   c):
        #        return a + b + c
        function = stmts[3]
        self.assertIsInstance(function, nodes.FunctionDef)
        self.assertEqual(function.fromlineno, 15)
        self.assertEqual(function.tolineno, 18)
        return_ = function.body[0]
        self.assertIsInstance(return_, nodes.Return)
        self.assertEqual(return_.fromlineno, 18)
        self.assertEqual(return_.tolineno, 18)
        if sys.version_info < (3, 0):
            self.assertEqual(function.blockstart_tolineno, 17)
        else:
            self.skipTest('FIXME  http://bugs.python.org/issue10445 '
                          '(no line number on function args)')

    def test_decorated_function_lineno(self):
        astroid = builder.parse('''
            @decorator
            def function(
                arg):
                print (arg)
            ''', __name__)
        function = astroid['function']
        self.assertEqual(function.fromlineno, 3) # XXX discussable, but that's what is expected by pylint right now
        self.assertEqual(function.tolineno, 5)
        self.assertEqual(function.decorators.fromlineno, 2)
        self.assertEqual(function.decorators.tolineno, 2)
        if sys.version_info < (3, 0):
            self.assertEqual(function.blockstart_tolineno, 4)
        else:
            self.skipTest('FIXME  http://bugs.python.org/issue10445 '
                          '(no line number on function args)')


    def test_class_lineno(self):
        stmts = self.astroid.body
        # on line 20:
        #    class debile(dict,
        #                 object):
        #       pass
        class_ = stmts[4]
        self.assertIsInstance(class_, nodes.ClassDef)
        self.assertEqual(class_.fromlineno, 20)
        self.assertEqual(class_.tolineno, 22)
        self.assertEqual(class_.blockstart_tolineno, 21)
        pass_ = class_.body[0]
        self.assertIsInstance(pass_, nodes.Pass)
        self.assertEqual(pass_.fromlineno, 22)
        self.assertEqual(pass_.tolineno, 22)

    def test_if_lineno(self):
        stmts = self.astroid.body
        # on line 20:
        #    if aaaa: pass
        #    else:
        #        aaaa,bbbb = 1,2
        #        aaaa,bbbb = bbbb,aaaa
        if_ = stmts[5]
        self.assertIsInstance(if_, nodes.If)
        self.assertEqual(if_.fromlineno, 24)
        self.assertEqual(if_.tolineno, 27)
        self.assertEqual(if_.blockstart_tolineno, 24)
        self.assertEqual(if_.orelse[0].fromlineno, 26)
        self.assertEqual(if_.orelse[1].tolineno, 27)

    def test_for_while_lineno(self):
        for code in ('''
            for a in range(4):
              print (a)
              break
            else:
              print ("bouh")
            ''', '''
            while a:
              print (a)
              break
            else:
              print ("bouh")
            '''):
            astroid = builder.parse(code, __name__)
            stmt = astroid.body[0]
            self.assertEqual(stmt.fromlineno, 2)
            self.assertEqual(stmt.tolineno, 6)
            self.assertEqual(stmt.blockstart_tolineno, 2)
            self.assertEqual(stmt.orelse[0].fromlineno, 6) # XXX
            self.assertEqual(stmt.orelse[0].tolineno, 6)

    def test_try_except_lineno(self):
        astroid = builder.parse('''
            try:
              print (a)
            except:
              pass
            else:
              print ("bouh")
            ''', __name__)
        try_ = astroid.body[0]
        self.assertEqual(try_.fromlineno, 2)
        self.assertEqual(try_.tolineno, 7)
        self.assertEqual(try_.blockstart_tolineno, 2)
        self.assertEqual(try_.orelse[0].fromlineno, 7) # XXX
        self.assertEqual(try_.orelse[0].tolineno, 7)
        hdlr = try_.handlers[0]
        self.assertEqual(hdlr.fromlineno, 4)
        self.assertEqual(hdlr.tolineno, 5)
        self.assertEqual(hdlr.blockstart_tolineno, 4)


    def test_try_finally_lineno(self):
        astroid = builder.parse('''
            try:
              print (a)
            finally:
              print ("bouh")
            ''', __name__)
        try_ = astroid.body[0]
        self.assertEqual(try_.fromlineno, 2)
        self.assertEqual(try_.tolineno, 5)
        self.assertEqual(try_.blockstart_tolineno, 2)
        self.assertEqual(try_.finalbody[0].fromlineno, 5) # XXX
        self.assertEqual(try_.finalbody[0].tolineno, 5)


    def test_try_finally_25_lineno(self):
        astroid = builder.parse('''
            try:
              print (a)
            except:
              pass
            finally:
              print ("bouh")
            ''', __name__)
        try_ = astroid.body[0]
        self.assertEqual(try_.fromlineno, 2)
        self.assertEqual(try_.tolineno, 7)
        self.assertEqual(try_.blockstart_tolineno, 2)
        self.assertEqual(try_.finalbody[0].fromlineno, 7) # XXX
        self.assertEqual(try_.finalbody[0].tolineno, 7)


    def test_with_lineno(self):
        astroid = builder.parse('''
            from __future__ import with_statement
            with file("/tmp/pouet") as f:
                print (f)
            ''', __name__)
        with_ = astroid.body[1]
        self.assertEqual(with_.fromlineno, 3)
        self.assertEqual(with_.tolineno, 4)
        self.assertEqual(with_.blockstart_tolineno, 3)


class BuilderTest(unittest.TestCase):

    def setUp(self):
        self.builder = builder.AstroidBuilder()

    def test_data_build_null_bytes(self):
        with self.assertRaises(exceptions.AstroidSyntaxError):
            self.builder.string_build('\x00')

    def test_data_build_invalid_x_escape(self):
        with self.assertRaises(exceptions.AstroidSyntaxError):
            self.builder.string_build('"\\x1"')

    def test_missing_file(self):
        with self.assertRaises(exceptions.AstroidBuildingError):
            resources.build_file('data/inexistant.py')

    def test_package_name(self):
        """test base properties and method of a astroid module"""
        datap = resources.build_file('data/__init__.py', 'data')
        self.assertEqual(datap.name, 'data')
        self.assertEqual(datap.package, 1)
        datap = resources.build_file('data/__init__.py', 'data.__init__')
        self.assertEqual(datap.name, 'data')
        self.assertEqual(datap.package, 1)

    def test_yield_parent(self):
        """check if we added discard nodes as yield parent (w/ compiler)"""
        code = """
            def yiell(): #@
                yield 0
                if noe:
                    yield more
        """
        func = test_utils.extract_node(code)
        self.assertIsInstance(func, nodes.FunctionDef)
        stmt = func.body[0]
        self.assertIsInstance(stmt, nodes.Expr)
        self.assertIsInstance(stmt.value, nodes.Yield)
        self.assertIsInstance(func.body[1].body[0], nodes.Expr)
        self.assertIsInstance(func.body[1].body[0].value, nodes.Yield)

    def test_no_future_imports(self):
        mod = builder.parse("import sys")
        self.assertEqual(set(), mod.future_imports)

    def test_future_imports(self):
        mod = builder.parse("from __future__ import print_function")
        self.assertEqual(frozenset(['print_function']), mod.future_imports)

    def test_two_future_imports(self):
        mod = builder.parse("""
            from __future__ import print_function
            from __future__ import absolute_import
            """)
        self.assertEqual(frozenset(['print_function', 'absolute_import']), mod.future_imports)

    def test_augassign_attr(self):
        builder.parse("""
            class Counter:
                v = 0
                def inc(self):
                    self.v += 1
            """, __name__)
        # TODO: Check self.v += 1 generate AugAssign(AssAttr(...)),
        # not AugAssign(GetAttr(AssName...))

    def test_build_constants(self):
        '''test expected values of constants after rebuilding'''
        code = '''
            def func():
                return None
                return
                return 'None'
            '''
        astroid = builder.parse(code)
        none, nothing, chain = [ret.value for ret in astroid.body[0].body]
        self.assertIsInstance(none, nodes.Const)
        self.assertIsNone(none.value)
        self.assertIs(nothing, nodes.Empty)
        self.assertIsInstance(chain, nodes.Const)
        self.assertEqual(chain.value, 'None')


class FileBuildTest(unittest.TestCase):
    def setUp(self):
        self.module = resources.build_file('data/module.py', 'data.module')

    def test_module_base_props(self):
        """test base properties and method of a astroid module"""
        module = self.module
        self.assertEqual(module.name, 'data.module')
        self.assertEqual(module.doc, "test module for astroid\n")
        self.assertEqual(module.fromlineno, 0)
        self.assertIsNone(module.parent)
        self.assertEqual(module.frame(), module)
        self.assertEqual(module.root(), module)
        self.assertEqual(module.source_file, os.path.abspath(resources.find('data/module.py')))
        self.assertEqual(module.pure_python, 1)
        self.assertEqual(module.package, 0)
        self.assertFalse(module.is_statement)
        self.assertEqual(module.statement(), module)
        self.assertEqual(module.statement(), module)

    def test_module_locals(self):
        """test the 'locals' dictionary of a astroid module"""
        module = self.module
        _locals = module.locals
        self.assertEqual(_locals, module.globals)
        keys = sorted(_locals.keys())
        should = ['MY_DICT', 'NameNode', 'YO', 'YOUPI',
                  '__revision__', 'global_access', 'modutils', 'four_args',
                  'os', 'redirect']
        should.sort()
        self.assertEqual(keys, sorted(should))

    def test_function_base_props(self):
        """test base properties and method of a astroid function"""
        module = self.module
        function = module['global_access']
        self.assertEqual(function.name, 'global_access')
        self.assertEqual(function.doc, 'function test')
        self.assertEqual(function.fromlineno, 11)
        self.assertTrue(function.parent)
        self.assertEqual(function.frame(), function)
        self.assertEqual(function.parent.frame(), module)
        self.assertEqual(function.root(), module)
        self.assertEqual([n.name for n in function.args.args], ['key', 'val'])
        self.assertEqual(function.type, 'function')

    def test_function_locals(self):
        """test the 'locals' dictionary of a astroid function"""
        _locals = self.module['global_access'].locals
        self.assertEqual(len(_locals), 4)
        keys = sorted(_locals.keys())
        self.assertEqual(keys, ['i', 'key', 'local', 'val'])

    def test_class_base_props(self):
        """test base properties and method of a astroid class"""
        module = self.module
        klass = module['YO']
        self.assertEqual(klass.name, 'YO')
        self.assertEqual(klass.doc, 'hehe')
        self.assertEqual(klass.fromlineno, 25)
        self.assertTrue(klass.parent)
        self.assertEqual(klass.frame(), klass)
        self.assertEqual(klass.parent.frame(), module)
        self.assertEqual(klass.root(), module)
        self.assertEqual(klass.basenames, [])
        if six.PY3:
            self.assertTrue(klass.newstyle)
        else:
            self.assertFalse(klass.newstyle)

    def test_class_locals(self):
        """test the 'locals' dictionary of a astroid class"""
        module = self.module
        klass1 = module['YO']
        locals1 = klass1.locals
        keys = sorted(locals1.keys())
        self.assertEqual(keys, ['__init__', 'a'])
        klass2 = module['YOUPI']
        locals2 = klass2.locals
        keys = locals2.keys()
        self.assertEqual(sorted(keys),
                         ['__init__', 'class_attr', 'class_method',
                          'method', 'static_method'])

    def test_class_instance_attrs(self):
        module = self.module
        klass1 = module['YO']
        klass2 = module['YOUPI']
        self.assertEqual(list(klass1.instance_attrs.keys()), ['yo'])
        self.assertEqual(list(klass2.instance_attrs.keys()), ['member'])

    def test_class_basenames(self):
        module = self.module
        klass1 = module['YO']
        klass2 = module['YOUPI']
        self.assertEqual(klass1.basenames, [])
        self.assertEqual(klass2.basenames, ['YO'])

    def test_method_base_props(self):
        """test base properties and method of a astroid method"""
        klass2 = self.module['YOUPI']
        # "normal" method
        method = klass2['method']
        self.assertEqual(method.name, 'method')
        self.assertEqual([n.name for n in method.args.args], ['self'])
        self.assertEqual(method.doc, 'method test')
        self.assertEqual(method.fromlineno, 47)
        self.assertEqual(method.type, 'method')
        # class method
        method = klass2['class_method']
        self.assertEqual([n.name for n in method.args.args], ['cls'])
        self.assertEqual(method.type, 'classmethod')
        # static method
        method = klass2['static_method']
        self.assertEqual(method.args.args, [])
        self.assertEqual(method.type, 'staticmethod')

    def test_method_locals(self):
        """test the 'locals' dictionary of a astroid method"""
        method = self.module['YOUPI']['method']
        _locals = method.locals
        keys = sorted(_locals)
        if sys.version_info < (3, 0):
            self.assertEqual(len(_locals), 6)
            self.assertEqual(keys, ['MY_DICT', 'a', 'autre', 'b', 'local', 'self'])
        else:# ListComp variables are no more accessible outside
            self.assertEqual(len(_locals), 4)
            self.assertEqual(keys, ['MY_DICT', 'autre', 'local', 'self'])

    def test_unknown_encoding(self):
        with self.assertRaises(exceptions.AstroidSyntaxError):
            with resources.tempfile_with_content(b'# -*- coding: lala -*-') as tmp:
                builder.AstroidBuilder().file_build(tmp)


class ModuleBuildTest(resources.SysPathSetup, FileBuildTest):

    def setUp(self):
        super(ModuleBuildTest, self).setUp()
        abuilder = builder.AstroidBuilder()
        try:
            import data.module
        except ImportError:
            # Make pylint happy.
            self.skipTest('Unable to load data.module')
        else:
            self.module = abuilder.module_build(data.module, 'data.module')

@unittest.skipIf(six.PY3, "guess_encoding not used on Python 3")
class TestGuessEncoding(unittest.TestCase):
    def setUp(self):
        self.guess_encoding = builder._guess_encoding

    def testEmacs(self):
        e = self.guess_encoding('# -*- coding: UTF-8  -*-')
        self.assertEqual(e, 'UTF-8')
        e = self.guess_encoding('# -*- coding:UTF-8 -*-')
        self.assertEqual(e, 'UTF-8')
        e = self.guess_encoding('''
        ### -*- coding: ISO-8859-1  -*-
        ''')
        self.assertEqual(e, 'ISO-8859-1')
        e = self.guess_encoding('''

        ### -*- coding: ISO-8859-1  -*-
        ''')
        self.assertIsNone(e)

    def testVim(self):
        e = self.guess_encoding('# vim:fileencoding=UTF-8')
        self.assertEqual(e, 'UTF-8')
        e = self.guess_encoding('''
        ### vim:fileencoding=ISO-8859-1
        ''')
        self.assertEqual(e, 'ISO-8859-1')
        e = self.guess_encoding('''

        ### vim:fileencoding= ISO-8859-1
        ''')
        self.assertIsNone(e)

    def test_wrong_coding(self):
        # setting "coding" varaible
        e = self.guess_encoding("coding = UTF-8")
        self.assertIsNone(e)
        # setting a dictionnary entry
        e = self.guess_encoding("coding:UTF-8")
        self.assertIsNone(e)
        # setting an arguement
        e = self.guess_encoding("def do_something(a_word_with_coding=None):")
        self.assertIsNone(e)

    def testUTF8(self):
        e = self.guess_encoding('\xef\xbb\xbf any UTF-8 data')
        self.assertEqual(e, 'UTF-8')
        e = self.guess_encoding(' any UTF-8 data \xef\xbb\xbf')
        self.assertIsNone(e)


if __name__ == '__main__':
    unittest.main()
