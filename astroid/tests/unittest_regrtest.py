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
import sys
import unittest
import textwrap

import six

from astroid import MANAGER, Instance, nodes
from astroid.builder import AstroidBuilder
from astroid import exceptions
from astroid.interpreter import lookup
from astroid.manager import AstroidManager
from astroid import raw_building
from astroid.test_utils import require_version, extract_node, bootstrap
from astroid.tests import resources
from astroid import transforms


BUILTINS = six.moves.builtins.__name__


class NonRegressionTests(resources.AstroidCacheSetupMixin,
                         unittest.TestCase):

    def setUp(self):
        sys.path.insert(0, resources.find('data'))
        MANAGER.always_load_extensions = True
        MANAGER.astroid_cache[BUILTINS] = self._builtins

    def tearDown(self):
        # Since we may have created a brainless manager, leading
        # to a new cache builtin module and proxy classes in the constants,
        # clear out the global manager cache.
        MANAGER.clear_cache()
        bootstrap(self._builtins)
        MANAGER.always_load_extensions = False
        sys.path.pop(0)
        sys.path_importer_cache.pop(resources.find('data'), None)

    def brainless_manager(self):
        manager = AstroidManager()
        # avoid caching into the AstroidManager borg since we get problems
        # with other tests :
        manager.__dict__ = {}
        manager._failed_import_hooks = []
        manager.astroid_cache = {}
        manager._mod_file_cache = {}
        manager._transform = transforms.TransformVisitor()
        manager.clear_cache() # trigger proper bootstraping
        bootstrap()
        return manager

    @require_version('3.0')
    def test_nameconstant(self):
        # used to fail for Python 3.4
        builder = AstroidBuilder()
        astroid = builder.string_build("def test(x=True): pass")
        default = astroid.body[0].args.args[0]
        self.assertEqual(default.name, 'x')
        self.assertEqual(next(default.infer()).value, True)

    def test_unicode_in_docstring(self):
        # Crashed for astroid==1.4.1
        # Test for https://bitbucket.org/logilab/astroid/issues/273/

        # In a regular file, "coding: utf-8" would have been used.
        node = extract_node(u'''
        from __future__ import unicode_literals

        class MyClass(object):
            def method(self):
                "With unicode : %s "

        instance = MyClass()
        ''' % u"\u2019")

        next(node.value.infer()).as_string()

    def test_qname_not_on_generatorexp(self):
        node = extract_node('''(i for i in range(10))''')
        with self.assertRaises(AttributeError):
            node.qname


if __name__ == '__main__':
    unittest.main()
