import unittest

from conans.test.utils.tools import TestClient
from parameterized.parameterized import parameterized


class ConanfileHelpersTest(unittest.TestCase):

    @parameterized.expand([(True,), (False,)])
    def test_helpers_same_name(self, scope_imports):
        helpers = '''
def build_helper(output):
    output.info("Building %d!")
    '''
        other_helper = '''
def source_helper(output):
    output.info("Source %d!")
    '''

        if scope_imports:
            file_content = '''from conans import ConanFile
from myhelper import build_helper
from myhelpers.other import source_helper

class ConanFileToolsTest(ConanFile):
    exports = "*"

    def source(self):
        source_helper(self.output)

    def build(self):
        build_helper(self.output)
'''
        else:
            file_content = '''from conans import ConanFile
import myhelper
from myhelpers import other

class ConanFileToolsTest(ConanFile):
    exports = "*"

    def source(self):
        other.source_helper(self.output)

    def build(self):
        myhelper.build_helper(self.output)
'''

        def files(number):
            return {"myhelper.py": helpers % number,
                    "myhelpers/__init__.py": "",
                    "myhelpers/other.py": other_helper % number,
                    "conanfile.py": file_content}

        client = TestClient()
        client.save(files(1))
        client.run("export . test/1.9@user/testing")
        client.save(files(2), clean_first=True)
        client.run("export . test2/2.3@user/testing")

        files = {"conanfile.txt": """[requires]
                                    test/1.9@user/testing\n
                                    test2/2.3@user/testing"""}
        client.save(files, clean_first=True)
        client.run("install . --build")
        self.assertIn("test/1.9@user/testing: Building 1!", client.out)
        self.assertIn("test/1.9@user/testing: Source 1!", client.out)
        self.assertIn("test2/2.3@user/testing: Building 2!", client.out)
        self.assertIn("test2/2.3@user/testing: Source 2!", client.out)
