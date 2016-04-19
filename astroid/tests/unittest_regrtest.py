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
