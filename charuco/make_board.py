"""Printable ChArUco boards for Easy Scanner: vector PDF at true scale, one board per page.

    python make_board.py                                   # every preset (A4..A0) into boards/
    python make_board.py --paper A3                        # one preset
    python make_board.py --paper A3 --squares 7x9 --square 40 -o my_board.pdf
    python make_board.py --check                           # rasterise the PDFs and detect every corner

The board is OpenCV's ChArUco layout (OpenCV >= 4.6, the same one the app detects): `squares` is
columns x rows across the page as printed, markers are `marker` mm (default 0.74 of the square,
45 -> 33.3), marker ids start at 0. Every page states the values to enter in the app's Settings and
carries a 100 mm scale bar: print at 100 % ("Actual size") and measure it.

Needs: pip install opencv-python numpy reportlab (and pymupdf for --check).
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
PAPER_MM = {'A4': (210, 297), 'A3': (297, 420), 'A2': (420, 594), 'A1': (594, 841), 'A0': (841, 1189)}
# 45 mm squares up to A2 (A2 is the 8 x 10 board we scan on); bigger paper gets bigger squares,
# so DICT_5X5_100 (100 markers) still covers the board and the markers stay readable from further away
PRESETS = {'A4': ((4, 6), 45.0), 'A3': ((6, 8), 45.0), 'A2': ((8, 10), 45.0),
           'A1': ((9, 13), 60.0), 'A0': ((10, 14), 80.0)}
MARKER_RATIO = 33.3 / 45.0
HEADER_MM = 17.0      # title, app settings and the scale bar above the board
DICTS = {name: getattr(cv2.aruco, name) for name in dir(cv2.aruco) if name.startswith('DICT_')}


def make_board(squares, square, marker, dict_name):
    dictionary = cv2.aruco.getPredefinedDictionary(DICTS[dict_name])
    count = squares[0] * squares[1] // 2
    if count > len(dictionary.bytesList):
        raise SystemExit(f'{squares[0]}x{squares[1]} needs {count} markers, {dict_name} has {len(dictionary.bytesList)}')
    return cv2.aruco.CharucoBoard(squares, square, marker, dictionary), dictionary


def black_polygons(board, dictionary, squares, square):
    """Black squares and black marker cells as quads in board mm (origin top-left, y down)."""
    quads = [np.asarray(q, float)[:, :2] for q in board.getObjPoints()]
    centres = [q.mean(axis=0) for q in quads]
    polys = []
    for r in range(squares[1]):
        for c in range(squares[0]):
            x0, y0 = c * square, r * square
            if not any(x0 < m[0] < x0 + square and y0 < m[1] < y0 + square for m in centres):
                polys.append(np.array([[x0, y0], [x0 + square, y0], [x0 + square, y0 + square], [x0, y0 + square]]))
    side = dictionary.markerSize + 2
    for marker_id, q in zip(board.getIds(), quads):
        bits = cv2.aruco.generateImageMarker(dictionary, int(marker_id), side, borderBits=1)
        u, v = (q[1] - q[0]) / side, (q[3] - q[0]) / side
        for i, j in zip(*np.nonzero(bits == 0)):
            p = q[0] + j * u + i * v
            polys.append(np.array([p, p + u, p + u + v, p + v]))
    return polys


def write_pdf(path, paper, squares, square, marker, dict_name):
    page = PAPER_MM[paper]
    board, dictionary = make_board(squares, square, marker, dict_name)
    size = (squares[0] * square, squares[1] * square)
    if size[0] > page[0] - 10 or size[1] > page[1] - HEADER_MM - 5:
        raise SystemExit(f'{size[0]:g} x {size[1]:g} mm does not fit {paper} ({page[0]} x {page[1]} mm) with margins')
    origin = ((page[0] - size[0]) / 2, HEADER_MM + (page[1] - HEADER_MM - size[1]) / 2)

    def pt(x, y):     # page mm, y down -> PDF points, y up
        return x * mm, (page[1] - y) * mm

    pdf = canvas.Canvas(str(path), pagesize=(page[0] * mm, page[1] * mm))
    pdf.setTitle(f'ChArUco {squares[0]}x{squares[1]}, {square:g} mm, {dict_name} ({paper})')
    shape = pdf.beginPath()
    for poly in black_polygons(board, dictionary, squares, square):
        shape.moveTo(*pt(*(poly[0] + origin)))
        for p in poly[1:]:
            shape.lineTo(*pt(*(p + origin)))
        shape.close()
    pdf.setFillColorRGB(0, 0, 0)
    pdf.drawPath(shape, stroke=0, fill=1, fillMode=1)   # non-zero fill: no seams between cells

    left = origin[0]
    pdf.setFont('Helvetica-Bold', 9)
    pdf.drawString(*pt(left, 5.5), f'Easy Scanner ChArUco {paper}: {squares[0]} x {squares[1]} squares of {square:g} mm, '
                                   f'markers {marker:g} mm, {dict_name}')
    pdf.setFont('Helvetica', 7)
    pdf.drawString(*pt(left, 9.5), f'App Settings: squares X {squares[0]}, squares Y {squares[1]}, square {square:g} mm, '
                                   f'marker {marker:g} mm, dictionary id {DICTS[dict_name]}. Print at 100 %, never "Fit to page".')
    bar_x = page[0] - left - 100      # 100 mm scale bar, right-aligned with the board
    pdf.setLineWidth(0.3)
    pdf.line(*pt(bar_x, 14), *pt(bar_x + 100, 14))
    for k in range(11):
        pdf.line(*pt(bar_x + 10 * k, 14 - (2.5 if k % 5 == 0 else 1.2)), *pt(bar_x + 10 * k, 14))
    pdf.drawRightString(*pt(bar_x - 2, 14), '100 mm')
    pdf.showPage()
    pdf.save()
    return {'paper': paper, 'file': path.name, 'squares_x': squares[0], 'squares_y': squares[1],
            'square_mm': square, 'marker_mm': marker, 'dictionary': dict_name, 'dict': DICTS[dict_name],
            'board_mm': list(size), 'board_origin_on_page_mm': [round(v, 3) for v in origin]}


def check(info, folder):
    """Rasterise the page at 4 px/mm and detect the board: every inner corner must be found."""
    import fitz
    page = fitz.open(folder / info['file'])[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(4 / (72 / 25.4), 4 / (72 / 25.4)), colorspace=fitz.csGRAY)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)
    board, _ = make_board((info['squares_x'], info['squares_y']), info['square_mm'], info['marker_mm'], info['dictionary'])
    corners, ids, _, _ = cv2.aruco.CharucoDetector(board).detectBoard(img)
    want = (info['squares_x'] - 1) * (info['squares_y'] - 1)
    found = 0 if ids is None else len(ids)
    err = None
    if found:
        expect = np.asarray(board.getChessboardCorners())[ids.ravel(), :2] + info['board_origin_on_page_mm']
        err = float(np.abs(corners.reshape(-1, 2) / 4 - expect).max())
    return found, want, err


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--paper', choices=PAPER_MM, help='one paper size (default: every preset)')
    ap.add_argument('--squares', help='columns x rows, e.g. 6x8 (default: the preset)')
    ap.add_argument('--square', type=float, help='square side, mm (default: the preset)')
    ap.add_argument('--marker', type=float, help=f'marker side, mm (default: {MARKER_RATIO:.2f} of the square)')
    ap.add_argument('--dict', default='DICT_5X5_100', choices=sorted(DICTS), help='ArUco dictionary')
    ap.add_argument('-o', '--out', type=Path, help='output PDF (one paper only)')
    ap.add_argument('--check', action='store_true', help='rasterise the written PDFs and detect the boards')
    a = ap.parse_args()

    papers = [a.paper] if a.paper else list(PRESETS)
    folder = a.out.parent if a.out else HERE / 'boards'
    folder.mkdir(parents=True, exist_ok=True)
    infos = []
    for paper in papers:
        squares, square = PRESETS[paper]
        if a.squares:
            squares = tuple(int(v) for v in a.squares.lower().split('x'))
        square = a.square or square
        marker = a.marker or round(square * MARKER_RATIO, 1)
        name = a.out.name if a.out else f'charuco_{paper}_{squares[0]}x{squares[1]}_{square:g}mm.pdf'
        info = write_pdf(folder / name, paper, squares, square, marker, a.dict)
        if a.check:
            found, want, err = check(info, folder)
            info['check'] = f'{found}/{want} corners, max error {err:.3f} mm' if err is not None else 'not detected'
        infos.append(info)
        print(f"{paper}: {name}  {squares[0]}x{squares[1]} x {square:g} mm, marker {marker:g} mm"
              + (f"  [{info['check']}]" if a.check else ''))
    if not a.out and not a.paper and not a.squares and not a.square and not a.marker:
        (folder / 'boards.json').write_text(json.dumps(infos, indent=1))


if __name__ == '__main__':
    main()
