"""STL mesh -> one CadQuery solid, so the downloaded parts can be cut and fused."""
from pathlib import Path

import cadquery as cq
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeSolid, BRepBuilderAPI_Sewing
from OCP.ShapeFix import ShapeFix_Solid
from OCP.StlAPI import StlAPI_Reader
from OCP.TopAbs import TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

# The original Tripod Mobile Phone Clamp V2 meshes, slim-phone variant (see ../README.md).
PARTS = Path(__file__).resolve().parent.parent / 'source'


def load_stl(path):
    mesh = TopoDS_Shape()
    if not StlAPI_Reader().Read(mesh, str(path)):
        raise ValueError(f'Cannot read STL: {path}')
    sewing = BRepBuilderAPI_Sewing(1e-4)
    sewing.Add(mesh)
    sewing.Perform()
    shells = TopExp_Explorer(sewing.SewedShape(), TopAbs_SHELL)
    maker = BRepBuilderAPI_MakeSolid()
    while shells.More():
        maker.Add(TopoDS.Shell_s(shells.Current()))
        shells.Next()
    fix = ShapeFix_Solid(maker.Solid())
    fix.Perform()
    return cq.Shape.cast(fix.Solid())


def cached_solid(stl):
    # Sewing tens of thousands of triangles takes minutes; reuse the solid until the STL changes.
    cache = stl.with_suffix('.brep')  # next to the STL; ignored by git
    if cache.exists() and cache.stat().st_mtime >= stl.stat().st_mtime:
        return cq.Shape.importBrep(str(cache))
    shape = load_stl(stl)
    shape.exportBrep(str(cache))
    return shape
