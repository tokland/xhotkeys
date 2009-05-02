#!/usr/bin/python
import unittest

from xhotkeys import misc

class XhotkeysMiscTest(unittest.TestCase):
    def test_struct(self):
        struct = misc.Struct("mystruct", var1=1, var2=2)
        self.assertEqual(1, struct.var1)
        self.assertEqual(2, struct.var2)
        self.assertRaises(AttributeError, lambda: struct.var3)
        struct.var1 = 11
        self.assertEqual(11, struct.var1)

    def test_partial_function(self):
        def function(a, b, c=0):
            return a + b + c
        function1 = misc.partial_function(function, 1)
        self.assertEqual(3, function1(2))
        self.assertEqual(8, function1(2, c=5))
        
        function2 = misc.partial_function(function, 1, c=2)
        self.assertEqual(6, function2(3))

    def test_first(self):
        lst = [1, 2, 3, 4]
        self.assertEqual(1, misc.first(lst))
        self.assertEqual(1, misc.first(iter(lst)))
        self.assertEqual(None, misc.first([]))
     
                                                        
def suite():
    return unittest.TestLoader().loadTestsFromTestCase(XhotkeysMiscTest)
 
if __name__ == '__main__':
    unittest.main()
