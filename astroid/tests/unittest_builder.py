# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/master/COPYING.LESSER

"""tests for the astroid builder and rebuilder module"""

import os
import sys
import unittest

import six

from astroid import builder
from astroid import exceptions
from astroid import nodes
from astroid import test_utils
from astroid.tests import resources

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
        self.assertEqual(strarg.fromlineno, 5)
        self.assertEqual(strarg.tolineno, 5)
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
        function = test_utils.extract_node('''
            @decorator
            def function( #@
                arg):
                print (arg)
            ''')
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

    def test_data_build_null_bytes(self):
        with self.assertRaises(exceptions.AstroidSyntaxError):
            builder.parse('\x00')

    def test_data_build_invalid_x_escape(self):
        with self.assertRaises(exceptions.AstroidSyntaxError):
            builder.parse('"\\x1"')

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
        self.module, self.nodes = resources.module()

    def test_module_base_props(self):
        """test base properties and method of a astroid module"""
        module = self.module
        self.assertEqual(module.name, 'data.module')
        self.assertEqual(module.doc, "test module for astroid\n")
        self.assertEqual(module.fromlineno, 0)
        self.assertIsNone(module.parent)
        self.assertEqual(module.frame(), module)
        self.assertEqual(module.root(), module)
        # TODO: restore this when paths are made consistent.

        self.assertEqual(module.pure_python, 1)
        self.assertEqual(module.package, 0)
        self.assertFalse(module.is_statement)
        self.assertEqual(module.statement(), module)
        self.assertEqual(module.statement(), module)

    def test_function_base_props(self):
        """test base properties and method of a astroid function"""
        global_access = self.nodes['global_access']
        self.assertEqual(global_access.name, 'global_access')
        self.assertEqual(global_access.doc, 'function test')
        self.assertEqual(global_access.fromlineno, 11)
        self.assertTrue(global_access.parent)
        self.assertEqual(global_access.frame(), global_access)
        self.assertEqual(global_access.parent.frame(), self.module)
        self.assertEqual(global_access.root(), self.module)
        self.assertEqual([n.name for n in global_access.args.args], ['key', 'val'])

    def test_class_base_props(self):
        """test base properties and method of a astroid class"""
        yo = self.nodes['YO']
        self.assertEqual(yo.name, 'YO')
        self.assertEqual(yo.doc, 'hehe')
        self.assertEqual(yo.fromlineno, 25)
        self.assertTrue(yo.parent)
        self.assertEqual(yo.frame(), yo)
        self.assertEqual(yo.parent.frame(), self.module)
        self.assertEqual(yo.root(), self.module)

    def test_method_base_props(self):
        """test base properties and method of a astroid method"""
        youpi = self.nodes['YOUPI']
        # "normal" method
        method = self.nodes['method']
        self.assertEqual(method.name, 'method')
        self.assertEqual([n.name for n in method.args.args], ['self'])
        self.assertEqual(method.doc, 'method test')
        self.assertEqual(method.fromlineno, 47)
        # class method
        method = self.nodes['class_method']
        self.assertEqual([n.name for n in method.args.args], ['cls'])
        method = self.nodes['static_method']
        self.assertEqual(method.args.args, [])


if __name__ == '__main__':
    unittest.main()
