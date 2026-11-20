# Materials and lights

```text
@color/tile #FF6600
@material/tile color=#FF6600 roughness=0.4 metallic=0.1 alpha=1
+light/key type=point power=500 color=#FFFFFF
@pos/key 2,1,4
@energy/key 800
```

Forge edits the first mesh material slot and uses a Principled BSDF. Hex colors are interpreted as sRGB. Roughness, metallic, and alpha range from 0 to 1. Transparency depends on Blender material and renderer settings. Light types are point, sun, spot, and area. Blender defines the energy units for each type.
