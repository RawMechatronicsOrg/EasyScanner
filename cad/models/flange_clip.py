"""Ball mount clip that grips one flange of the 16 x 13 U profile (the Orbiter phone clamp).

Instead of wrapping the whole profile like ball_mount.clip, it holds only the flange on +X: an
inner jaw runs up inside the U along the flange, the outer wall lies on its outside, a bridge
passes under the flange's free edge and a lip lies on the profile's top over that corner, so the
flange is captured in X and Z and the clip slides on from the profile's free end. A sprung tongue
cut out of the inner jaw presses a bump onto the flange and holds the clip where it is put. The
outer wall carries the collet (ball_mount.collet), its axis across the profile, parallel to the
top, pointing away from the flange. Same ball, nut and laser clamps. The collet axis runs through the
middle of the flange's height and the clip is symmetric along Y, so on a profile turned the other way
up (as in Orbiter, open side toward the phone clamp) the same clip fits turned half a turn about the
collet: the lip then lies on the web's outside and the bridge over the flange's free edge.

Coordinates: built in the collet's frame like ball_mount (collet axis Z, its plate top at
z = PLATE), so the ball, nut and clamps keep their coordinates. The grip is drawn in the
profile's frame (`to_collet`): profile along Y, its top face z=0, the gripped flange x 6.5..8,
z -13..0; that frame's +X goes to the collet's +Z, its +Z to the collet's -X.
Printed as built, collet up: the jaw's and the lip's inner faces on the bed, 45 deg flanks
under the outer wall, the flange slot bridged; no supports.
"""
import cadquery as cq

import ball_mount as bm
from ball_mount import BLOCK, PLATE

PARAMS = {k: bm.PARAMS[k] for k in ('ball_d', 'seat_gap')}

FLANGE_X = (6.5, 8.0)        # the gripped flange, profile frame
FLANGE_EDGE = -13.0          # its free edge
WEB = 1.5                    # the profile's top wall
GAP = 0.2                    # all round the flange, like the snap channels
JAW, JAW_TOP = 2.0, -3.5     # inner jaw thickness; it stops 2 mm under the web
BRIDGE, LIP = 2.5, 2.5       # under the free edge / on the top face
TONGUE_W, TONGUE_T, SLIT = 12.0, 1.2, 1.0   # sprung tongue in the jaw (along Y, thickness, side slits)
TONGUE_ROOT = -12.0          # the slits stop here, over the bridge
BUMP = 0.3                   # interference of the tongue's bump with the flange

X_OUT = FLANGE_X[1] + GAP                    # outer wall's inner face = collet plate's back
X_IN = FLANGE_X[0] - GAP - JAW               # jaw's inner face = lip's end, on the bed
Z_LO = FLANGE_EDGE - GAP - BRIDGE
Z_HI = GAP + LIP
AXIS_Z = (Z_LO + Z_HI) / 2                   # collet axis, mid-grip


def to_collet(shape):
    return shape.translate(cq.Vector(-X_OUT, 0, -AXIS_Z)).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90)


def grip():
    """Profile frame. The envelope runs from the bed face (x = X_IN, the grip's height) out at
    45 deg to the collet plate (BLOCK tall about AXIS_Z), then the flange slot and the passage
    for the profile's top and inside are cut out of it."""
    x_plate = X_OUT + PLATE
    half = BLOCK / 2
    flank = half - (Z_HI - Z_LO) / 2                  # how much taller the plate is than the grip
    assert X_IN + flank <= x_plate, 'no room for the 45 deg flanks'
    plane = cq.Plane(origin=(0, BLOCK / 2, 0), xDir=(1, 0, 0), normal=(0, -1, 0))
    outline = [(X_IN, Z_LO), (X_IN + flank, AXIS_Z - half), (x_plate, AXIS_Z - half),
               (x_plate, AXIS_Z + half), (X_IN + flank, AXIS_Z + half), (X_IN, Z_HI)]
    body = cq.Workplane(plane).polyline(outline).close().extrude(BLOCK).val()
    slot = cq.Solid.makeBox(X_OUT - FLANGE_X[0] + GAP, BLOCK + 2, -FLANGE_EDGE + 2 * GAP,
                            cq.Vector(FLANGE_X[0] - GAP, -BLOCK / 2 - 1, FLANGE_EDGE - GAP))
    top = cq.Solid.makeBox(X_OUT - X_IN + 1, BLOCK + 2, GAP - JAW_TOP,      # the web and the U's inside
                           cq.Vector(X_IN - 1, -BLOCK / 2 - 1, JAW_TOP))
    body = body.cut(slot).cut(top)
    # sprung tongue: slits either side through the jaw, the tongue thinned on its flange side and
    # a half-round bump at its free end reaching BUMP into the flange
    for s in (-1, 1):
        y0 = s * TONGUE_W / 2 + (0 if s > 0 else -SLIT)
        body = body.cut(cq.Solid.makeBox(JAW + 1, SLIT, JAW_TOP - TONGUE_ROOT + 1,
                                         cq.Vector(X_IN - .5, y0, TONGUE_ROOT)))
    jaw_face = FLANGE_X[0] - GAP
    tongue_face = X_IN + TONGUE_T
    body = body.cut(cq.Solid.makeBox(jaw_face - tongue_face + .01, TONGUE_W, JAW_TOP - TONGUE_ROOT + .01,
                                     cq.Vector(tongue_face, -TONGUE_W / 2, TONGUE_ROOT)))
    r = FLANGE_X[0] + BUMP - tongue_face
    bump = cq.Solid.makeCylinder(r, TONGUE_W, cq.Vector(tongue_face, -TONGUE_W / 2, JAW_TOP - r), cq.Vector(0, 1, 0))
    return body.fuse(bump.intersect(cq.Solid.makeBox(r, TONGUE_W, 2 * r,
                                                     cq.Vector(tongue_face, -TONGUE_W / 2, JAW_TOP - 2 * r))))


def build(p):
    return to_collet(grip()).fuse(bm.collet(bm.dims(p))).clean()
