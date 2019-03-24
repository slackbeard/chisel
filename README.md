## Chisel

A Blender tool for making chisel effects on a mesh.

![Chisel demo](/cube_demo.gif)

The addon works by running a bevel on the selected edges and then collapsing the geometry of each loose end, resulting in tapered end points.

I use this tool for quick effects like cracks:

![Log demo](/log_demo.gif)

and creases:

![Subsurf demo](/subsurf_demo.gif)

### Usage

1. Run chisel.py in Blender to register the operator

1. In Edit mode, select 2 or more connected edges

1. Press space to bring up the search box

1. Type 'Chisel' and run it

### Controls

**Move Mouse Right/Left:** Width increase/decrease

**Move Mouse Up/Down:** Length increase/decrease(by moving the end points outward/inward)

**Scroll Mouse Wheel Down/Up:** Depth increase/decrease

**Left Click:** Finished

**Right Click:** Cancel

**X:** Only change Width

**Y:** Only change Length

### Known Issues:

* For very small geometry, the newly created edges will overshoot adjacent edges and make a huge mess

* UVs will stretch as you increase the width / length of the chisel
