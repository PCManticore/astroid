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
"""tests for specific behaviour of astroid nodes
"""
from functools import partial
import os
import sys
import textwrap
import unittest
import warnings

import six

import astroid
from astroid import builder
from astroid import exceptions
from astroid import nodes
from astroid import parse
from astroid import test_utils
from astroid.tests import resources

abuilder = builder.AstroidBuilder()
BUILTINS = six.moves.builtins.__name__


class AsStringTest(resources.SysPathSetup, unittest.TestCase):

    def test_modules_as_string(self):
        for name in (os.path.join(p, n) for p, _, ns in os.walk('astroid/') for n in ns if n.endswith('.py')):
            with open(name, 'r') as source_file:
                ast = parse(source_file.read())
                # if ast != parse(ast.as_string()):
                #     print(name)
                #     print(ast == ast)
                #     ast.print_tree()
                #     parse(ast.as_string()).print_tree()
                self.assertEqual(ast, parse(ast.as_string()))

    def test_tuple_as_string(self):
        def build(string):
            return abuilder.string_build(string).body[0].value

        self.assertEqual(build('1,').as_string(), '(1, )')
        self.assertEqual(build('1, 2, 3').as_string(), '(1, 2, 3)')
        self.assertEqual(build('(1, )').as_string(), '(1, )')
        self.assertEqual(build('1, 2, 3').as_string(), '(1, 2, 3)')

    @test_utils.require_version(minver='3.0')
    def test_func_signature_issue_185(self):
        code = textwrap.dedent('''
        def test(a, b, c=42, *, x=42, **kwargs):
            print(a, b, c, args)
        ''')
        node = parse(code)
        self.assertEqual(node.as_string().strip(), code.strip())

    def test_varargs_kwargs_as_string(self):
        ast = abuilder.string_build('raise_string(*args, **kwargs)').body[0]
        self.assertEqual(ast.as_string(), 'raise_string(*args, **kwargs)')

    def test_as_string(self):
        """check as_string for python syntax >= 2.7"""
        code = '''one_two = {1, 2}
b = {v: k for (k, v) in enumerate('string')}
cdd = {k for k in b}\n\n'''
        ast = abuilder.string_build(code)
        self.assertMultiLineEqual(ast.as_string(), code)

    @test_utils.require_version('3.0')
    def test_3k_as_string(self):
        """check as_string for python 3k syntax"""
        code = '''print()

def function(var):
    nonlocal counter
    try:
        hello
    except NameError as nexc:
        (*hell, o) = b'hello'
        raise AttributeError from nexc
\n'''
        ast = abuilder.string_build(code)
        self.assertEqual(ast.as_string(), code)

    @test_utils.require_version('3.0')
    @unittest.expectedFailure
    def test_3k_annotations_and_metaclass(self):
        code_annotations = textwrap.dedent('''
        def function(var:int):
            nonlocal counter

        class Language(metaclass=Natural):
            """natural language"""
        ''')

        ast = abuilder.string_build(code_annotations)
        self.assertEqual(ast.as_string(), code_annotations)

    def test_ellipsis(self):
        ast = abuilder.string_build('a[...]').body[0]
        self.assertEqual(ast.as_string(), 'a[...]')

    def test_slices(self):
        for code in ('a[0]', 'a[1:3]', 'a[:-1:step]', 'a[:,newaxis]',
                     'a[newaxis,:]', 'del L[::2]', 'del A[1]', 'del Br[:]'):
            ast = abuilder.string_build(code).body[0]
            self.assertEqual(ast.as_string(), code)

    def test_slice_and_subscripts(self):
        code = """a[:1] = bord[2:]
a[:1] = bord[2:]
del bree[3:d]
bord[2:]
del av[d::f], a[df:]
a[:1] = bord[2:]
del SRC[::1,newaxis,1:]
tous[vals] = 1010
del thousand[key]
del a[::2], a[:-1:step]
del Fee.form[left:]
aout.vals = miles.of_stuff
del (ccok, (name.thing, foo.attrib.value)), Fee.form[left:]
if all[1] == bord[0:]:
    pass\n\n"""
        ast = abuilder.string_build(code)
        self.assertEqual(ast.as_string(), code)


class _NodeTest(unittest.TestCase):
    """test transformation of If Node"""
    CODE = None

    @property
    def astroid(self):
        try:
            return self.__class__.__dict__['CODE_Astroid']
        except KeyError:
            astroid = builder.parse(self.CODE)
            self.__class__.CODE_Astroid = astroid
            return astroid


class IfNodeTest(_NodeTest):
    """test transformation of If Node"""
    CODE = """
        if 0:
            print()

        if True:
            print()
        else:
            pass

        if "":
            print()
        elif []:
            raise

        if 1:
            print()
        elif True:
            print()
        elif func():
            pass
        else:
            raise
    """

    def test_if_elif_else_node(self):
        """test transformation for If node"""
        self.assertEqual(len(self.astroid.body), 4)
        for stmt in self.astroid.body:
            self.assertIsInstance(stmt, nodes.If)
        self.assertFalse(self.astroid.body[0].orelse)  # simple If
        self.assertIsInstance(self.astroid.body[1].orelse[0], nodes.Pass)  # If / else
        self.assertIsInstance(self.astroid.body[2].orelse[0], nodes.If)  # If / elif
        self.assertIsInstance(self.astroid.body[3].orelse[0].orelse[0], nodes.If)

    def test_block_range(self):
        # XXX ensure expected values
        self.assertEqual(self.astroid.block_range(1), (0, 22))
        self.assertEqual(self.astroid.block_range(10), (0, 22))  # XXX (10, 22) ?
        self.assertEqual(self.astroid.body[1].block_range(5), (5, 6))
        self.assertEqual(self.astroid.body[1].block_range(6), (6, 6))
        self.assertEqual(self.astroid.body[1].orelse[0].block_range(7), (7, 8))
        self.assertEqual(self.astroid.body[1].orelse[0].block_range(8), (8, 8))


class TryExceptNodeTest(_NodeTest):
    CODE = """
        try:
            print ('pouet')
        except IOError:
            pass
        except UnicodeError:
            print()
        else:
            print()
    """

    def test_block_range(self):
        # XXX ensure expected values
        self.assertEqual(self.astroid.body[0].block_range(1), (1, 8))
        self.assertEqual(self.astroid.body[0].block_range(2), (2, 2))
        self.assertEqual(self.astroid.body[0].block_range(3), (3, 8))
        self.assertEqual(self.astroid.body[0].block_range(4), (4, 4))
        self.assertEqual(self.astroid.body[0].block_range(5), (5, 5))
        self.assertEqual(self.astroid.body[0].block_range(6), (6, 6))
        self.assertEqual(self.astroid.body[0].block_range(7), (7, 7))
        self.assertEqual(self.astroid.body[0].block_range(8), (8, 8))


class TryFinallyNodeTest(_NodeTest):
    CODE = """
        try:
            print ('pouet')
        finally:
            print ('pouet')
    """

    def test_block_range(self):
        # XXX ensure expected values
        self.assertEqual(self.astroid.body[0].block_range(1), (1, 4))
        self.assertEqual(self.astroid.body[0].block_range(2), (2, 2))
        self.assertEqual(self.astroid.body[0].block_range(3), (3, 4))
        self.assertEqual(self.astroid.body[0].block_range(4), (4, 4))


class TryExceptFinallyNodeTest(_NodeTest):
    CODE = """
        try:
            print('pouet')
        except Exception:
            print ('oops')
        finally:
            print ('pouet')
    """

    def test_block_range(self):
        # XXX ensure expected values
        self.assertEqual(self.astroid.body[0].block_range(1), (1, 6))
        self.assertEqual(self.astroid.body[0].block_range(2), (2, 2))
        self.assertEqual(self.astroid.body[0].block_range(3), (3, 4))
        self.assertEqual(self.astroid.body[0].block_range(4), (4, 4))
        self.assertEqual(self.astroid.body[0].block_range(5), (5, 5))
        self.assertEqual(self.astroid.body[0].block_range(6), (6, 6))


@unittest.skipIf(six.PY3, "Python 2 specific test.")
class TryExcept2xNodeTest(_NodeTest):
    CODE = """
        try:
            hello
        except AttributeError, (retval, desc):
            pass
    """


    def test_tuple_attribute(self):
        handler = self.astroid.body[0].handlers[0]
        self.assertIsInstance(handler.name, nodes.Tuple)


class ImportNodeTest(resources.SysPathSetup, unittest.TestCase):
    def setUp(self):
        super(ImportNodeTest, self).setUp()
        self.module, self.nodes = resources.module()
        self.module2, self.nodes2 = resources.module2()
        # self.module = resources.build_file('data/module.py', 'data.module')
        # self.module2 = resources.build_file('data/module2.py', 'data.module2')

    # TODO: do we want real_name?
    @unittest.skipUnless(2 == 3, "need to decide if we need real_name or not")
    def test_real_name(self):
        from_ = self.nodes['NameNode']
        self.assertEqual(inferenceutil.real_name(from_, 'NameNode'), 'Name')
        imp_ = self.nodes['os.path']
        self.assertEqual(inferenceutil.real_name(imp_, 'os'), 'os')
        self.assertRaises(exceptions.AttributeInferenceError,
                          inferenceutil.real_name, imp_, 'os.path')
        imp_ = self.module['NameNode']
        self.assertEqual(inferenceutil.real_name(imp_, 'NameNode'), 'Name')
        self.assertRaises(exceptions.AttributeInferenceError,
                          inferenceutil.real_name, imp_, 'Name')
        imp_ = self.nodes2['YO']
        self.assertEqual(inferenceutil.real_name(imp_, 'YO'), 'YO')
        self.assertRaises(exceptions.AttributeInferenceError,
                          inferenceutil.real_name, imp_, 'data')

    def test_as_string(self):
        ast = self.nodes['modutils']
        self.assertEqual(ast.as_string(), "from astroid import modutils")
        ast = self.nodes['NameNode']
        self.assertEqual(ast.as_string(), "from astroid.tree.node_classes import Name as NameNode")
        ast = self.nodes['os.path']
        self.assertEqual(ast.as_string(), "import os.path")
        code = """from . import here
from .. import door
from .store import bread
from ..cave import wine\n\n"""
        ast = abuilder.string_build(code)
        self.assertMultiLineEqual(ast.as_string(), code)


class CmpNodeTest(unittest.TestCase):
    def test_as_string(self):
        ast = abuilder.string_build("a == 2").body[0]
        self.assertEqual(ast.as_string(), "a == 2")


# TODO: test depends on raw_building

# class ConstNodeTest(unittest.TestCase):
    
    # def _test(self, value):
    #     node = raw_building.ast_from_object(value)
    #     self.assertIsInstance(node._proxied, (nodes.ClassDef, nodes.AssignName))
    #     self.assertEqual(node._proxied.name, value.__class__.__name__)
    #     self.assertIs(node.value, value)
    #     self.assertTrue(node._proxied.parent)
    #     self.assertEqual(node._proxied.root().name, value.__class__.__module__)

    # def test_none(self):
    #     self._test(None)

    # def test_bool(self):
    #     self._test(True)

    # def test_int(self):
    #     self._test(1)

    # def test_float(self):
    #     self._test(1.0)

    # def test_complex(self):
    #     self._test(1.0j)

    # def test_str(self):
    #     self._test('a')

    # def test_unicode(self):
    #     self._test(u'a')


class NameNodeTest(unittest.TestCase):
    def test_assign_to_True(self):
        """test that True and False assignements don't crash"""
        code = """
            True = False #@
            def hello(False):
                pass
            del True #@
        """
        if sys.version_info >= (3, 0):
            with self.assertRaises(exceptions.AstroidBuildingError):
                builder.parse(code)
        else:
            assign0, assign1 = test_utils.extract_node(code)
            assign_true = assign0.down().down()
            self.assertIsInstance(assign_true, nodes.AssignName)
            self.assertEqual(assign_true.name, "True")
            del_true = assign1.down().down()
            self.assertIsInstance(del_true, nodes.DelName)
            self.assertEqual(del_true.name, "True")


class ArgumentsNodeTC(unittest.TestCase):

    # TODO: test depends on inference

    @unittest.skipIf(sys.version_info[:2] == (3, 3),
                     "Line numbering is broken on Python 3.3.")
    def test_linenumbering(self):
        func = test_utils.extract_node('''
            def func(a, #@
                b): pass
            x = lambda x: None
        ''')
        self.assertEqual(func.args.fromlineno, 2)
        self.assertFalse(func.args.is_statement)
        # xlambda = next(ast['x'].infer())
        # self.assertEqual(xlambda.args.fromlineno, 4)
        # self.assertEqual(xlambda.args.tolineno, 4)
        # self.assertFalse(xlambda.args.is_statement)
        if sys.version_info < (3, 0):
            self.assertEqual(func.args.tolineno, 3)
        else:
            self.skipTest('FIXME  http://bugs.python.org/issue10445 '
                          '(no line number on function args)')




@test_utils.require_version('3.5')
class Python35AsyncTest(unittest.TestCase):

    def test_async_await_keywords(self):
        async_def, async_for, async_with, await_node = test_utils.extract_node('''
        async def func(): #@
            async for i in range(10): #@
                f = __(await i)
            async with test(): #@
                pass
        ''')
        self.assertIsInstance(async_def, nodes.AsyncFunctionDef)
        self.assertIsInstance(async_for, nodes.AsyncFor)
        self.assertIsInstance(async_with, nodes.AsyncWith)
        self.assertIsInstance(await_node, nodes.Await)
        self.assertIsInstance(await_node.value, nodes.Name)

    def _test_await_async_as_string(self, code):
        ast_node = parse(code)
        self.assertEqual(ast_node.as_string().strip(), code.strip())

    def test_await_as_string(self):
        code = textwrap.dedent('''
        async def function():
            await 42
        ''')
        self._test_await_async_as_string(code)

    def test_asyncwith_as_string(self):
        code = textwrap.dedent('''
        async def function():
            async with (42):
                pass
        ''')
        self._test_await_async_as_string(code)

    def test_asyncfor_as_string(self):
        code = textwrap.dedent('''
        async def function():
            async for i in range(10):
                await 42
        ''')
        self._test_await_async_as_string(code)


# TODO: are the scope functions in or out?

# class ScopeTest(unittest.TestCase):

#     def test_decorators(self):
#         ast_node = test_utils.extract_node('''
#         @test
#         def foo(): pass
#         ''')
#         decorators = ast_node.decorators
#         self.assertIsInstance(decorators.scope(), nodes.Module)
#         self.assertEqual(decorators.scope(), decorators.root())

#     def test_scope_of_default_argument_value(self):
#         node = test_utils.extract_node('''
#         def test(a=__(b)):
#             pass
#         ''')
#         scope = node.scope()
#         self.assertIsInstance(scope, nodes.Module)

#     @test_utils.require_version(minver='3.0')
#     def test_scope_of_default_keyword_argument_value(self):
#         node = test_utils.extract_node('''
#         def test(*, b=__(c)):
#             pass
#         ''')
#         scope = node.scope()
#         self.assertIsInstance(scope, nodes.Module)

#     @test_utils.require_version(minver='3.0')
#     def test_scope_of_annotations(self):
#         ast_nodes = test_utils.extract_node('''
#         def test(a: __(b), *args:__(f), c:__(d)=4, **kwargs: _(l))->__(x):
#             pass
#         ''')
#         for node in ast_nodes:
#             scope = node.scope()
#             self.assertIsInstance(scope, nodes.Module)

#     def test_scope_of_list_comprehension_target_composite_nodes(self):
#         ast_node = test_utils.extract_node('''
#         [i for data in __([DATA1, DATA2]) for i in data]
#         ''')
#         node = ast_node.elts[0]
#         scope = node.scope()
#         self.assertIsInstance(scope, nodes.Module)

#     def test_scope_of_nested_list_comprehensions(self):
#         ast_node = test_utils.extract_node('''
#         [1 for data in DATA for x in __(data)]
#         ''')
#         scope = ast_node.scope()
#         if six.PY2:
#             self.assertIsInstance(scope, nodes.Module)
#         else:
#             self.assertIsInstance(scope, nodes.ListComp)

#     def test_scope_of_list_comprehension_targets(self):
#         ast_node = test_utils.extract_node('''
#         [1 for data in DATA]
#         ''')
#         # target is `data` from the list comprehension
#         target = ast_node.generators[0].target
#         scope = target.scope()
#         if six.PY2:
#             self.assertIsInstance(scope, nodes.Module)
#         else:
#             self.assertIsInstance(scope, nodes.ListComp)

#     def test_scope_of_list_comprehension_value(self):
#         ast_node = test_utils.extract_node('''
#         [__(i) for i in DATA]
#         ''')
#         scope = ast_node.scope()
#         if six.PY3:
#             self.assertIsInstance(scope, nodes.ListComp)
#         else:
#             self.assertIsInstance(scope, nodes.Module)

#     def test_scope_of_dict_comprehension(self):        
#         ast_nodes = test_utils.extract_node('''
#         {i: __(j) for (i, j) in DATA}
#         {i:j for (i, j) in __(DATA)}
#         ''')
#         elt_scope = ast_nodes[0].scope()
#         self.assertIsInstance(elt_scope, nodes.DictComp)
#         iter_scope = ast_nodes[1].scope()
#         self.assertIsInstance(iter_scope, nodes.Module)

#         ast_node = test_utils.extract_node('''
#         {i:1 for i in DATA}''')
#         target = ast_node.generators[0].target
#         target_scope = target.scope()
#         self.assertIsInstance(target_scope, nodes.DictComp)

#     def test_scope_elt_of_generator_exp(self):
#         ast_node = test_utils.extract_node('''
#         list(__(i) for i in range(10))
#         ''')
#         scope = ast_node.scope()
#         self.assertIsInstance(scope, nodes.GeneratorExp)
        

class ContextTest(unittest.TestCase):

    def test_subscript_load(self):
        node = test_utils.extract_node('f[1]')
        self.assertIs(node.ctx, astroid.Load)

    def test_subscript_del(self):
        node = test_utils.extract_node('del f[1]')
        self.assertIs(node.targets[0].ctx, astroid.Del)

    def test_subscript_store(self):
        node = test_utils.extract_node('f[1] = 2')
        subscript = node.targets[0]
        self.assertIs(subscript.ctx, astroid.Store)

    def test_list_load(self):
        node = test_utils.extract_node('[]')
        self.assertIs(node.ctx, astroid.Load)

    def test_list_del(self):
        node = test_utils.extract_node('del []')
        self.assertIs(node.targets[0].ctx, astroid.Del)

    def test_list_store(self):
        with self.assertRaises(exceptions.AstroidSyntaxError):
            test_utils.extract_node('[0] = 2')

    def test_tuple_load(self):
        node = test_utils.extract_node('(1, )')
        self.assertIs(node.ctx, astroid.Load)

    def test_tuple_store(self):
        with self.assertRaises(exceptions.AstroidSyntaxError):
            test_utils.extract_node('(1, ) = 3')

    @test_utils.require_version(minver='3.5')
    def test_starred_load(self):
        node = test_utils.extract_node('a = *b')
        starred = node.value
        self.assertIs(starred.ctx, astroid.Load)

    @test_utils.require_version(minver='3.0')
    def test_starred_store(self):
        node = test_utils.extract_node('a, *b = 1, 2')
        starred = node.targets[0].elts[1]
        self.assertIs(starred.ctx, astroid.Store) 
        

class FunctionTest(unittest.TestCase):

    def test_function_not_on_top_of_lambda(self):
        lambda_, function_ = test_utils.extract_node('''
        lambda x: x #@
        def func(): pass #@
        ''')
        self.assertNotIsInstance(lambda_, astroid.FunctionDef)
        self.assertNotIsInstance(function_, astroid.Lambda)


class DictTest(unittest.TestCase):

    def test_keys_values_items(self):
        node = test_utils.extract_node('''
        {1: 2, 2:3}
        ''')
        self.assertEqual([key.value for key in node.keys], [1, 2])
        self.assertEqual([value.value for value in node.values], [2, 3])
        self.assertEqual([(key.value, value.value) for (key, value) in node.items],
                         [(1, 2), (2, 3)])


# TODO: Scoped nodes


class ModuleLoader(resources.SysPathSetup):
    def setUp(self):
        super(ModuleLoader, self).setUp()
        self.module, self.nodes = resources.module()
        self.module2, self.nodes2 = resources.module2()
        # self.module = resources.build_file('data/module.py', 'data.module')
        # self.module2 = resources.build_file('data/module2.py', 'data.module2')
        self.nonregr = resources.build_file('data/nonregr.py', 'data.nonregr')
        self.pack = resources.build_file('data/__init__.py', 'data')


class ModuleNodeTest(ModuleLoader, unittest.TestCase):

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
            with self.assertRaises(exceptions.TooManyLevelsError) as cm:
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

    def test_default_value(self):
        make_class = self.nodes2['make_class']
        self.assertIsInstance(make_class.args.default_value('base'), nodes.Attribute)
        self.assertRaises(exceptions.NoDefault, make_class.args.default_value, 'args')
        self.assertRaises(exceptions.NoDefault, make_class.args.default_value, 'kwargs')
        self.assertRaises(exceptions.NoDefault, make_class.args.default_value, 'any')

    def test_navigation(self):
        global_access = self.nodes['global_access']
        self.assertEqual(global_access.statement(), global_access)
        l_sibling = global_access.previous_sibling()
        # check taking parent if child is not a stmt
        self.assertIsInstance(l_sibling, nodes.Assign)
        child = global_access.args.args[0]
        self.assertEqual(l_sibling, child.previous_sibling())
        r_sibling = global_access.next_sibling()
        self.assertIsInstance(r_sibling, nodes.ClassDef)
        self.assertEqual(r_sibling.name, 'YO')
        self.assertEqual(r_sibling, child.next_sibling())
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
        func = tree.down().down()
        self.assertEqual(func.args.format_args(), 'a, b, c, d')

    def test_four_args(self):
        four_args = self.nodes['four_args']
        self.assertEqual(four_args.args.args, ['a', ('b', 'c', 'd')])
        self.assertEqual(four_args.type, 'function')

    def test_format_args(self):
        make_class = self.nodes2['make_class']
        self.assertEqual(make_class.args.format_args(),
                         'any, base=data.module.YO, *args, **kwargs')
        four_args = self.nodes['four_args']
        self.assertEqual(four_args.args.format_args(), 'a, b, c, d')

    def test_is_generator(self):
        not_a_generator = self.nodes2['not_a_generator']
        self.assertFalse(not_a_generator.is_generator())
        generator = self.nodes2['generator']
        self.assertTrue(generator.is_generator())
        make_class = self.nodes2['make_class']
        self.assertFalse(make_class.is_generator())

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
        lmbd = astroid.down().down().down().down()
        self.assertEqual('%s.<lambda>' % __name__, lmbd.parent.value.qname())

    def test_argnames(self):
        if sys.version_info < (3, 0):
            code = 'def f(a, (b, c), *args, **kwargs): pass'
        else:
            code = 'def f(a, b, c, *args, **kwargs): pass'
        astroid = builder.parse(code, __name__)
        f = astroid.down().down()
        self.assertEqual(f.argnames(), ['a', 'b', 'c', 'args', 'kwargs'])



class ClassNodeTest(ModuleLoader, unittest.TestCase):

    def test_navigation(self):
        yo = self.nodes['YO']
        self.assertEqual(yo.statement(), yo)
        l_sibling = yo.previous_sibling()
        self.assertTrue(isinstance(l_sibling, nodes.FunctionDef), l_sibling)
        self.assertEqual(l_sibling.name, 'global_access')
        r_sibling = yo.next_sibling()
        self.assertIsInstance(r_sibling, nodes.ClassDef)
        self.assertEqual(r_sibling.name, 'YOUPI')

    def test_function_with_decorator_lineno(self):
        data = '''
            @f(a=2, 
               b=3)
            def g1(x): #@
                print(x)

            @f(a=2, 
               b=3)
            def g2(): #@
                pass
        '''
        g1, g2 = test_utils.extract_node(data)
        self.assertEqual(g1.fromlineno, 4)
        self.assertEqual(g1.tolineno, 5)
        self.assertEqual(g2.fromlineno, 9)
        self.assertEqual(g2.tolineno, 10)


if __name__ == '__main__':
    unittest.main()
