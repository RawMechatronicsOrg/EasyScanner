"""Write every printable part in its print orientation: own parts to export/,
the phone clamp to phone-clamp/export/.

CadQuery models are built with their default PARAMS and dropped onto z=0; the
downloaded screw halves and knurled head are only re-oriented.
Run from this folder with CadQuery installed: python export_stl.py
"""
from pathlib import Path
import sys

import cadquery as cq
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'models'))
sys.path.insert(0, str(ROOT / 'phone-clamp' / 'models'))
import ball_mount  # noqa: E402
import flange_clip  # noqa: E402
import laser_clamp_cross  # noqa: E402
import phone_clamp_lower  # noqa: E402
import phone_clamp_upper  # noqa: E402
from mesh_solid import PARTS  # noqa: E402

OUT = ROOT / 'export'
CLAMP_OUT = ROOT / 'phone-clamp' / 'export'
STL = np.dtype([('normal', '<f4', (3,)), ('v', '<f4', (3, 3)), ('attr', '<u2')])


def model(module, path):
    shape = module.build({k: v['default'] for k, v in module.PARAMS.items()})
    shape = shape.translate(cq.Vector(0, 0, -shape.BoundingBox().zmin))
    shape.exportStl(str(path), 0.01, 0.1)


def ball_mount_parts():
    """Clip walls down, ball flat down, nut thread entry down, laser clamp flat top down."""
    d, parts = ball_mount.parts({k: v['default'] for k, v in ball_mount.PARAMS.items()})
    for name, shape in parts.items():
        if name in ('ball', 'laser_clamp'):
            shape = shape.rotate(cq.Vector(0, 0, d['zc']), cq.Vector(1, 0, d['zc']), 180)
        shape = shape.translate(cq.Vector(0, 0, -shape.BoundingBox().zmin))
        shape.exportStl(str(OUT / f'ball_mount_{name}.stl'), 0.01, 0.1)


def mesh(source, name, axes):
    """axes: new (x, y, z) as (index, sign) of the old axes; result centred in XY on z=0."""
    data = (PARTS / source).read_bytes()
    tris = np.frombuffer(data, dtype=STL, offset=84).copy()
    for key in ('v', 'normal'):
        old = tris[key].copy()
        for i, (j, sign) in enumerate(axes):
            tris[key][..., i] = sign * old[..., j]
    v = tris['v']
    lo, hi = v.min((0, 1)), v.max((0, 1))
    v -= np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    (CLAMP_OUT / name).write_bytes(data[:84] + tris.tobytes())


if __name__ == '__main__':
    model(phone_clamp_lower, CLAMP_OUT / 'updated_phone_clamp_lower_profile_slot.stl')  # walls down, tooth feet on the bed
    model(phone_clamp_upper, CLAMP_OUT / 'updated_phone_clamp_upper_no_plate.stl')      # flat sole down
    mesh('updated_phone_clamp_screw_bottom_hole.stl', 'screw_bottom_print_orientation.stl', ((0, 1), (1, -1), (2, -1)))
    mesh('updated_phone_clamp_screw_top_hole.stl', 'screw_top_print_orientation.stl', ((0, 1), (1, 1), (2, 1)))
    mesh('updated_phone_clamp_knurl_head_hole.stl', 'knurled_head_upright.stl', ((0, 1), (2, -1), (1, 1)))
    ball_mount_parts()
    model(laser_clamp_cross, OUT / 'ball_mount_laser_clamp_cross.stl')                    # boss down
    model(flange_clip, OUT / 'ball_mount_flange_clip.stl')                                # collet up, as built
    print('\n'.join(sorted(str(p.relative_to(ROOT)) for p in (*OUT.glob('*.stl'), *CLAMP_OUT.glob('*.stl')))))
