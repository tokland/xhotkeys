import unittest

class AllTestSuite(unittest.TestSuite):
    all_tests = [
        "test_misc",
        "test_xhotkeyslib",
        "test_xhotkeysd",
    ]
    def __init__(self):
        unittest.TestSuite.__init__(self)
        for module_name in self.all_tests:
            module = __import__(module_name, globals())
            self.addTest(module.suite())

if __name__ == '__main__':
    unittest.main(defaultTest='AllTestSuite',
        testRunner=unittest.TextTestRunner(verbosity=2))
