# Keyframe animation

```text
~move/box from=0,0,0 to=10,0,0 frames=1:120
~scale/box from=1 to=2,2,2 frames=1:120
~rotate/box axis=z deg=360 frames=1:120
!timeline 1:120
```

Movement and scale set endpoint values. Rotation adds the requested degrees to the object's current Euler rotation on one axis. Keys use Blender's default interpolation. The commands retain other channels from an existing action. Playback and curve editing use Blender's timeline. There is no Kitlean command for rigs, constraints, or playback in 0.1.
