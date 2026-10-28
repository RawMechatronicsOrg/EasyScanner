"""Renders of the Easy Scanner assembly for the README (Blender 4.2+ / 5.x, Cycles).

    blender -b --factory-startup -P render_blender.py -- [--out ../../docs/images] [--samples 192] [--preview]

Shots: three studio views of easy_scanner.glb and a schematic of a scan: the scanner 250 mm above an
A3 ChArUco board (../../charuco/boards) with a vase on it, the laser's light sheet and the stripe it
draws on the board and the vase. The stripe is a shader on the lit surfaces (distance to the laser
plane inside the fan), so it ignores occlusion: it is a picture of the idea, not a simulation.

Scanner frame (mm, as in easy_scanner.step): Z up along the screen normal, so the phone camera and the
laser look down -Z; X runs along the profile toward the laser; the lowest point is at z 0.
"""
import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MM = 0.001
# the laser's rod lens (aperture) and fan; the rod lies along X, so the sheet is the plane x = LASER_X
LASER = Vector((90.9, 61.1, 1.9)) * MM
FAN_HALF_DEG = 35.0
STRIPE_MM = (0.8, 1.6)             # full red within the first, fading out by the second (half widths; drawn wide to read)
BOARD_Z = -250 * MM                # board top in the scan schematic
BOARD_PDF = REPO / 'charuco' / 'boards' / 'charuco_A3_6x8_45mm.pdf'
PAGE_MM = (297.0, 420.0)
PAGE_CENTRE = Vector((57.0, 45.0)) * MM
VASE_AT = Vector((80.0, 40.0)) * MM


def args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=REPO / 'docs' / 'images')
    ap.add_argument('--samples', type=int, default=192)
    ap.add_argument('--preview', action='store_true', help='small and fast, to check the framing')
    return ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])


def gpu(scene):
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA'):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        rtx = [d for d in prefs.devices if d.type == kind and 'RTX' in d.name]
        if rtx:
            for d in prefs.devices:
                d.use = d in rtx          # never the GTX 1650: speech-to-text owns it
            scene.cycles.device = 'GPU'
            print('render on', [d.name for d in rtx], kind)
            return
    print('no RTX device, rendering on the CPU')


def principled(name, colour, rough=0.5, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*colour, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Coat Weight'].default_value = coat
    return m


def restyle(objects):
    """glTF colours are flat; give the parts plausible surfaces (PLA satin, aluminium, brass, glass)."""
    keep = {}
    for o in objects:
        if o.type != 'MESH':
            continue
        base = o.active_material.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value[:3]
        n = o.name
        if n.startswith('Profile'):
            m = keep.setdefault('alu', principled('Aluminium', (0.82, 0.83, 0.85), 0.32, 1.0))
        elif n in ('Laser body 01', 'Laser body 02'):
            m = keep.setdefault('brass', principled('Brass', (0.85, 0.62, 0.30), 0.3, 1.0))
        elif n in ('S24 body 02', 'S24 body 03'):
            m = keep.setdefault('glass', principled('Phone glass', (0.01, 0.01, 0.012), 0.08, 0.0, 1.0))
        elif n.startswith('S24 body'):
            m = keep.setdefault('frame', principled('Phone frame', (0.55, 0.56, 0.58), 0.28, 1.0))
        elif n.startswith('Laser body'):
            m = principled(f'{n} colour', base, 0.4)
        else:   # printed parts
            m = keep.setdefault(tuple(round(c, 3) for c in base), principled(f'PLA {len(keep)}', base, 0.42))
        o.data.materials.clear()
        o.data.materials.append(m)
        if o.data.polygons:
            o.data.shade_smooth() if hasattr(o.data, 'shade_smooth') else None
            for f in o.data.polygons:
                f.use_smooth = True


def auto_smooth(objects):
    for o in objects:
        if o.type == 'MESH':
            bpy.context.view_layer.objects.active = o
            o.select_set(True)
    try:
        bpy.ops.object.shade_auto_smooth(angle=math.radians(35))
    except Exception as e:      # older Blender: per-mesh flag
        print('auto smooth:', e)
    for o in objects:
        o.select_set(False)


def stripe_factor(nt):
    """Node output: 1 on the laser stripe (inside the fan, below the aperture), 0 elsewhere."""
    n = nt.nodes
    pos = n.new('ShaderNodeNewGeometry')
    sep = n.new('ShaderNodeSeparateXYZ')
    nt.links.new(pos.outputs['Position'], sep.inputs[0])

    def math_node(op, a, b=None, clamp=False):
        m = n.new('ShaderNodeMath')
        m.operation = op
        m.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                nt.links.new(v, m.inputs[i])
        return m.outputs[0]

    dist = math_node('ABSOLUTE', math_node('SUBTRACT', sep.outputs['X'], LASER.x))
    ramp = n.new('ShaderNodeMapRange')
    ramp.interpolation_type = 'SMOOTHSTEP'
    ramp.inputs['From Min'].default_value = STRIPE_MM[0] * MM
    ramp.inputs['From Max'].default_value = STRIPE_MM[1] * MM
    ramp.inputs['To Min'].default_value = 1.0
    ramp.inputs['To Max'].default_value = 0.0
    nt.links.new(dist, ramp.inputs['Value'])
    depth = math_node('SUBTRACT', LASER.z, sep.outputs['Z'])                     # below the aperture
    side = math_node('ABSOLUTE', math_node('SUBTRACT', sep.outputs['Y'], LASER.y))
    inside = math_node('LESS_THAN', side, math_node('MULTIPLY', depth, math.tan(math.radians(FAN_HALF_DEG))))
    below = math_node('GREATER_THAN', depth, 0.0)
    return math_node('MULTIPLY', ramp.outputs[0], math_node('MULTIPLY', inside, below))


def with_stripe(m):
    """Mix a red emission over a material's surface output where the laser stripe falls."""
    nt = m.node_tree
    out = nt.nodes['Material Output']
    surf = out.inputs['Surface'].links[0].from_socket
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.02, 0.01, 1)
    em.inputs['Strength'].default_value = 40.0
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(stripe_factor(nt), mix.inputs['Fac'])
    nt.links.new(surf, mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


def plane(name, size, at, material):
    bpy.ops.mesh.primitive_plane_add(size=1, location=at)
    o = bpy.context.object
    o.name = name
    o.scale = (*size, 1)
    o.data.materials.append(material)
    return o


def board_texture(path_png):
    import subprocess
    if not path_png.exists():   # rasterise the A3 page once (PyMuPDF in a system Python)
        code = ("import fitz,sys; d=fitz.open(sys.argv[1]); d[0].get_pixmap(dpi=200).save(sys.argv[2])")
        subprocess.run(['python', '-c', code, str(BOARD_PDF), str(path_png)], check=True)
    return bpy.data.images.load(str(path_png))


def scan_props(tmp):
    paper = principled('Paper', (0.9, 0.9, 0.9), 0.75)
    tex = paper.node_tree.nodes.new('ShaderNodeTexImage')
    tex.image = board_texture(tmp / 'board_A3.png')
    paper.node_tree.links.new(tex.outputs['Color'], paper.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
    page = plane('Board A3', (PAGE_MM[0] * MM, PAGE_MM[1] * MM), (*PAGE_CENTRE, BOARD_Z), with_stripe(paper))
    table = plane('Table', (1.6, 1.6), (0.05, 0.05, BOARD_Z - 0.2 * MM),
                  with_stripe(principled('Table', (0.36, 0.33, 0.30), 0.6)))
    # a vase turned from a profile (radius, height) in mm
    prof = [(0, 0), (26, 0), (30, 6), (35, 24), (34, 40), (26, 58), (16, 70), (15, 78), (19, 86), (17, 87), (0, 87)]
    import bmesh
    me = bpy.data.meshes.new('Vase')
    bm = bmesh.new()
    seg = 96
    rings = []
    for r, h in prof:
        rings.append([bm.verts.new((r * MM * math.cos(2 * math.pi * k / seg), r * MM * math.sin(2 * math.pi * k / seg), h * MM))
                      for k in range(seg)])
    for a, b in zip(rings, rings[1:]):
        for k in range(seg):
            bm.faces.new((a[k], a[(k + 1) % seg], b[(k + 1) % seg], b[k]))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bm.to_mesh(me)
    bm.free()
    vase = bpy.data.objects.new('Vase', me)
    bpy.context.collection.objects.link(vase)
    vase.location = (*VASE_AT, BOARD_Z)
    vase.data.materials.append(with_stripe(principled('Clay', (0.78, 0.74, 0.70), 0.65)))
    for f in me.polygons:
        f.use_smooth = True
    vase.modifiers.new('subd', 'SUBSURF').levels = 1
    # the light sheet: a translucent red fan from the aperture down to the table
    h = LASER.z - BOARD_Z
    w = math.tan(math.radians(FAN_HALF_DEG)) * h
    fm = bpy.data.meshes.new('Laser sheet')
    fm.from_pydata([tuple(LASER), (LASER.x, LASER.y - w, BOARD_Z), (LASER.x, LASER.y + w, BOARD_Z)], [], [(0, 1, 2)])
    fan = bpy.data.objects.new('Laser sheet', fm)
    bpy.context.collection.objects.link(fan)
    sheet = bpy.data.materials.new('Laser sheet')
    sheet.use_nodes = True
    nt = sheet.node_tree
    nt.nodes.remove(nt.nodes['Principled BSDF'])
    em = nt.nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = (1.0, 0.05, 0.03, 1)
    em.inputs['Strength'].default_value = 0.08
    add = nt.nodes.new('ShaderNodeAddShader')
    nt.links.new(nt.nodes.new('ShaderNodeBsdfTransparent').outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    fan.data.materials.append(sheet)
    fan.visible_shadow = False
    fan.visible_diffuse = False
    fan.visible_glossy = False
    return [page, table, vase, fan, *view_cone()]


def view_cone():
    """Thin lines from the phone's main camera to the corners of what it sees on the board (a sketch:
    about 68 x 53 deg, the long side along the phone)."""
    eye = Vector((22.75, 44.5, 36.4)) * MM
    h = eye.z - BOARD_Z
    hx, hy = math.tan(math.radians(26.5)) * h, math.tan(math.radians(34)) * h
    ink = principled('Sketch line', (0.08, 0.2, 0.45), 0.5)
    out = []
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        c = bpy.data.curves.new('view ray', 'CURVE')
        c.dimensions = '3D'
        c.bevel_depth = 0.35 * MM
        sp = c.splines.new('POLY')
        sp.points.add(1)
        sp.points[0].co = (*eye, 1)
        sp.points[1].co = (eye.x + sx * hx, eye.y + sy * hy, BOARD_Z, 1)
        o = bpy.data.objects.new('view ray', c)
        o.data.materials.append(ink)
        o.visible_shadow = False
        bpy.context.collection.objects.link(o)
        out.append(o)
    return out


def studio_floor():
    return plane('Floor', (3, 3), (0.04, 0, -45 * MM), principled('Floor', (0.93, 0.93, 0.93), 0.8))


def lights():
    def area(name, at, energy, size):
        d = bpy.data.lights.new(name, 'AREA')
        d.energy = energy
        d.size = size
        o = bpy.data.objects.new(name, d)
        bpy.context.collection.objects.link(o)
        o.location = at
        aim(o, Vector((0.04, 0.0, 0.02)))
        return o
    area('Key', (0.55, -0.6, 0.75), 45, 0.6)
    area('Fill', (-0.7, -0.2, 0.35), 14, 0.9)
    area('Rim', (0.0, 0.8, 0.5), 25, 0.5)
    area('Under', (0.3, -0.3, -0.6), 8, 0.8)


def aim(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat('-Z', 'Y').to_euler()


def frame(cam, direction, target, points, margin=1.12):
    """Put the camera along `direction` from `target`, as close as possible with every point in view."""
    d = Vector(direction).normalized()
    scene = bpy.context.scene
    aspect = scene.render.resolution_x / scene.render.resolution_y
    half = math.atan(math.tan(cam.data.angle / 2) / max(aspect, 1)) if aspect >= 1 else cam.data.angle / 2
    half_h = math.atan(math.tan(half) * aspect)
    lo, hi = 0.05, 10.0
    for _ in range(60):
        dist = (lo + hi) / 2
        cam.location = target + d * dist
        aim(cam, target)
        bpy.context.view_layer.update()
        inv = cam.matrix_world.inverted()
        ok = True
        for p in points:
            q = inv @ p
            if -q.z <= 0 or abs(q.x) / -q.z > math.tan(half_h) / margin or abs(q.y) / -q.z > math.tan(half) / margin:
                ok = False
                break
        lo, hi = (lo, dist) if ok else (dist, hi)
    cam.location = target + d * hi
    aim(cam, target)


def fill(cam, points, share=0.84):
    """Centre the points in the frame with lens shift and zoom so they span `share` of it."""
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    wide = scene.render.resolution_x >= scene.render.resolution_y
    for _ in range(3):
        bpy.context.view_layer.update()
        uv = [world_to_camera_view(scene, cam, p) for p in points]
        u0, u1 = min(q.x for q in uv), max(q.x for q in uv)
        v0, v1 = min(q.y for q in uv), max(q.y for q in uv)
        aspect = scene.render.resolution_y / scene.render.resolution_x
        cam.data.shift_x += ((u0 + u1) / 2 - .5) * (1 if wide else aspect)
        cam.data.shift_y += ((v0 + v1) / 2 - .5) * (aspect if wide else 1)
        zoom = share / max(u1 - u0, v1 - v0)
        cam.data.lens *= zoom
        cam.data.shift_x *= zoom
        cam.data.shift_y *= zoom


def mesh_points(objects, step=7):
    pts = []
    for o in objects:
        if o.type == 'MESH':
            mw = o.matrix_world
            vs = o.data.vertices
            pts += [mw @ vs[i].co for i in range(0, len(vs), step)]
    return pts


def bbox_points(objects):
    pts = []
    for o in objects:
        if o.type == 'MESH':
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    return pts


def main():
    a = args()
    a.out.mkdir(parents=True, exist_ok=True)
    tmp = Path(bpy.app.tempdir or '.')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    gpu(scene)
    scene.cycles.samples = 24 if a.preview else a.samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = (800, 500) if a.preview else (1600, 1000)
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = 'JPEG'
    scene.render.image_settings.quality = 90
    try:   # keeps the PLA colours saturated; AgX washes the pink and green out
        scene.view_settings.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        scene.view_settings.view_transform = 'AgX'
    # the camera sees a near-white backdrop, the scene is lit by a dim grey sky
    world = bpy.data.worlds.new('World')
    world.use_nodes = True
    wn = world.node_tree
    sky = wn.nodes['Background']
    sky.inputs['Color'].default_value = (0.8, 0.8, 0.82, 1)
    sky.inputs['Strength'].default_value = 0.25
    backdrop = wn.nodes.new('ShaderNodeBackground')
    backdrop.inputs['Color'].default_value = (0.95, 0.95, 0.96, 1)
    mix = wn.nodes.new('ShaderNodeMixShader')
    wn.links.new(wn.nodes.new('ShaderNodeLightPath').outputs['Is Camera Ray'], mix.inputs['Fac'])
    wn.links.new(sky.outputs[0], mix.inputs[1])
    wn.links.new(backdrop.outputs[0], mix.inputs[2])
    wn.links.new(mix.outputs[0], wn.nodes['World Output'].inputs['Surface'])
    scene.world = world

    bpy.ops.import_scene.gltf(filepath=str(HERE / 'easy_scanner.glb'))
    parts = [o for o in bpy.data.objects if o.type == 'MESH']
    restyle(parts)
    auto_smooth(parts)
    lights()
    cam = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 60

    pts = bbox_points(parts)
    centre = sum(pts, Vector()) / len(pts)
    floor = studio_floor()
    shots = {
        'assembly_side': (1.0, -1.25, -0.35),
        'assembly_top': (0.75, -0.95, 1.25),
        'assembly_under': (0.35, -0.55, -1.2),
    }
    verts = mesh_points(parts)
    for name, direction in shots.items():
        floor.hide_render = direction[2] < 0      # no floor when looking from below
        cam.data.lens, cam.data.shift_x, cam.data.shift_y = 60, 0, 0
        frame(cam, direction, centre, pts)
        fill(cam, verts)
        scene.render.filepath = str(a.out / f'{name}.jpg')
        bpy.ops.render.render(write_still=True)
        print('wrote', scene.render.filepath)

    floor.hide_render = True
    props = scan_props(tmp)
    scan_pts = pts + [Vector((PAGE_CENTRE.x + sx * PAGE_MM[0] / 2 * MM, PAGE_CENTRE.y + sy * PAGE_MM[1] / 2 * MM, BOARD_Z))
                      for sx in (-1, 1) for sy in (-1, 1)]
    target = Vector((0.06, 0.04, BOARD_Z * 0.55))
    cam.data.lens, cam.data.shift_x, cam.data.shift_y = 45, 0, 0
    frame(cam, (1.25, -0.6, 0.7), target, scan_pts, margin=1.04)
    fill(cam, verts + scan_pts[-4:], share=0.92)
    scene.render.filepath = str(a.out / 'scan_schematic.jpg')
    bpy.ops.render.render(write_still=True)
    print('wrote', scene.render.filepath)


main()
