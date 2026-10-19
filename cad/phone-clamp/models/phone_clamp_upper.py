"""Tripod Mobile Phone Clamp V2, upper part (slim-phone variant) with the tripod-nut plate removed.

The plate (38 x 20 mm block with the blind 12 mm hole for the tripod nut, plus
the sloped buttress behind it) is cut away down to the clamping jaw, and the
jaw's centre is rebuilt from the surfaces measured on its exposed flanks, so
the front reads as if the plate never existed. The slide bar stays.

Measured on the STL (mm, part coordinates; jaw front faces -Y):
  - jaw front, plan: arc R 188 about a vertical axis (sd 0.02 across x 16..24);
  - jaw front, profile at x=0: ~48-deg bottom chamfer y = -1.0974 z - 73.8535
    from the floor z=2.5 to z=3.588, then an arc centre (y -36.817, z 6.989)
    R 41.116 (residual 0.005);
  - jaw top in the centre: cylinder along Y, axis z 49.612, R 38.609 (lowest z 11.003);
  - front-top edge: rounded, ~1-1.5 mm.
"""
import cadquery as cq

from mesh_solid import PARTS, cached_solid

STL = PARTS / 'updated_phone_clamp_upper.stl'

PARAMS = {
    'top_round': {'default': 1.2, 'min': 0.3, 'max': 2.0, 'step': 0.1},
}

FLOOR = 2.5
PLAN_R = 188.0
CHAMFER = (-1.0974, -73.8535)          # y = k z + b
ARC_C, ARC_R = (-36.8167, 6.9887), 41.1157  # (y, z), radius
JOIN_Z = 3.5884
TOP_AXIS_Z, TOP_R = 49.612, 38.609
VERTEX_Y = ARC_C[0] - ARC_R            # most forward point of the profile
REBUILD_X = 16.5                       # half-width rebuilt from the measured surfaces
PLATE_Y = -78.3                        # everything in front of this is plate only
JAW_BACK_Y = -72.2                     # seam with the kept jaw; at -71.8 the fuse leaves a 2 um crack


def profile_y(z):
    if z <= JOIN_Z:
        return CHAMFER[0]*z + CHAMFER[1]
    return ARC_C[0] - (ARC_R**2 - (z - ARC_C[1])**2) ** .5


def jaw_centre(top_round):
    # Profile in the x=0 plane, revolved about a vertical axis to give the plan arc.
    z0, z1 = FLOOR - 1, 20.0
    pts = [cq.Vector(0, profile_y(z), z) for z in (z0, JOIN_Z, 12.0, z1)]
    back = JAW_BACK_Y + 10
    wire = cq.Wire.assembleEdges([
        cq.Edge.makeLine(pts[0], pts[1]),
        cq.Edge.makeThreePointArc(pts[1], pts[2], pts[3]),
        cq.Edge.makeLine(pts[3], cq.Vector(0, back, z1)),
        cq.Edge.makeLine(cq.Vector(0, back, z1), cq.Vector(0, back, z0)),
        cq.Edge.makeLine(cq.Vector(0, back, z0), pts[0]),
    ])
    axis_y = VERTEX_Y + PLAN_R
    front = (cq.Solid.revolve(wire, [], 24, cq.Vector(0, axis_y, 0), cq.Vector(0, axis_y, 1))
             .rotate(cq.Vector(0, axis_y, 0), cq.Vector(0, axis_y, 1), -12))
    box = cq.Solid.makeBox(2*REBUILD_X, JAW_BACK_Y - (PLATE_Y - 2), TOP_AXIS_Z - FLOOR,
                           cq.Vector(-REBUILD_X, PLATE_Y - 2, FLOOR))
    top = cq.Solid.makeCylinder(TOP_R, 40, cq.Vector(0, PLATE_Y - 5, TOP_AXIS_Z), cq.Vector(0, 1, 0))
    block = front.intersect(box).cut(top)
    edge = [e for e in block.Edges()
            if e.BoundingBox().xlen > 2*REBUILD_X - .1 and e.Center().z > FLOOR + 5 and e.Center().y < JAW_BACK_Y - 2]
    return block.fillet(top_round, edge)


def build(p):
    part = cached_solid(STL)
    plate = cq.Solid.makeBox(100, 50, 50, cq.Vector(-50, PLATE_Y - 50, -10))
    centre = cq.Solid.makeBox(2*REBUILD_X, JAW_BACK_Y - PLATE_Y, 50, cq.Vector(-REBUILD_X, PLATE_Y, -10))
    return part.cut(plate.fuse(centre)).fuse(jaw_centre(p['top_round'])).clean()
