import unittest

from kitquen_forge.language import ForgeError, parse, serialize


def ir(commands):
    return [(cmd.op, cmd.target, cmd.args) for cmd in commands]


class LanguageTests(unittest.TestCase):
    def test_examples_are_equivalent(self):
        readable = """import.kln 3d
[create 3d.cube="base"]
base.size=(40,40,20)
base.position=(0,0,0)
base.material.color/#FF6600
[create 3d.hole="opening"]
opening.target/base
opening.diameter=10
scene.export/stl/$model.stl$"""
        compact = """+cube/base
@size/base 40,40,20
@pos/base 0,0,0
@color/base #FF6600
+hole/base d=10
!export/stl model.stl"""
        self.assertEqual(ir(parse(readable)), ir(parse(compact)))

    def test_roundtrip(self):
        script = """# comment
+cube/base size=2
~rotate/base axis=z deg=360 frames=1:120
!timeline 1:120
!export/glb 'my model.glb'"""
        commands = parse(script)
        for readable in (True, False):
            self.assertEqual(ir(parse(serialize(commands, readable))), ir(commands))

    def test_errors(self):
        for command in (
            "os.system('test')",
            "+cube/x size=nan",
            "+cube/x size=0",
            "+cube/x size=1 size=2",
            "@pos/x 1,2",
            "@color/x #xyz",
            "~move/x from=0,0,0 to=1,2,3 frames=5:1",
            "' '",
            "!export/obj file.obj\n+cube/x",
            '[create 3d.hole="opening"]',
        ):
            with self.subTest(command=command), self.assertRaises(ForgeError):
                parse(command)

    def test_source_line(self):
        with self.assertRaises(ForgeError) as found:
            parse("\n# first\n+cube/base\n@unknown/base 1")
        self.assertEqual(found.exception.line, 4)
