"""Tripod Mobile Phone Clamp V2, lower (base) part, slim-phone variant,
with a snap-on channel for a 16 x 13 mm aluminium profile under the sole.

The channel walls (profile_clip.py) hang from the flat sole (z=0, flat for
|x| <= 15, y -29.5..36) and run along the clamp axis (Y). The knurled screw
head hangs 3 mm below the sole (y 30..49, beyond the part's end), so the
profile's top stops head_gap below the sole on a spacer under the body and
passes under the head.
"""
from pathlib import Path
import sys

import cadquery as cq

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'models'))  # profile_clip is shared with cad/models
import profile_clip  # noqa: E402
from mesh_solid import PARTS, cached_solid  # noqa: E402

STL = PARTS / 'updated_phone_clamp_lower.stl'

PARAMS = {
    **profile_clip.PARAMS,
    'head_gap': {'default': 3.5, 'min': 0.0, 'max': 6.0, 'step': 0.1},  # head bottom is at z -2.99
}

SOLE_Y = (-29.5, 35.0)   # walls run the full flat sole, under the jaw too
HEAD_Y = 30.0            # knurled head from here on: no spacer under it
# Sole edge is rounded from x 15.49 (z 0) to 17.4 (z 2.5); below z 0.6 the round is flatter
# than 45 deg and would need support printed walls-down, so the walls swallow it up to here.
EDGE_X, EDGE_Z = 16.6, 0.7
OVERLAP = 0.3            # reach into the 2.4 mm floor so the fuse is not coplanar


def channel(p):
    gap = p['head_gap']
    body = profile_clip.walls(p, SOLE_Y, -gap, (EDGE_X, EDGE_Z), EDGE_Z)
    if gap > 0:
        s = p['slot_width'] / 2
        body = body.fuse(cq.Solid.makeBox(2*s + .2, HEAD_Y - SOLE_Y[0], gap + OVERLAP,
                                          cq.Vector(-s - .1, SOLE_Y[0], -gap)))
    return body


def build(p):
    return cached_solid(STL).fuse(channel(p)).clean()
