"""Snap-on channel for the 16 x 13 mm aluminium profile, shared by every part
that clips onto it (phone clamp base, ball mount).

Two walls hang below a flat sole and run along Y. The profile's top rests on
`ceiling`; a tooth at the foot of each wall catches its bottom face, and the
lead-in under the tooth spreads the walls when the part is pushed down onto
the profile. Each wall's outer face is a slightly convex arc from the foot up
to `edge` (a point on the part's side), thick and stiff at the root, `wall`
thick at the tooth; printed walls-down it has no flat overhang.
"""
import math

import cadquery as cq

PARAMS = {
    'slot_width': {'default': 16.4, 'min': 15.8, 'max': 17.2, 'step': 0.1},  # profile 16 + 0.2 per side
    'slot_depth': {'default': 13.2, 'min': 12.6, 'max': 14.0, 'step': 0.1},  # profile 13 + 0.2
    'wall': {'default': 2.2, 'min': 1.6, 'max': 3.5, 'step': 0.1},  # at the foot
    'bulge': {'default': 0.8, 'min': 0.0, 'max': 2.5, 'step': 0.1},  # outer face arc vs straight
    # 0.6 = 0.4 mm wall travel, ~1.6 % peak strain at the wall root (across layers when
    # printed walls-down); 0.7 gives ~2.0 %, too close to PLA's limit.
    'hook': {'default': 0.6, 'min': 0.3, 'max': 1.5, 'step': 0.1},
}
TIP = 0.3       # flat on the tooth tip
LEAD_IN = 30    # deg from vertical


def foot_z(p, ceiling):
    """z of the walls' feet, their lowest point (on the bed when printed walls-down)."""
    return ceiling - p['slot_depth'] - TIP - p['hook'] / math.tan(math.radians(LEAD_IN))


def walls(p, y_range, ceiling, edge, top):
    """Both walls, x-symmetric, from y_range[0] to y_range[1].

    ceiling: z of the profile's top face; edge: (x, z) where the outer arc meets
    the part's side; top: z the walls reach up to inside the part (>= edge z).
    """
    s, w, h = p['slot_width'] / 2, p['wall'], p['hook']
    catch = ceiling - p['slot_depth']
    foot = foot_z(p, ceiling)
    ax, az = s + w, foot
    bx, bz = edge
    length = math.hypot(bx - ax, bz - az)
    mid = ((ax + bx) / 2 + p['bulge'] * (bz - az) / length, (az + bz) / 2 - p['bulge'] * (bx - ax) / length)
    plane = cq.Plane(origin=(0, y_range[1], 0), xDir=(1, 0, 0), normal=(0, -1, 0))
    sketch = (cq.Workplane(plane).moveTo(s, top)
              .lineTo(s, catch).lineTo(s - h, catch).lineTo(s - h, catch - TIP).lineTo(s, foot)
              .lineTo(ax, az))
    sketch = sketch.threePointArc(mid, (bx, bz)) if p['bulge'] > 0 else sketch.lineTo(bx, bz)
    if top > bz:
        sketch = sketch.lineTo(bx, top)
    return sketch.close().extrude(y_range[1] - y_range[0]).mirror('YZ', union=True).val()
