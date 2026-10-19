"""Ball-head mount for the line laser on the 16 x 13 mm aluminium profile.

Four printed parts, shown assembled (nut backed off, i.e. ball free):
  - clip: 30 x 30 block with the profile snap channel (profile_clip.py) under it
    and a collet on top: spherical seat, four slotted fingers wrapping the ball
    a little past its equator (it snaps in), coarse external thread P3 below;
  - ball: sphere with a flat on top and a hole to its centre, tapped M5 after printing;
  - nut: internal thread plus an internal cone matching the fingers' taper;
    screwing it down squeezes the fingers onto the ball;
  - laser clamp, L-shaped: a column on a 15 mm boss with a vertical through hole
    for an M5 socket head cap screw (head in a counterbore open at the top, the
    screw runs through the boss into the ball; the head seats on a 45 deg cone), and
    a link out to a vertical split ring for a 12 mm laser module, bored slightly
    under size so the plastic grips it. The link joins the column and ring outlines
    by their outer tangents, has a through slot and a 45 deg brace onto the boss; the
    ring wall thins from the root to the lips. The screw and laser axes are parallel;
    the link puts the laser laser_clear outside the nut in plan (28 mm between the
    axes by default), so the module hangs past the nut.

With the defaults an M5 x 25 screw passes ~17 mm of clamp (the head sits 0.35 mm
down its seating cone) and engages ~7.95 mm of the ball (the hole is 8.3 deep from the flat).

Coordinates: profile along Y under the clip, collet axis = Z, clip sole at z=0.
Print orientations (export_stl.py): clip walls down, ball flat down, nut thread
entry down, laser clamp upside down (flat top face on the bed).
"""
import math

import cadquery as cq

import profile_clip

PARAMS = {
    **profile_clip.PARAMS,
    'ball_d': {'default': 20.0, 'min': 16.0, 'max': 30.0, 'step': 0.5},
    'seat_gap': {'default': 0.15, 'min': 0.0, 'max': 0.4, 'step': 0.05},     # ball in the seat, radial
    'thread_gap': {'default': 0.3, 'min': 0.1, 'max': 0.6, 'step': 0.05},    # nut on collet, radial
    'laser_d': {'default': 12.0, 'min': 8.0, 'max': 20.0, 'step': 0.1},
    'laser_grip': {'default': 0.2, 'min': 0.0, 'max': 0.6, 'step': 0.05},    # bore = laser_d - grip
    'laser_clear': {'default': 4.0, 'min': 0.0, 'max': 15.0, 'step': 0.5},   # laser body to the nut's outline, in plan
    'boss': {'default': 15.0, 'min': 8.0, 'max': 25.0, 'step': 0.5},
}

BLOCK, PLATE = 30.0, 4.0       # clip block footprint (x, y) and plate thickness above the profile
COLLET_WALL = 2.35             # seat to thread root
PITCH, DEPTH = 3.0, 1.5        # coarse thread
CREST = 0.6                    # crest flat; 30 deg flanks
# Collet from the plate up: thread, a plain neck the nut's cone travels down over,
# then the fingers' outer cone the nut squeezes. The ball sits so the finger tips
# wrap it to zc + 0.3 R: opening ~3 % under the ball, it snaps in.
THREAD_LEN, NECK, CONE_LEN = 7.0, 3.0, 5.0
FINGERS_ABOVE = 0.3
TIP_WALL = 1.8
SLOTS, SLOT_W, SLOT_BELOW = 4, 1.5, 1.0   # slots reach SLOT_BELOW under the thread top
CONE_GAP = 0.15                # nut cone to fingers, radial, nut backed off
NUT_TRAVEL = 2.5               # nominal nut position leaves this much thread to tighten
NUT_WALL, NUT_LIP = 4.0, 1.5
GRIPS, GRIP_R = 12, 2.0
M5_TAP, M5_CLEAR = 4.2, 5.4
HEAD_D, HEAD_H = 9.2, 5.3      # M5 socket head 8.5 x 5 plus clearance
CLAMP_LEN, CLAMP_FLOOR = 16.0, 2.4   # floor under the head, incl. its 1.9 mm cone
JAW_ROOT, JAW_TIP = 2.8, 1.2   # laser ring wall opposite the split and at the lips
SPLIT = 2.4                    # axial split of the laser ring, on its far side
LIP_ROUND, ENTRY = 0.4, 0.5    # rounded lips; lead-in chamfer at both ends of the laser bore
COLUMN_WALL = 2.0              # around the head counterbore
BRACE_FOOT, BRACE_W = 3.0, 9.0   # 45 deg brace under the link meets the boss this far above its foot
ARM_SLOT_W = 7.0               # through slot in the link between the column and the ring
BOSS_D = 11.0


def revolve(points):
    """Solid of revolution about Z from an (r, z) outline."""
    plane = cq.Plane(origin=(0, 0, 0), xDir=(1, 0, 0), normal=(0, -1, 0))
    return cq.Workplane(plane).polyline(points).close().revolve(360, (0, 0, 0), (0, 1, 0)).val()


def ridge(r_root, r_crest, z0, z1, crest):
    """Helical thread ridge, root buried at r_root, crest at r_crest, 30 deg flanks."""
    root = crest + 2 * abs(r_root - r_crest) * math.tan(math.radians(30))
    plane = cq.Plane(origin=(0, 0, z0), xDir=(1, 0, 0), normal=(0, -1, 0))
    profile = cq.Workplane(plane).polyline(
        [(r_root, -root / 2), (r_crest, -crest / 2), (r_crest, crest / 2), (r_root, root / 2)]).close()
    helix = cq.Wire.makeHelix(PITCH, z1 - z0, r_root, center=cq.Vector(0, 0, z0))
    return profile.sweep(helix, isFrenet=True).val()


def dims(p):
    R = p['ball_d'] / 2
    seat = R + p['seat_gap']
    d = dict(R=R, seat=seat, lo=PLATE + .5)
    d['thread_top'] = d['lo'] + THREAD_LEN
    d['cone0'] = d['thread_top'] + NECK
    d['tip'] = d['cone0'] + CONE_LEN
    d['zc'] = d['tip'] - FINGERS_ABOVE * R
    assert d['zc'] - seat >= PLATE + 1, 'ball seat cuts into the plate'
    d['minor'] = seat + COLLET_WALL
    d['major'] = d['minor'] + DEPTH
    d['nut_out'] = d['major'] + NUT_WALL
    d['tip_in'] = math.sqrt(seat ** 2 - (d['tip'] - d['zc']) ** 2)
    d['tip_out'] = d['tip_in'] + TIP_WALL
    d['flat_r'] = BOSS_D / 2 + 0.1
    d['flat_z'] = math.sqrt(R ** 2 - d['flat_r'] ** 2)       # flat height above the ball centre
    return d


def clip(p, d):
    walls = profile_clip.walls(p, (-BLOCK / 2, BLOCK / 2), 0.0, (BLOCK / 2, 0.0), 0.3)
    block = cq.Solid.makeBox(BLOCK, BLOCK, PLATE, cq.Vector(-BLOCK / 2, -BLOCK / 2, 0))
    lo, top = d['lo'], d['thread_top']
    collet = revolve([(0, PLATE - .3), (d['minor'], PLATE - .3), (d['minor'], d['cone0']),
                      (d['tip_out'], d['tip']), (0, d['tip'])])
    span = (lo - PITCH, top + PITCH)
    thread = ridge(d['minor'] - .1, d['major'], *span, CREST).intersect(
        revolve([(0, lo), (d['minor'], lo), (d['major'], lo + DEPTH), (d['major'], top - DEPTH),
                 (d['minor'], top), (0, top)]))
    body = block.fuse(walls, collet, thread)
    body = body.cut(cq.Solid.makeSphere(d['seat'], cq.Vector(0, 0, d['zc']), angleDegrees1=-90, angleDegrees2=90))
    # lead-in chamfer on the finger tips' inner edge, then the slots
    body = body.cut(cq.Solid.makeCone(d['tip_in'] - .3, d['tip_in'] + .8, 1.1, cq.Vector(0, 0, d['tip'] - 1.09)))
    slot_lo = top - SLOT_BELOW
    for i in range(SLOTS // 2):
        cutter = cq.Solid.makeBox(2 * d['major'] + 4, SLOT_W, d['tip'] - slot_lo + 1,
                                  cq.Vector(-d['major'] - 2, -SLOT_W / 2, slot_lo))
        body = body.cut(cutter.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 45 + 180 * i / (SLOTS // 2)))
    return body.clean()


def ball(d):
    R = d['R']
    sphere = cq.Solid.makeSphere(R, cq.Vector(0, 0, d['zc']), angleDegrees1=-90, angleDegrees2=90)
    flat = cq.Solid.makeBox(3 * R, 3 * R, R, cq.Vector(-1.5 * R, -1.5 * R, d['zc'] + d['flat_z']))
    hole = cq.Solid.makeCylinder(M5_TAP / 2, d['flat_z'] + .01, cq.Vector(0, 0, d['zc']))
    entry = cq.Solid.makeCone(M5_TAP / 2, M5_TAP / 2 + .6, .6, cq.Vector(0, 0, d['zc'] + d['flat_z'] - .6))
    return sphere.cut(flat).cut(hole).cut(entry).clean()


def nut(p, d):
    g = p['thread_gap']
    bottom = d['lo'] + NUT_TRAVEL                   # nominal: backed off, cone CONE_GAP off the fingers
    top = d['tip'] + NUT_LIP
    bore, inner = d['major'] + g, d['minor'] + g    # thread root and crest radii of the nut
    out = d['nut_out']
    cone_in = d['minor'] + CONE_GAP
    shoulder = d['cone0'] - (bore - cone_in)        # 45 deg from the thread bore to the cone
    assert shoulder - NUT_TRAVEL > d['thread_top'] - DEPTH + 0.3, 'nut shoulder would hit the collet thread'
    body = revolve([(bore + .8, bottom), (out - .8, bottom), (out, bottom + .8), (out, top - .8), (out - .8, top),
                    (d['tip_out'] + CONE_GAP + .5, top), (d['tip_out'] + CONE_GAP, top - .5),
                    (d['tip_out'] + CONE_GAP, d['tip']), (cone_in, d['cone0']), (bore, shoulder), (bore, bottom + .8)])
    # half a pitch out of phase with the collet's ridge (which starts at lo - PITCH) so they mesh
    start = d['lo'] - PITCH / 2
    thread = ridge(bore + .1, inner, start, shoulder + PITCH, CREST).intersect(
        revolve([(inner - .01, bottom + .8), (bore + .2, bottom + .8), (bore + .2, shoulder - .5),
                 (inner - .01, shoulder - .5)]))
    body = body.fuse(thread)
    for i in range(GRIPS):
        a = 2 * math.pi * i / GRIPS
        body = body.cut(cq.Solid.makeCylinder(GRIP_R, top - bottom + 2, cq.Vector(out * math.cos(a), out * math.sin(a), bottom - 1)))
    return body.clean()


def laser_clamp(p, d):
    """L-shaped: a column over the boss holds the screw (head counterbore open at the
    top); an arm from the same flat top face carries a vertical split ring for the
    laser out past the nut's outline, so the screw and laser axes are parallel."""
    z0 = d['zc'] + d['flat_z']                      # boss bottom on the ball flat
    bore_r = (p['laser_d'] - p['laser_grip']) / 2
    off = d['nut_out'] + p['laser_d'] / 2 + p['laser_clear']   # laser axis, along +X
    pocket = z0 + p['boss'] + CLAMP_FLOOR           # counterbore floor
    top = pocket + HEAD_H                           # flat top face, printed on the bed
    column_r = HEAD_D / 2 + COLUMN_WALL
    L = CLAMP_LEN
    # Ring outline shifted toward the root: the wall thins from JAW_ROOT to JAW_TIP at the
    # lips, roughly as the bending moment falls, so the jaws flex along their whole length
    # instead of hinging at the root, and the grip spreads softly over the laser.
    ecc = (JAW_ROOT - JAW_TIP) / 2
    ring_r = bore_r + (JAW_ROOT + JAW_TIP) / 2
    ring = cq.Solid.makeCylinder(ring_r, L, cq.Vector(off - ecc, 0, top - L))
    ring = ring.cut(cq.Solid.makeCylinder(bore_r, L + 2, cq.Vector(off, 0, top - L - 1)))
    ring = ring.cut(cq.Solid.makeBox(bore_r + JAW_TIP + 1, SPLIT, L + 2,
                                     cq.Vector(off, -SPLIT / 2, top - L - 1)))  # split, far side
    lips = [e for e in cq.Workplane().add(ring).edges('|Z').vals() if e.Center().x > off]
    ring = ring.fillet(LIP_ROUND, lips)
    # Link: the column and ring outlines joined by their outer tangents, as tall as the ring,
    # with a through slot from past the brace up to the ring's root wall. The tangent sides
    # hold the jaws out to ~90 deg off the root: a plane-stress estimate gives about twice
    # the grip of an arm entering only the root, the slot takes back ~15 %.
    cx = off - ecc                                  # ring outline centre
    c = (column_r - ring_r) / cx
    n = (c, math.sqrt(1 - c * c))                   # outer tangent's normal, +Y side
    side = [(column_r * n[0], column_r * n[1]), (cx + ring_r * n[0], ring_r * n[1])]
    band = cq.Workplane(cq.Plane(origin=(0, 0, top - L))).polyline(
        side + [(x, -y) for x, y in reversed(side)]).close().extrude(L).val()
    column = cq.Solid.makeCylinder(column_r, L, cq.Vector(0, 0, top - L))
    link = band.fuse(column).cut(cq.Solid.makeCylinder(bore_r, L + 2, cq.Vector(off, 0, top - L - 1)))
    # 45 deg brace under the link onto the boss; below the boss's foot chamfer it stays inside the boss
    leg = top - L - z0 - BRACE_FOOT
    assert leg > 0, 'laser ring reaches below the brace foot'
    plane = cq.Plane(origin=(0, BRACE_W / 2, 0), xDir=(1, 0, 0), normal=(0, -1, 0))
    brace = cq.Workplane(plane).polyline([(0, top - L + .1), (0, z0 + .5), (BOSS_D / 2 - BRACE_FOOT + .5, z0 + .5),
                                          (BOSS_D / 2 + leg, top - L), (BOSS_D / 2 + leg, top - L + .1)]
                                         ).close().extrude(BRACE_W).val()
    boss = cq.Solid.makeCylinder(BOSS_D / 2, p['boss'] + .1, cq.Vector(0, 0, z0))
    body = boss.fuse(link, brace, ring)
    x0, x1 = BOSS_D / 2 + leg + 1, off - bore_r - JAW_ROOT   # slot: past the brace to the ring's outline
    slot = cq.Workplane(cq.Plane(origin=(0, 0, top - L - 1))).slot2D(x1 - x0, ARM_SLOT_W).extrude(L + 2).val()
    body = body.cut(slot.translate(cq.Vector((x0 + x1) / 2, 0, 0)))
    for z, r0, r1 in ((top - L - .01, bore_r + ENTRY + .01, bore_r), (top - ENTRY, bore_r, bore_r + ENTRY + .01)):
        body = body.cut(cq.Solid.makeCone(r0, r1, ENTRY + .01, cq.Vector(off, 0, z)))   # laser lead-in
    body = body.cut(cq.Solid.makeCylinder(HEAD_D / 2, top - pocket + 1, cq.Vector(0, 0, pocket)))
    # 45 deg cone from the counterbore down to the screw hole: printed upside down a flat ring there
    # is an overhang the slicer supports (12 perimeters cover it, no bridge); the head seats on the cone.
    cone_h = (HEAD_D - M5_CLEAR) / 2
    body = body.cut(cq.Solid.makeCone(M5_CLEAR / 2, HEAD_D / 2, cone_h + .01, cq.Vector(0, 0, pocket - cone_h)))
    body = body.cut(cq.Solid.makeCylinder(M5_CLEAR / 2, pocket - z0 + 1, cq.Vector(0, 0, z0 - .5)))
    edge = [e for e in body.Edges() if abs(e.Center().z - z0) < 1e-6]   # boss foot
    return body.chamfer(.5, None, edge).clean() if edge else body.clean()


def parts(p):
    d = dims(p)
    return d, {'clip': clip(p, d), 'ball': ball(d), 'nut': nut(p, d), 'laser_clamp': laser_clamp(p, d)}


def build(p):
    return cq.Compound.makeCompound(list(parts(p)[1].values()))
