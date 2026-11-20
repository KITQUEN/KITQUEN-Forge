# Kitlean 3D 0.1

Each nonempty line contains one command. Whole lines starting with `#` or `//` are comments. Hex colors remain available after an operation. Each batch accepts 1–128 commands and up to 32 KiB of UTF‑8 text.

```text
+primitive/alias size=1
@pos/alias 1,2,3
?/alias
-/alias
~move/alias from=1,2,3 to=0,0,0 frames=1:24
!timeline 1:24
```

`+` creates, `@` modifies, `?` inspects, `-` deletes, `~` animates and `!` performs a scene command. Targets are aliases or persistent 32-character lowercase hex IDs. Create aliases start with an ASCII letter and contain up to 63 letters, digits, underscores, or hyphens. Numeric values are finite. Vectors contain exactly three components, and size also permits a uniform scalar. Color is `#RRGGBB`. Single or double quoting can group filenames with spaces.

Canonical readable commands use `create.`, `set.`, `inspect`, `delete`, `animate.`, and `scene.` in place of prefix symbols. `forge_validate` converts in either direction. The parser also accepts these readable forms.

```text
import.kln 3d
[create 3d.cube="base"]
base.size=(4,4,2)
base.position=(0,0,0)
base.material.color/#FF6600
[create 3d.hole="opening"]
opening.target/base
opening.diameter=1
scene.export/stl/$model.stl$
```

A hole block names the operation for readability. It modifies the target mesh, leaving no cutter object. The lexer and schema produce a shared intermediate representation before Blender executes anything. This dialect is independent of other Kitlean implementations.
