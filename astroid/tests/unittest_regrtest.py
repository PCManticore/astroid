# Licensed under the LGPL: https://www.gnu.org/licenses/old-licenses/lgpl-2.1.en.html
# For details: https://github.com/PyCQA/astroid/blob/master/COPYING.LESSER

import sys
import unittest

import six

from astroid import builder
from astroid.test_utils import require_version, extract_node
from astroid.tests import resources
from astroid import transforms


BUILTINS = six.moves.builtins.__name__


class NonRegressionTests(unittest.TestCase):

    @require_version('3.0')
    def test_nameconstant(self):
        # used to fail for Python 3.4
        astroid = builder.parse("def test(x=True): pass")
        default = astroid.body[0].args.args[0]
        self.assertEqual(default.name, 'x')

    def test_unicode_in_docstring(self):
         # Crashed for astroid==1.4.1
         # Test for https://bitbucket.org/logilab/astroid/issues/273/

         # In a regular file, "coding: utf-8" would have been used.
         node = extract_node(u'''
         from __future__ import unicode_literals

         class MyClass(object):
            def method(self):
                 "With unicode : %s "
         ''' % u"\u2019")

         node.as_string()


if __name__ == '__main__':
    unittest.main()
