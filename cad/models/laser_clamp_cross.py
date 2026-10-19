"""First laser clamp of the ball mount (2026-10-18): the laser lies across the screw.

A split ring for a 12 mm laser module on top of a 15 mm boss; a vertical through
hole for an M5 socket head cap screw: the head drops in through the split and sits
in a counterbore under the bore, the screw runs through the boss into the ball. Fit
the screw first, then the laser. Same ball, nut and clip as ball_mount.py; this is
the alternative to its L-shaped laser_clamp.

Recovered from the 2026-10-18 code (matches the mesh on the 18.10 plates) and
reprinted 2026-10-19 with the bore opened to the laser's size: 11.8 gripped too hard.
Printed boss down (export_stl.py).
"""
import math

import cadquery as cq

import ball_mount as bm
from ball_mount import BOSS_D, CLAMP_LEN, HEAD_D, HEAD_H, M5_CLEAR, SPLIT

PARAMS = {k: bm.PARAMS[k] for k in ('ball_d', 'seat_gap', 'laser_d', 'boss')}
PARAMS['laser_grip'] = {**bm.PARAMS['laser_grip'], 'default': 0.0}   # bore = laser_d - grip

CLAMP_WALL, CLAMP_FLOOR = 2.5, 2.0


def laser_clamp(p, d):
    z0 = d['zc'] + d['flat_z']                      # boss bottom on the ball flat
    bore_r = (p['laser_d'] - p['laser_grip']) / 2
    ring_r = bore_r + CLAMP_WALL
    pocket = z0 + p['boss'] + CLAMP_FLOOR           # counterbore floor
    axis_z = pocket + HEAD_H + bore_r               # laser axis
    L = CLAMP_LEN
    ring = cq.Solid.makeCylinder(ring_r, L, cq.Vector(0, -L / 2, axis_z), cq.Vector(0, 1, 0))
    # The boss runs its full length at BOSS_D, then a 45 deg flare out to the block's corners
    # (no flat ledge when printed boss-down), then the block under the ring.
    flare_z = z0 + p['boss']
    flare_h = math.hypot(ring_r, L / 2) - BOSS_D / 2
    block = cq.Solid.makeBox(2 * ring_r, L, axis_z - flare_z - flare_h, cq.Vector(-ring_r, -L / 2, flare_z + flare_h))
    boss = cq.Solid.makeCylinder(BOSS_D / 2, p['boss'] + .1, cq.Vector(0, 0, z0))
    flare = cq.Solid.makeCone(BOSS_D / 2, BOSS_D / 2 + flare_h, flare_h, cq.Vector(0, 0, flare_z)).intersect(
        cq.Solid.makeBox(2 * ring_r, L, flare_h, cq.Vector(-ring_r, -L / 2, flare_z)))
    body = ring.fuse(block, boss, flare)
    body = body.cut(cq.Solid.makeCylinder(bore_r, L + 2, cq.Vector(0, -L / 2 - 1, axis_z), cq.Vector(0, 1, 0)))
    # teardrop top (45 deg flanks up to the split): printed boss-down the bore needs no support
    # inside, which would scar the surface that grips the laser; the grip still wraps 270 deg
    k = bore_r / math.sqrt(2)
    plane = cq.Plane(origin=(0, L / 2 + 1, 0), xDir=(1, 0, 0), normal=(0, -1, 0))
    body = body.cut(cq.Workplane(plane).polyline([(-k, axis_z + k), (0, axis_z + 2 * k), (k, axis_z + k)])
                    .close().extrude(L + 2).val())
    body = body.cut(cq.Solid.makeBox(SPLIT, L + 2, ring_r, cq.Vector(-SPLIT / 2, -L / 2 - 1, axis_z)))
    body = body.cut(cq.Solid.makeCylinder(HEAD_D / 2, axis_z + ring_r - pocket + 1, cq.Vector(0, 0, pocket)))
    body = body.cut(cq.Solid.makeCylinder(M5_CLEAR / 2, pocket - z0 + 1, cq.Vector(0, 0, z0 - .5)))
    edge = [e for e in body.Edges() if abs(e.Center().z - z0) < 1e-6]   # boss foot
    return body.chamfer(.5, None, edge).clean() if edge else body.clean()


def build(p):
    return laser_clamp(p, bm.dims(p))
