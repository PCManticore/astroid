# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
import unittest

from astroid import builder
from astroid import nodes
from astroid import test_utils
from astroid import util


class InferenceUtil(unittest.TestCase):

    def test_not_exclusive(self):
        code = """
        x = 10 #@
        for x in range(5):
            print (x)

        if x > 0:
            print ('#' * x)
        """
        module = builder.parse(code, __name__, __file__)
        xass1 = test_utils.extract_node(code)
        assert xass1.lineno == 2
        xnames = [n for n in module.nodes_of_class(nodes.Name) if n.name == 'x']
        assert len(xnames) == 3
        assert xnames[1].lineno == 6
        self.assertEqual(util.are_exclusive(xass1, xnames[1]), False)
        self.assertEqual(util.are_exclusive(xass1, xnames[2]), False)

    def test_if(self):
        nodes = test_utils.extract_node('''
        if 1:
            a = 1 #@
            a = 2 #@
        elif 2:
            a = 12 #@
            a = 13 #@
        else:
            a = 3 #@
            a = 4 #@
        ''')
        a1, a2, a3, a4, a5, a6 = nodes
        self.assertEqual(util.are_exclusive(a1, a2), False)
        self.assertEqual(util.are_exclusive(a1, a3), True)
        self.assertEqual(util.are_exclusive(a1, a5), True)
        self.assertEqual(util.are_exclusive(a3, a5), True)
        self.assertEqual(util.are_exclusive(a3, a4), False)
        self.assertEqual(util.are_exclusive(a5, a6), False)

    def test_try_except(self):
        nodes = test_utils.extract_node('''
        try:
            def exclusive_func2(): #@
                "docstring"
        except TypeError:
            def exclusive_func2(): #@
                "docstring"
        except:
            def exclusive_func2(): #@
                "docstring"
        else:
            def exclusive_func2(): #@
                "this one redefine the one defined line 42"
        ''')
        f1, f2, f3, f4 = nodes
        self.assertEqual(util.are_exclusive(f1, f2), True)
        self.assertEqual(util.are_exclusive(f1, f3), True)
        self.assertEqual(util.are_exclusive(f1, f4), False)
        self.assertEqual(util.are_exclusive(f2, f4), True)
        self.assertEqual(util.are_exclusive(f3, f4), True)
        self.assertEqual(util.are_exclusive(f3, f2), True)

        self.assertEqual(util.are_exclusive(f2, f1), True)
        self.assertEqual(util.are_exclusive(f4, f1), False)
        self.assertEqual(util.are_exclusive(f4, f2), True)


if __name__ == '__main__':
    unittest.main()
