# SPDX-FileCopyrightText: 2025-2026 The French Monkey
# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "Grid",
    "author": "The French Monkey",
    "version": (1, 0, 3),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Grid",
    "description": "Generate parametric grid",
    "category": "Add Mesh",
    "license": "GPL-3.0-or-later",
}

import bpy
import random
from math import cos, sin, tau, sqrt, hypot, radians, floor, atan2

try:
    from . import relay_updater
except ImportError:  # the Addon Collection has its own updates
    relay_updater = None

# ---------------------------------------------------------
# Utils
# ---------------------------------------------------------

def ensure_link(obj):
    coll = bpy.context.collection
    if obj.name not in coll.objects:
        coll.objects.link(obj)

def deactivate_all():
    bpy.ops.object.select_all(action="DESELECT")

def safe_delete_children(parent):
    if not parent: return
    kids = list(parent.children)
    if not kids: return
    deactivate_all()
    for ob in kids: ob.select_set(True)
    bpy.ops.object.delete()

def make_mesh_faces(name, v3_list, faces_idx):
    me = bpy.data.meshes.new(name)
    me.from_pydata(v3_list, [], faces_idx)
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ensure_link(ob)
    return ob

def add_strip_quads(v2a, v2b, halfw):
    x1, y1 = v2a; x2, y2 = v2b
    dx, dy = x2 - x1, y2 - y1
    L = hypot(dx, dy)
    if L < 1e-9: return None
    nx, ny = -dy / L, dx / L
    return [
        (x1 + nx * halfw, y1 + ny * halfw, 0.0),
        (x1 - nx * halfw, y1 - ny * halfw, 0.0),
        (x2 - nx * halfw, y2 - ny * halfw, 0.0),
        (x2 + nx * halfw, y2 + ny * halfw, 0.0)
    ]

def add_cross_quads(center, size, halfw):
    x, y = center
    s2 = size * 0.5
    v, f = [], []
    q = add_strip_quads((x - s2, y), (x + s2, y), halfw)
    if q: i = len(v); v.extend(q); f.append((i, i+1, i+2, i+3))
    q = add_strip_quads((x, y - s2), (x, y + s2), halfw)
    if q: i = len(v); v.extend(q); f.append((i, i+1, i+2, i+3))
    return v, f

def add_disc_ngon(center, r, segs):
    if r <= 0: return [], []
    cx, cy = center
    segs = max(3, int(segs))
    verts = [(cx, cy, 0.0)]
    for i in range(segs):
        a = tau * i / segs
        verts.append((cx + r * cos(a), cy + r * sin(a), 0.0))
    faces = [(0, i, i+1) for i in range(1, segs)] + [(0, segs, 1)]
    return verts, faces

def add_ring_ngon(center, r_in, r_out, segs):
    r_in = max(0.0, float(r_in))
    r_out = max(r_in + 1e-9, float(r_out))
    segs = max(6, int(segs))
    cx, cy = center
    outer, inner = [], []
    for i in range(segs):
        a = tau * i / segs
        outer.append((cx + r_out * cos(a), cy + r_out * sin(a), 0.0))
        inner.append((cx + r_in * cos(a), cy + r_in * sin(a), 0.0))
    v = outer + inner
    faces = [(i, (i+1)%segs, segs+((i+1)%segs), segs+i) for i in range(segs)]
    return v, faces

def add_square_ring(center, s_outer, s_inner):
    s_outer = float(s_outer)
    s_inner = min(max(0.0, float(s_inner)), s_outer - 1e-9)
    ox, ix = s_outer * 0.5, s_inner * 0.5
    x, y = center
    outer = [(x-ox, y-ox, 0.0), (x+ox, y-ox, 0.0), (x+ox, y+ox, 0.0), (x-ox, y+ox, 0.0)]
    if s_inner <= 1e-9: return outer, [(0, 1, 2, 3)]
    inner = [(x-ix, y-ix, 0.0), (x+ix, y-ix, 0.0), (x+ix, y+ix, 0.0), (x-ix, y+ix, 0.0)]
    v = outer + inner
    faces = [(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    return v, faces

def bounds_from_points(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), max(xs), min(ys), max(ys)

def filter_by_spacing(points, spacing):
    if spacing <= 0.0: return list(points)
    kept, s2 = [], spacing * spacing
    for p in points:
        px, py = p
        if all((px - qx)**2 + (py - qy)**2 >= s2 for qx, qy in kept):
            kept.append(p)
    return kept

def vary_size(base, rand_pct, rng):
    r = max(0.0, float(rand_pct))
    if r <= 0.0: return base
    return max(0.0, base * (1.0 + rng.uniform(-r, r)))

# ---------------------------------------------------------
# Rectangular
# ---------------------------------------------------------

def grid_square_data(cols, rows, step_x, step_y, scale):
    cols, rows = max(2, int(cols)), max(2, int(rows))
    sx, sy, sc = float(step_x), float(step_y), float(scale)
    ox, oy = -(cols - 1) * 0.5 * sx, -(rows - 1) * 0.5 * sy
    verts, id_at, k = [], {}, 0
    for j in range(rows):
        for i in range(cols):
            x, y = (ox + i * sx) * sc, (oy + j * sy) * sc
            id_at[(i, j)] = k; verts.append((x, y)); k += 1
    edges = [(id_at[(i,j)], id_at[(i+1,j)]) for j in range(rows) for i in range(cols-1)] + \
            [(id_at[(i,j)], id_at[(i,j+1)]) for j in range(rows-1) for i in range(cols)]
    def sub_fn(f):
        f = max(1, int(f))
        return grid_square_data((cols-1)*f+1, (rows-1)*f+1, sx/f, sy/f, sc)
    return verts, edges, sub_fn

# ---------------------------------------------------------
# Circular
# ---------------------------------------------------------

def grid_circular_data(rings, segs, radius, scale, inner_radius=0.0):
    rings, segs = max(1, int(rings)), max(3, int(segs))
    sc = float(scale)
    inner_radius = max(0.0, float(inner_radius))
    radius = max(inner_radius + 1e-6, float(radius))
    verts, id_at, ring_verts, k = [], {}, [], 0
    for r in range(rings + 1):
        frac = r / rings
        rad = inner_radius + (radius - inner_radius) * frac
        cur = []
        for s in range(segs):
            a = tau * s / segs
            x, y = rad * cos(a) * sc, rad * sin(a) * sc
            id_at[(r, s)] = k
            verts.append((x, y))
            cur.append(k)
            k += 1
        ring_verts.append(cur)
    edges = [(id_at[(r, s)], id_at[(r+1, s)]) for s in range(segs) for r in range(rings)]
    edges += [(ring[i], ring[(i+1)%segs]) for ring in ring_verts for i in range(segs)]
    def sub_fn(f):
        f = max(1, int(f))
        return grid_circular_data(rings*f, segs, radius, sc, inner_radius)
    order = sorted(range(len(verts)), key=lambda i: (round(verts[i][0],6), round(verts[i][1],6)))
    index_map = {old:new for new, old in enumerate(order)}
    verts = [verts[i] for i in order]
    edges = [(index_map[a], index_map[b]) for a,b in edges]
    return verts, edges, sub_fn

# ---------------------------------------------------------
# Hexagonal 
# ---------------------------------------------------------

def grid_hexagonal_data(rings, radius, scale):
    from math import sqrt, cos, sin, tau
    rings, sc = max(1, int(rings)), float(scale)
    size = radius / (1.5 * rings + 1)
    corner_offsets = [(cos(tau * (2*i + 1) / 12.0), sin(tau * (2*i + 1) / 12.0)) for i in range(6)]
    centers = [(q, r) for q in range(-rings, rings + 1) for r in range(max(-rings, -q - rings), min(rings, -q + rings) + 1)]
    vert_dict, verts, edge_set, edges = {}, [], set(), []
    def add_vert(px, py):
        key = (round(px, 9), round(py, 9))
        if key in vert_dict: return vert_dict[key]
        idx = len(verts); verts.append((px, py)); vert_dict[key] = idx; return idx
    for q, r in centers:
        cx, cy = size * (sqrt(3) * q + sqrt(3)/2 * r) * sc, size * (1.5 * r) * sc
        corners = [add_vert(cx + size * ox * sc, cy + size * oy * sc) for ox, oy in corner_offsets]
        for i in range(6):
            a, b = corners[i], corners[(i+1)%6]
            key = frozenset({a, b})
            if key not in edge_set:
                edge_set.add(key); edges.append((a, b))
    def sub_fn(f):
        return grid_hexagonal_data(rings * max(1, int(f)), radius, sc)
    order = sorted(range(len(verts)), key=lambda i: (round(verts[i][0],6), round(verts[i][1],6)))
    index_map = {old:new for new, old in enumerate(order)}
    verts = [verts[i] for i in order]
    edges = [(index_map[a], index_map[b]) for a,b in edges]
    return verts, edges, sub_fn

# ---------------------------------------------------------
# Voronoi
# ---------------------------------------------------------

def grid_voronoi_data(cols, rows, step_x, step_y, scale, relax_iter=2):
    from collections import defaultdict
    from mathutils import geometry

    cols, rows = max(2, int(cols)), max(2, int(rows))
    sx, sy = float(step_x) * float(scale), float(step_y) * float(scale)
    width, height = (cols - 1) * sx, (rows - 1) * sy
    ox, oy = -0.5 * width, -0.5 * height
    min_x, max_x, min_y, max_y = ox, ox + width, oy, oy + height

    base_sites = [[ox + i * sx, oy + j * sy] for j in range(rows) for i in range(cols)]

    def circumcenter(a, b, c):
        ax, ay = a; bx, by = b; cx, cy = c
        d = 2.0 * (ax*(by-cy) + bx*(cy-ay) + cx*(ay-by))
        if abs(d) < 1e-12: return ((ax+bx+cx)/3.0, (ay+by+cy)/3.0)
        ux = ((ax*ax+ay*ay)*(by-cy) + (bx*bx+by*by)*(cy-ay) + (cx*cx+cy*cy)*(ay-by)) / d
        uy = ((ax*ax+ay*ay)*(cx-bx) + (bx*bx+by*by)*(ax-cx) + (cx*cx+cy*cy)*(bx-ax)) / d
        return ux, uy

    relax_iter = max(0, int(relax_iter))
    sites = [s[:] for s in base_sites]
    for _ in range(relax_iter):
        v, _, faces, *_ = geometry.delaunay_2d_cdt(sites, [], [], 0, 1e-6, True)
        tris_by_site = defaultdict(list)
        for f_idx, tri in enumerate(faces):
            for vi in tri: tris_by_site[vi].append(f_idx)
        new_sites = []
        for idx in range(len(sites)):
            tris = tris_by_site.get(idx)
            if not tris: new_sites.append(sites[idx]); continue
            cx = cy = 0.0
            for t in tris:
                a, b, c = (v[j] for j in faces[t])
                ux, uy = circumcenter(a, b, c); cx += ux; cy += uy
            n = len(tris); new_sites.append([cx / n, cy / n])
        sites = new_sites

    tile_dx = width + (sx if cols > 1 else 0.0)
    tile_dy = height + (sy if rows > 1 else 0.0)
    augmented_sites = [[x + ti*tile_dx, y + tj*tile_dy] for tj in (-1,0,1) for ti in (-1,0,1) for x, y in sites]

    V, _, F, *_ = geometry.delaunay_2d_cdt(augmented_sites, [], [], 0, 1e-6, True)
    tri_cc = [circumcenter(V[t[0]], V[t[1]], V[t[2]]) for t in F]

    edge_to_faces = defaultdict(list)
    for f_idx, (a, b, c) in enumerate(F):
        for e0, e1 in ((a,b),(b,c),(c,a)):
            if e0 == e1: continue
            k0, k1 = (e0, e1) if e0 < e1 else (e1, e0)
            edge_to_faces[(k0, k1)].append(f_idx)

    def clip_to_box(p1, p2):
        x1, y1 = p1; x2, y2 = p2
        dx, dy = x2 - x1, y2 - y1
        t0, t1 = 0.0, 1.0
        def clip(p, q):
            nonlocal t0, t1
            if abs(p) < 1e-20: return q >= 0.0
            t = q / p
            if p < 0:
                if t > t1: return False
                if t > t0: t0 = t
            else:
                if t < t0: return False
                if t < t1: t1 = t
            return True
        if not clip(-dx, x1 - min_x): return None
        if not clip( dx, max_x - x1): return None
        if not clip(-dy, y1 - min_y): return None
        if not clip( dy, max_y - y1): return None
        nx1, ny1 = x1 + t0*dx, y1 + t0*dy
        nx2, ny2 = x1 + t1*dx, y1 + t1*dy
        if (nx1-nx2)**2 + (ny1-ny2)**2 < 1e-18: return None
        return (nx1, ny1), (nx2, ny2)

    verts2d, vert_map, edges, seen = [], {}, [], set()
    def add_vert(px, py):
        key = (round(px, 9), round(py, 9))
        idx = vert_map.get(key)
        if idx is not None: return idx
        idx = len(verts2d); verts2d.append((px, py)); vert_map[key] = idx; return idx

    for (a, b), face_ids in edge_to_faces.items():
        if len(face_ids) < 2: continue
        c1, c2 = tri_cc[face_ids[0]], tri_cc[face_ids[1]]
        clipped = clip_to_box(c1, c2)
        if not clipped: continue
        (x1, y1), (x2, y2) = clipped
        i1, i2 = add_vert(x1, y1), add_vert(x2, y2)
        if i1 == i2: continue
        ekey = (min(i1, i2), max(i1, i2))
        if ekey in seen: continue
        seen.add(ekey); edges.append((i1, i2))

    def sub_fn(f):
        f = max(1, int(f))
        return grid_voronoi_data(cols * f, rows * f, step_x / f, step_y / f, scale, relax_iter=relax_iter)[:3]

    return verts2d, edges, sub_fn, sites

# ---------------------------------------------------------
# Density
# ---------------------------------------------------------

def edges_count(cols, rows):
    return (cols - 1) * rows + (rows - 1) * cols

def factor_for_density_intersections(cols, rows, density):
    base = cols * rows
    target = max(1, int(base * max(0.0, density)))
    if target <= base: return 1, target, base
    f = 1
    while True:
        c2, r2 = (cols - 1) * f + 1, (rows - 1) * f + 1
        cnt = c2 * r2
        if cnt >= target or f > 4096: return f, target, cnt
        f += 1

def factor_for_density_centers(cols, rows, density):
    base = (cols - 1) * (rows - 1)
    target = max(1, int(base * max(0.0, density)))
    if target <= base: return 1, target, base
    f = 1
    while True:
        c2, r2 = (cols - 1) * f + 1, (rows - 1) * f + 1
        cnt = (c2 - 1) * (r2 - 1)
        if cnt >= target or f > 4096: return f, target, cnt
        f += 1

def factor_for_density_edges(cols, rows, density):
    base = edges_count(cols, rows)
    target = max(1, int(base * max(0.0, density)))
    if target <= base: return 1, target, base
    f = 1
    while True:
        c2, r2 = (cols - 1) * f + 1, (rows - 1) * f + 1
        cnt = edges_count(c2, r2)
        if cnt >= target or f > 4096: return f, target, cnt
        f += 1

def placement_intersections(intersections):
    return list(intersections)

def placement_centers(cols, rows, step_x, step_y, scale):
    cols, rows = max(2, int(cols)), max(2, int(rows))
    sx, sy = float(step_x) * float(scale), float(step_y) * float(scale)
    ox, oy = -(cols - 1) * 0.5 * sx, -(rows - 1) * 0.5 * sy
    return [(ox + (i + 0.5) * sx, oy + (j + 0.5) * sy) for j in range(rows - 1) for i in range(cols - 1)]

def placement_edge_midpoints(intersections, edges):
    mids, seen = [], set()
    for a, b in edges:
        if a == b: continue
        key = tuple(sorted((round(intersections[a][0], 6), round(intersections[a][1], 6),
                            round(intersections[b][0], 6), round(intersections[b][1], 6))))
        if key in seen: continue
        seen.add(key)
        x1, y1 = intersections[a]; x2, y2 = intersections[b]
        mids.append(((x1 + x2) * 0.5, (y1 + y2) * 0.5))
    return mids

def placement_random(bounds, count, seed=0):
    if count <= 0: return []
    minx, maxx, miny, maxy = bounds
    rng = random.Random(int(seed))
    return [(rng.uniform(minx, maxx), rng.uniform(miny, maxy)) for _ in range(count)]

def densify_and_sample(points, target):
    if target <= 0 or not points: return []
    n = len(points)
    if target >= n: return list(points)
    step, out, i = n / target, [], 0.0
    while len(out) < target:
        out.append(points[int(i)]); i += step
        if i >= n: break
    return out

def sample_with_density(points, density):
    n = len(points)
    if n == 0: return []
    target = max(1, int(round(n * max(0.0, float(density)))))
    if target <= n: return densify_and_sample(points, target)
    reps = max(1, int(round(target / n)))
    return (points * reps)[:target]

def placement_circular_centers(rings, segs, inner_radius, outer_radius, scale):
    rings, segs = max(1, int(rings)), max(3, int(segs))
    inner, outer, sc = float(inner_radius), float(outer_radius), float(scale)
    pts = []
    for r in range(rings):
        r0, r1 = inner + (outer - inner) * (r / rings), inner + (outer - inner) * ((r + 1) / rings)
        rad = 0.5 * (r0 + r1)
        for s in range(segs):
            a = tau * (s + 0.5) / segs
            pts.append((rad * cos(a) * sc, rad * sin(a) * sc))
    return pts

def placement_hex_centers(rings, radius, scale):
    from math import sqrt
    rings, sc = max(1, int(rings)), float(scale)
    size = radius / (1.5 * rings + 1)
    return [(size * (sqrt(3) * q + sqrt(3)/2 * r) * sc, size * (1.5 * r) * sc)
            for q in range(-rings, rings + 1)
            for r in range(max(-rings, -q - rings), min(rings, -q + rings) + 1)]

def placement_circular_intersections(rings, segs, inner_radius, outer_radius, scale):
    from math import cos, sin, tau
    rings, segs = max(1, int(rings)), max(3, int(segs))
    inner, outer, sc = float(inner_radius), float(outer_radius), float(scale)
    pts = []
    for r in range(rings + 1):
        rad = inner + (outer - inner) * (r / rings)
        for s in range(segs):
            a = tau * s / segs
            pts.append((rad * cos(a) * sc, rad * sin(a) * sc))
    return pts

def placement_circular_edges(rings, segs, inner_radius, outer_radius, scale):
    from math import cos, sin, tau
    rings, segs = max(1, int(rings)), max(3, int(segs))
    inner, outer, sc = float(inner_radius), float(outer_radius), float(scale)
    pts = []
    for r in range(rings):
        rad1, rad2 = inner + (outer - inner) * (r / rings), inner + (outer - inner) * ((r + 1) / rings)
        for s in range(segs):
            a, b = tau * s / segs, tau * (s + 0.5) / segs
            pts.append((((rad1 + rad2) * 0.5 * cos(a)) * sc, ((rad1 + rad2) * 0.5 * sin(a)) * sc))
            pts.append((rad2 * cos(b) * sc, rad2 * sin(b) * sc))
    return pts

def placement_circular_edges_exact(intersections, edges):
    mids, seen = [], set()
    for a, b in edges:
        if a == b: continue
        x1, y1 = intersections[a]; x2, y2 = intersections[b]
        mx, my = (x1 + x2) * 0.5, (y1 + y2) * 0.5
        key = (round(mx, 6), round(my, 6))
        if key in seen: continue
        seen.add(key); mids.append((mx, my))
    return mids

def _polygon_centroid(pts):
    n, A, cx, cy = len(pts), 0.0, 0.0, 0.0
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        cross = x1 * y2 - x2 * y1
        A += cross; cx += (x1 + x2) * cross; cy += (y1 + y2) * cross
    if abs(A) < 1e-12:
        return (sum(x for x, _ in pts) / n, sum(y for _, y in pts) / n)
    A *= 0.5; cx /= 6.0 * A; cy /= 6.0 * A
    return (cx, cy)

def placement_circular_centers_exact(intersections, edges, rings, segs):
    from math import atan2
    polar = []
    for i, (x, y) in enumerate(intersections):
        r = (x * x + y * y) ** 0.5; a = atan2(y, x)
        if a < 0: a += 6.283185307179586
        polar.append((r, a, i, x, y))
    polar.sort(key=lambda t: (round(t[0], 6), t[1]))
    groups = [[] for _ in range(rings + 1)]
    unique_radii = sorted({round(t[0], 6) for t in polar})
    if len(unique_radii) != rings + 1:
        dr = (max(unique_radii) - min(unique_radii)) / rings
        unique_radii = [min(unique_radii) + i * dr for i in range(rings + 1)]
    for r, a, i, x, y in polar:
        ring_idx = min(range(len(unique_radii)), key=lambda j: abs(unique_radii[j] - r))
        groups[ring_idx].append((a, x, y))
    for g in groups: g.sort(key=lambda t: t[0])
    pts = []
    for r in range(rings):
        g0, g1 = groups[r], groups[r + 1]
        if not g0 or not g1: continue
        n0, n1 = len(g0), len(g1)
        if n0 != n1:
            step = n0 / n1 if n0 > n1 else n1 / n0
            if n0 > n1: g0 = [g0[int(i * step) % n0] for i in range(n1)]
            else: g1 = [g1[int(i * step) % n1] for i in range(n0)]
        segs_eff = min(len(g0), segs)
        for s in range(segs_eff):
            _, x00, y00 = g0[s]; _, x01, y01 = g0[(s + 1) % segs_eff]
            _, x10, y10 = g1[s]; _, x11, y11 = g1[(s + 1) % segs_eff]
            pts.append(((x00 + x01 + x10 + x11) * 0.25, (y00 + y01 + y10 + y11) * 0.25))
    return pts

def placement_hex_intersections(rings, radius, scale):
    from math import sqrt
    sc = float(scale)
    size = radius / (1.5 * rings + 1)
    return [(size * (sqrt(3) * q + sqrt(3)/2 * r) * sc,
             size * (1.5 * r) * sc)
            for q in range(-rings, rings + 1)
            for r in range(max(-rings, -q - rings), min(rings, -q + rings) + 1)]

def placement_hex_edges(rings, radius, scale):
    from math import sqrt
    pts, sc = [], float(scale)
    size = radius / (1.5 * rings + 1)
    hex_dirs = [(1,0),(1,-1),(0,-1),(-1,0),(-1,1),(0,1)]
    for q in range(-rings, rings + 1):
        for r in range(max(-rings, -q - rings), min(rings, -q + rings) + 1):
            cx = size * (sqrt(3) * q + sqrt(3)/2 * r) * sc
            cy = size * (1.5 * r) * sc
            for dx, dy in hex_dirs:
                nx = size * (sqrt(3) * dx + sqrt(3)/2 * dy) * 0.5 * sc
                ny = size * (1.5 * dy) * 0.5 * sc
                pts.append((cx + nx, cy + ny))
    return pts

def _poly_centroid_xy(pts):
    n, A, cx, cy = len(pts), 0.0, 0.0, 0.0
    for i in range(n):
        x1, y1 = pts[i]; x2, y2 = pts[(i + 1) % n]
        c = x1 * y2 - x2 * y1
        A += c; cx += (x1 + x2) * c; cy += (y1 + y2) * c
    if abs(A) < 1e-12:
        return (sum(x for x, _ in pts)/n, sum(y for _, y in pts)/n)
    A *= 0.5; cx /= 6.0 * A; cy /= 6.0 * A
    return (cx, cy)

def placement_circular_centers_topology(intersections, segs, rings):
    from math import atan2
    polar = []
    for x, y in intersections:
        r, a = (x*x + y*y)**0.5, atan2(y, x)
        if a < 0.0: a += 6.283185307179586
        polar.append((r, a, x, y))
    polar.sort(key=lambda t: (round(t[0], 6), t[1]))
    radii = sorted({round(t[0], 6) for t in polar})
    groups = [[] for _ in range(len(radii))]
    for r, a, x, y in polar:
        idx = min(range(len(radii)), key=lambda j: abs(radii[j] - r))
        groups[idx].append((a, x, y))
    for g in groups: g.sort(key=lambda t: t[0])
    def normalize_ring(ring, target):
        n = len(ring)
        if n == target or n == 0: return ring
        step, out, i = n / target, [], 0.0
        while len(out) < target:
            out.append(ring[int(i) % n]); i += step
        return out
    groups = [normalize_ring(g, segs) for g in groups]
    pts = []
    for r in range(len(groups) - 1):
        ring0, ring1 = groups[r], groups[r + 1]
        for s in range(segs):
            _, x00, y00 = ring0[s]; _, x01, y01 = ring0[(s + 1) % segs]
            _, x10, y10 = ring1[s]; _, x11, y11 = ring1[(s + 1) % segs]
            corners = [(x00, y00), (x10, y10), (x11, y11), (x01, y01)]
            pts.append(_poly_centroid_xy(corners))
    return pts

def placement_voronoi_intersections(verts):
    return verts

def placement_voronoi_centers(verts, edges, sites=None):
    from collections import defaultdict
    from math import isfinite
    if not sites:
        conn = defaultdict(list)
        for a, b in edges:
            xa, ya = verts[a]; xb, yb = verts[b]
            mx, my = (xa + xb) * 0.5, (ya + yb) * 0.5
            conn[a].append((mx, my)); conn[b].append((mx, my))
        centers = []
        for mids in conn.values():
            if mids:
                cx = sum(x for x, _ in mids) / len(mids)
                cy = sum(y for _, y in mids) / len(mids)
                centers.append((cx, cy))
        return centers

    def clip_poly_halfplane(poly, nx, ny, c):
        if not poly: return []
        out, sx, sy = [], *poly[-1]
        sv = nx * sx + ny * sy - c
        for ex, ey in poly:
            ev = nx * ex + ny * ey - c
            s_in, e_in = sv <= 0.0, ev <= 0.0
            if s_in and e_in: out.append((ex, ey))
            elif s_in and not e_in or (not s_in and e_in):
                t = sv / (sv - ev) if abs(sv - ev) > 1e-12 else 0.0
                out.append((sx + t * (ex - sx), sy + t * (ey - sy)))
                if not s_in and e_in: out.append((ex, ey))
            sx, sy, sv = ex, ey, ev
        return out

    def poly_centroid(poly):
        n = len(poly)
        if n == 0: return None
        if n == 1: return poly[0]
        if n == 2: return ((poly[0][0] + poly[1][0]) * 0.5, (poly[0][1] + poly[1][1]) * 0.5)
        A = cx = cy = 0.0
        for i in range(n):
            x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
            cross = x1 * y2 - x2 * y1
            A += cross; cx += (x1 + x2) * cross; cy += (y1 + y2) * cross
        if abs(A) < 1e-12:
            return (sum(x for x, _ in poly)/n, sum(y for _, y in poly)/n)
        A *= 0.5; cx /= 6.0 * A; cy /= 6.0 * A
        return (cx, cy)

    minx, maxx = min(x for x, _ in verts), max(x for x, _ in verts)
    miny, maxy = min(y for _, y in verts), max(y for _, y in verts)
    width, height = maxx - minx, maxy - miny
    rect = [(minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)]
    offsets = [(-width, -height), (0, -height), (width, -height),
               (-width, 0), (0, 0), (width, 0),
               (-width, height), (0, height), (width, height)]
    sites_tiled = [(x + ox, y + oy) for ox, oy in offsets for (x, y) in sites]
    base_start, base_end = len(sites) * 4, len(sites) * 5
    centers = []
    for k in range(base_start, base_end):
        px, py = sites_tiled[k]; poly = list(rect)
        for j, (qx, qy) in enumerate(sites_tiled):
            if j == k: continue
            nx, ny = qx - px, qy - py
            c = 0.5 * ((qx*qx + qy*qy) - (px*px + py*py))
            poly = clip_poly_halfplane(poly, nx, ny, c)
            if not poly: break
        if not poly: continue
        cent = poly_centroid(poly)
        if not cent: continue
        cx, cy = cent
        if isfinite(cx) and isfinite(cy):
            cx, cy = max(minx, min(cx, maxx)), max(miny, min(cy, maxy))
            centers.append((cx, cy))
    return centers

def placement_voronoi_edges(verts, edges):
    return [((verts[a][0] + verts[b][0]) * 0.5, (verts[a][1] + verts[b][1]) * 0.5) for a, b in edges]

# ---------------------------------------------------------
# Layer Builders 
# ---------------------------------------------------------

def build_lines_layer(name, verts2d, edges, thickness):
    if thickness <= 0 or not edges:
        return None
    halfw = thickness * 0.5
    v, f = [], []
    for (a, b) in edges:
        quad = add_strip_quads(verts2d[a], verts2d[b], halfw)
        if not quad: continue
        base = len(v)
        v.extend(quad)
        f.append((base, base+1, base+2, base+3))
    return make_mesh_faces(name, v, f) if f else None

def build_subgrid_layer(name, sub_fn, factor, thickness):
    if factor <= 1:
        return None
    v2, e2, _ = sub_fn(int(factor))
    return build_lines_layer(name, v2, e2, thickness)

def build_dots_or_rings(name, points, r_outer, r_inner, segs, size_rand, seed):
    if r_outer <= 0 or not points:
        return None
    rng = random.Random(int(seed))
    v, f = [], []
    for c in points:
        s_outer = vary_size(r_outer, size_rand, rng)
        s_inner = min(vary_size(r_inner, size_rand, rng), max(0.0, s_outer - 1e-6)) if r_inner > 0 else 0.0
        if s_inner > 1e-9:
            dv, df = add_ring_ngon(c, s_inner, s_outer, segs)
        else:
            dv, df = add_disc_ngon(c, s_outer, segs)
        if not df: continue
        base = len(v)
        v.extend(dv)
        f.extend(tuple(base + idx for idx in face) for face in df)
    return make_mesh_faces(name, v, f) if f else None

def build_crosses(name, points, size, thickness, size_rand, seed):
    if size <= 0 or thickness <= 0 or not points:
        return None
    rng = random.Random(int(seed))
    halfw = thickness * 0.5
    v, f = [], []
    for c in points:
        s = vary_size(size, size_rand, rng)
        dv, df = add_cross_quads(c, s, halfw)
        if not df: continue
        base = len(v)
        v.extend(dv)
        f.extend(tuple(base + idx for idx in face) for face in df)
    return make_mesh_faces(name, v, f) if f else None

def build_ticks_points(name, points, length, thickness, angle_deg, size_rand, seed):
    if length <= 0 or thickness <= 0 or not points:
        return None
    rng = random.Random(int(seed))
    v, f = [], []
    a = radians(float(angle_deg))
    ux, uy = (cos(a), sin(a))
    halfw = thickness * 0.5
    for (x, y) in points:
        L = vary_size(length, size_rand, rng)
        half_len = L * 0.5
        p0 = (x - ux * half_len, y - uy * half_len)
        p1 = (x + ux * half_len, y + uy * half_len)
        quad = add_strip_quads(p0, p1, halfw)
        if not quad: continue
        base = len(v)
        v.extend(quad)
        f.append((base, base+1, base+2, base+3))
    return make_mesh_faces(name, v, f) if f else None

def build_ticks_edge_path(name, verts2d, edges, length, step, thickness, size_rand, seed):
    if length <= 0 or step <= 0 or thickness <= 0 or not edges:
        return None
    rng = random.Random(int(seed))
    v, f = [], []
    halfw = thickness * 0.5
    for (a, b) in edges:
        x1, y1 = verts2d[a]; x2, y2 = verts2d[b]
        dx, dy = x2 - x1, y2 - y1
        L = hypot(dx, dy)
        if L < 1e-8: continue
        n_ticks = int(L / step)
        if n_ticks < 1: continue
        for i in range(1, n_ticks + 1):
            t = min(1.0, i * step / L)
            mx = x1 + dx * t; my = y1 + dy * t
            px, py = -dy / L, dx / L  
            cur_len = vary_size(length, size_rand, rng)
            a0 = (mx - (px * cur_len * 0.5), my - (py * cur_len * 0.5))
            a1 = (mx + (px * cur_len * 0.5), my + (py * cur_len * 0.5))
            quad = add_strip_quads(a0, a1, halfw)
            if not quad: continue
            base = len(v)
            v.extend(quad)
            f.append((base, base+1, base+2, base+3))
    return make_mesh_faces(name, v, f) if f else None

def build_squares(name, points, size, inner, size_rand, seed):
    if size <= 0 or not points:
        return None
    rng = random.Random(int(seed))
    v, f = [], []
    for c in points:
        s_out = vary_size(size, size_rand, rng)
        s_in = min(vary_size(inner, size_rand, rng), max(0.0, s_out - 1e-6)) if inner > 0 else 0.0
        dv, df = add_square_ring(c, s_out, s_in)
        if not df: continue
        base = len(v)
        v.extend(dv)
        f.extend(tuple(base + idx for idx in face) for face in df)
    return make_mesh_faces(name, v, f) if f else None

# ---------------------------------------------------------
# Point Computation per Layer
# ---------------------------------------------------------

def compute_layer_points(
    p, base_cols, base_rows, base_step_x, base_step_y, scale,
    intersections, edges, sub_fn, mode, density, rand_count, spacing, seed
):
    shape = p.grid_shape
    bounds = bounds_from_points(intersections)
    d = max(0.0, float(density))

    def dense_data(f):
        if f == 1: return intersections, edges
        v2, e2, _ = sub_fn(int(f)); return v2, e2

    if mode == "RANDOM":
        return filter_by_spacing(placement_random(bounds, rand_count, seed=seed), spacing)

    if mode == "INTERSECT":
        if shape == "CIRCULAR":
            pts = placement_circular_intersections(p.circ_rings, p.circ_segments, p.circ_inner_radius, p.circ_radius, p.grid_scale)
        elif shape == "HEXAGONAL":
            pts = placement_hex_intersections(p.hex_rings, p.hex_radius, p.grid_scale)
        elif shape == "VORONOI":
            pts = placement_voronoi_intersections(intersections)
        else:
            f, target, _ = factor_for_density_intersections(base_cols, base_rows, d)
            v2, e2 = dense_data(f)
            pts_all = placement_intersections(v2)
            if d < 1.0:
                base_pts = placement_intersections(intersections)
                pts = densify_and_sample(base_pts, target)
            else:
                pts = densify_and_sample(pts_all, target)
        return filter_by_spacing(pts, spacing)

    if mode == "CENTER":
        if shape == "CIRCULAR":
            pts = placement_circular_centers_exact(p.circ_rings, p.circ_segments, p.circ_inner_radius, p.circ_radius, p.grid_scale)
        elif shape == "HEXAGONAL":
            pts = placement_hex_centers(p.hex_rings, p.hex_radius, p.grid_scale)
        elif shape == "VORONOI":
            pts = placement_voronoi_centers(intersections, edges, p.voro_sites if hasattr(p, "voro_sites") else None)
        else:
            f, target, _ = factor_for_density_centers(base_cols, base_rows, d)
            c2, r2 = (base_cols - 1) * f + 1, (base_rows - 1) * f + 1
            step_fx, step_fy = base_step_x / f, base_step_y / f
            pts_all = placement_centers(c2, r2, step_fx, step_fy, scale)
            if d < 1.0:
                base_pts = placement_centers(base_cols, base_rows, base_step_x, base_step_y, scale)
                pts = densify_and_sample(base_pts, target)
            else:
                pts = densify_and_sample(pts_all, target)
        return filter_by_spacing(pts, spacing)

    if mode == "EDGE":
        if shape == "CIRCULAR":
            pts = placement_circular_edges_exact(intersections, edges)
        elif shape == "HEXAGONAL":
            pts = placement_hex_edges(p.hex_rings, p.hex_radius, p.grid_scale)
        elif shape == "VORONOI":
            pts = placement_voronoi_edges(intersections, edges)
        else:
            f, target, _ = factor_for_density_edges(base_cols, base_rows, d)
            v2, e2 = dense_data(f)
            pts_all = placement_edge_midpoints(v2, e2)
            if d < 1.0:
                base_pts = placement_edge_midpoints(intersections, edges)
                pts = densify_and_sample(base_pts, target)
            else:
                pts = densify_and_sample(pts_all, target)
        return filter_by_spacing(pts, spacing)

    return []

# ---------------------------------------------------------
# Build / Update
# ---------------------------------------------------------

def get_or_create_parent(context):
    obj = context.active_object
    if obj and obj.type == "EMPTY" and obj.get("grid_generator"):
        return obj
    if obj and obj.parent and obj.parent.get("grid_generator"):
        return obj.parent
    parent = bpy.data.objects.new("Grid_Square", None)
    parent.empty_display_type = 'PLAIN_AXES'
    parent["grid_generator"] = True
    ensure_link(parent)
    return parent

def rebuild_grid(obj):
    if not obj or obj.type != "EMPTY" or "grid_generator" not in obj: return False

    p = bpy.context.scene.gridgen_props
    shape = p.grid_shape

    if shape == "RECTANGULAR":
        intersections, edges, sub_fn = grid_square_data(p.rect_cols, p.rect_rows, p.rect_step_x, p.rect_step_y, p.grid_scale)
        base_cols, base_rows = p.rect_cols, p.rect_rows
        base_step_x, base_step_y = p.rect_step_x, p.rect_step_y

    elif shape == "CIRCULAR":
        intersections, edges, sub_fn = grid_circular_data(p.circ_rings, p.circ_segments, p.circ_radius, p.grid_scale, p.circ_inner_radius)
        base_cols, base_rows = p.circ_rings + 1, p.circ_segments
        base_step_x = base_step_y = p.circ_radius - p.circ_inner_radius

    elif shape == "HEXAGONAL":
        intersections, edges, sub_fn = grid_hexagonal_data(p.hex_rings, p.hex_radius, p.grid_scale)
        base_cols = p.hex_rings
        base_rows = 6 * (p.hex_rings + 1)
        base_step_x = base_step_y = p.hex_radius

    elif shape == "VORONOI":
        intersections, edges, sub_fn, p.voro_sites = grid_voronoi_data(p.voro_cols, p.voro_rows, p.rect_step_x, p.rect_step_y, p.grid_scale, relax_iter=p.voro_relax)
        base_cols, base_rows = p.voro_cols, p.voro_rows
        base_step_x, base_step_y = p.rect_step_x, p.rect_step_y
    else:
        return False

    safe_delete_children(obj)

    if p.show_main:
        ob = build_lines_layer("GG_Main", intersections, edges, p.main_thick)
        if ob: ob.parent = obj

    if p.show_sub and p.sub_factor > 1:
        ob = build_subgrid_layer("GG_Subgrid", sub_fn, p.sub_factor, p.sub_thick)
        if ob: ob.parent = obj

    if p.show_dots:
        if shape == "CIRCULAR" and p.dot_placement == "CENTER":
            base_pts = placement_circular_centers_topology(intersections, p.circ_segments, p.circ_rings)
        elif shape == "HEXAGONAL" and p.dot_placement == "CENTER":
            base_pts = placement_hex_centers(p.hex_rings, p.hex_radius, p.grid_scale)
        else:
            base_pts = compute_layer_points(p, base_cols, base_rows, base_step_x, base_step_y, p.grid_scale, intersections, edges, sub_fn, p.dot_placement, p.dot_density, p.dot_random_count, p.dot_spacing, p.dot_seed)
        pts = sample_with_density(base_pts, p.dot_density)
        pts = filter_by_spacing(pts, p.dot_spacing)
        ob = build_dots_or_rings("GG_Dots", pts, p.dot_radius, p.dot_inner_radius, p.dot_segments, p.dot_size_random, p.dot_seed)
        if ob: ob.parent = obj

    if p.show_crosses:
        if shape == "CIRCULAR" and p.cross_placement == "CENTER":
            base_pts = placement_circular_centers_topology(intersections, p.circ_segments, p.circ_rings)
        elif shape == "HEXAGONAL" and p.cross_placement == "CENTER":
            base_pts = placement_hex_centers(p.hex_rings, p.hex_radius, p.grid_scale)
        else:
            base_pts = compute_layer_points(p, base_cols, base_rows, base_step_x, base_step_y, p.grid_scale, intersections, edges, sub_fn, p.cross_placement, p.cross_density, p.cross_random_count, p.cross_spacing, p.cross_seed)
        pts = sample_with_density(base_pts, p.cross_density)
        pts = filter_by_spacing(pts, p.cross_spacing)
        ob = build_crosses("GG_Crosses", pts, p.cross_size, p.cross_thick, p.cross_size_random, p.cross_seed)
        if ob: ob.parent = obj

    if p.show_squares:
        if shape == "CIRCULAR" and p.square_placement == "CENTER":
            base_pts = placement_circular_centers_topology(intersections, p.circ_segments, p.circ_rings)
        elif shape == "HEXAGONAL" and p.square_placement == "CENTER":
            base_pts = placement_hex_centers(p.hex_rings, p.hex_radius, p.grid_scale)
        else:
            base_pts = compute_layer_points(p, base_cols, base_rows, base_step_x, base_step_y, p.grid_scale, intersections, edges, sub_fn, p.square_placement, p.square_density, p.square_random_count, p.square_spacing, p.square_seed)
        pts = sample_with_density(base_pts, p.square_density)
        pts = filter_by_spacing(pts, p.square_spacing)
        ob = build_squares("GG_Squares", pts, p.square_size, p.square_inner, p.square_size_random, p.square_seed)
        if ob: ob.parent = obj

    if p.show_ticks:
        if p.tick_placement == "EDGE_PATH":
            effective_step = max(1e-6, p.tick_step / max(0.1, p.tick_density))
            ob = build_ticks_edge_path("GG_Ticks", intersections, edges, p.tick_length, effective_step, p.tick_thick, p.tick_size_random, p.tick_seed)
        else:
            if shape == "CIRCULAR" and p.tick_placement == "CENTER":
                base_pts = placement_circular_centers_topology(intersections, p.circ_segments, p.circ_rings)
            elif shape == "HEXAGONAL" and p.tick_placement == "CENTER":
                base_pts = placement_hex_centers(p.hex_rings, p.hex_radius, p.grid_scale)
            else:
                base_pts = compute_layer_points(p, base_cols, base_rows, base_step_x, base_step_y, p.grid_scale, intersections, edges, sub_fn, p.tick_placement, p.tick_density, p.tick_random_count, p.tick_spacing_points, p.tick_seed)
            pts = sample_with_density(base_pts, p.tick_density)
            pts = filter_by_spacing(pts, p.tick_spacing_points)
            ob = build_ticks_points("GG_Ticks", pts, p.tick_length, p.tick_thick, p.tick_angle, p.tick_size_random, p.tick_seed)
        if ob: ob.parent = obj

    obj.name = f"Grid_{shape.capitalize()}"
    return True

def generate_grid(context):
    p = context.scene.gridgen_props
    obj = context.active_object
    keys = (
        "grid_shape", "grid_scale", "sub_factor", "show_main", "show_sub",
        "show_dots", "show_crosses", "show_squares", "show_ticks", "show_frame",
        "main_thick", "sub_thick", "dot_radius", "dot_inner_radius",
        "dot_segments", "dot_size_random", "dot_seed", "cross_size",
        "cross_thick", "cross_size_random", "cross_seed", "square_size",
        "square_inner", "square_size_random", "square_seed", "tick_length",
        "tick_thick", "tick_angle", "tick_step", "tick_density",
        "tick_spacing_points", "tick_random_count", "tick_seed", "frame_thick"
    )

    target = None
    if obj and obj.type == "EMPTY" and "grid_generator" in obj and obj.select_get():
        target = obj
    elif obj and obj.parent and obj.parent.type == "EMPTY" and "grid_generator" in obj.parent and obj.parent.select_get():
        target = obj.parent

    if target:
        for k in keys:
            if hasattr(p, k): target[k] = getattr(p, k)
        view_layer = context.view_layer
        active_before, selected_before = view_layer.objects.active, [o for o in view_layer.objects if o.select_get()]
        rebuild_grid(target)
        for o in selected_before: o.select_set(True)
        view_layer.objects.active = active_before
        target.select_set(True)
        view_layer.objects.active = target
        target.name = f"Grid_{p.grid_shape.capitalize()}"
        return target

    new_obj = bpy.data.objects.new(f"Grid_{p.grid_shape.capitalize()}", None)
    new_obj["grid_generator"] = True
    context.collection.objects.link(new_obj)
    context.view_layer.objects.active = new_obj
    new_obj.select_set(True)
    for k in keys:
        if hasattr(p, k): new_obj[k] = getattr(p, k)
    rebuild_grid(new_obj)
    context.view_layer.objects.active = new_obj
    new_obj.select_set(True)
    return new_obj

def update_grid(self, context):
    p = context.scene.gridgen_props
    if not p.live_update: return
    obj = context.active_object
    if not obj: return

    target = None
    if obj.type == "EMPTY" and "grid_generator" in obj and obj.select_get():
        target = obj
    elif obj.parent and obj.parent.type == "EMPTY" and "grid_generator" in obj.parent and obj.parent.select_get():
        target = obj.parent
    if not target: return

    view_layer = context.view_layer
    active_before, selected_before = view_layer.objects.active, [o for o in view_layer.objects if o.select_get()]
    rebuild_grid(target)
    for o in selected_before: o.select_set(True)
    view_layer.objects.active = active_before

# ---------------------------------------------------------
# Properties
# ---------------------------------------------------------

class GridGenProperties(bpy.types.PropertyGroup):

    live_update: bpy.props.BoolProperty(name="Live Update", default=False)
    grid_shape: bpy.props.EnumProperty(name="Shape", description="Base geometry of the grid", items=[("RECTANGULAR", "Rectangular", "Classic rows × columns grid"), ("CIRCULAR", "Circular", "Concentric rings with spokes"), ("HEXAGONAL", "Hexagonal", "Flat-top hexagonal tiling"), ("VORONOI", "Voronoi", "Relaxed Voronoi cells")], default="RECTANGULAR", update=update_grid)

    # Rectangular Grid Controls
    rect_cols: bpy.props.IntProperty(name="Columns", default=20, min=2, max=100, subtype='FACTOR', update=update_grid)
    rect_rows: bpy.props.IntProperty(name="Rows", default=20, min=2, max=100, subtype='FACTOR', update=update_grid)
    rect_step_x: bpy.props.FloatProperty(name="Step X", default=1.0, min=0.01, max=10, subtype='FACTOR', update=update_grid)
    rect_step_y: bpy.props.FloatProperty(name="Step Y", default=1.0, min=0.01, max=10, subtype='FACTOR', update=update_grid)

    # Circular Grid Controls
    circ_rings: bpy.props.IntProperty(name="Rings", default=8, min=1, max=128, subtype='FACTOR', update=update_grid)
    circ_segments: bpy.props.IntProperty(name="Segments per Ring", default=24, min=6, max=128, subtype='FACTOR', update=update_grid)
    circ_radius: bpy.props.FloatProperty(name="Outer Radius", default=10.0, min=0.1, max=100.0, subtype='FACTOR', update=update_grid)
    circ_inner_radius: bpy.props.FloatProperty(name="Inner Radius", default=0.0, min=0.0, max=100.0, subtype='FACTOR', update=update_grid)

    # Hexagonal Grid Controls
    hex_rings: bpy.props.IntProperty(name="Rings", default=6, min=1, max=50, subtype='FACTOR', update=update_grid)
    hex_radius: bpy.props.FloatProperty(name="Hex Radius", default=1.0, min=0.01, max=100.0, subtype='FACTOR', update=update_grid)

    # Voronoi Grid Controls
    voro_cols: bpy.props.IntProperty(name="Site Columns", default=15, min=2, max=100, subtype='FACTOR', update=update_grid)
    voro_rows: bpy.props.IntProperty(name="Site Rows", default=15, min=2, max=100, subtype='FACTOR', update=update_grid)
    voro_relax: bpy.props.IntProperty(name="Relax Iterations", default=2, min=0, max=20, subtype='FACTOR', update=update_grid)

    # Global Scale
    grid_scale: bpy.props.FloatProperty(name="Scale", default=1.0, min=0.01, max=10.0, subtype='FACTOR', update=update_grid)

    # Main Lines
    show_main: bpy.props.BoolProperty(name="Main Lines", default=False, update=update_grid)
    main_thick: bpy.props.FloatProperty(name="Main Thickness", default=0.05, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)

    # Subgrid Lines
    show_sub: bpy.props.BoolProperty(name="Subgrid Lines", default=True, update=update_grid)
    sub_factor: bpy.props.IntProperty(name="Subgrid Factor", default=5, min=2, max=20, subtype='FACTOR', update=update_grid)
    sub_thick: bpy.props.FloatProperty(name="Subgrid Thickness", default=0.02, min=0.0, max=0.1, subtype='FACTOR', update=update_grid)

    # Dots / Rings
    show_dots: bpy.props.BoolProperty(name="Dots / Rings", default=False, update=update_grid)
    dot_radius: bpy.props.FloatProperty(name="Outer Radius", default=0.06, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    dot_inner_radius: bpy.props.FloatProperty(name="Inner Radius", default=0.00, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    dot_segments: bpy.props.IntProperty(name="Segments", default=12, min=6, max=128, subtype='FACTOR', update=update_grid)
    dot_placement: bpy.props.EnumProperty(name="Dot Placement", items=[("INTERSECT", "Intersections", ""), ("CENTER", "Centers", ""), ("EDGE", "Edge Midpoints", ""), ("RANDOM", "Random", "")], default="INTERSECT", update=update_grid)
    dot_density: bpy.props.FloatProperty(name="Dot Density", default=1.0, min=0.1, max=2.0, subtype='FACTOR', update=update_grid)
    dot_random_count: bpy.props.IntProperty(name="Dot Count (Random)", default=100, min=0, max=10000, subtype='FACTOR', update=update_grid)
    dot_spacing: bpy.props.FloatProperty(name="Dot Spacing", default=0.0, min=0.0, max=10.0, subtype='FACTOR', update=update_grid)
    dot_size_random: bpy.props.FloatProperty(name="Size Random %", default=0.0, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    dot_seed: bpy.props.IntProperty(name="Dot Seed", default=11, min=0, subtype='FACTOR', update=update_grid)

    # Crosses
    show_crosses: bpy.props.BoolProperty(name="Crosses", default=False, update=update_grid)
    cross_size: bpy.props.FloatProperty(name="Cross Size", default=0.20, min=0.0, max=10.0, subtype='FACTOR', update=update_grid)
    cross_thick: bpy.props.FloatProperty(name="Cross Thickness", default=0.04, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    cross_placement: bpy.props.EnumProperty(name="Cross Placement", items=[("INTERSECT", "Intersections", ""), ("CENTER", "Centers", ""), ("EDGE", "Edge Midpoints", ""), ("RANDOM", "Random", "")], default="INTERSECT", update=update_grid)
    cross_density: bpy.props.FloatProperty(name="Cross Density", default=1.0, min=0.1, max=2.0, subtype='FACTOR', update=update_grid)
    cross_random_count: bpy.props.IntProperty(name="Cross Count (Random)", default=50, min=0, max=1000, subtype='FACTOR', update=update_grid)
    cross_spacing: bpy.props.FloatProperty(name="Cross Spacing", default=0.0, min=0.0, max=10.0, subtype='FACTOR', update=update_grid)
    cross_size_random: bpy.props.FloatProperty(name="Size Random %", default=0.0, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    cross_seed: bpy.props.IntProperty(name="Cross Seed", default=22, min=0, subtype='FACTOR', update=update_grid)

    # Squares
    show_squares: bpy.props.BoolProperty(name="Squares", default=False, update=update_grid)
    square_size: bpy.props.FloatProperty(name="Square Size", default=0.20, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    square_inner: bpy.props.FloatProperty(name="Inner Size", default=0.00, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    square_placement: bpy.props.EnumProperty(name="Square Placement", items=[("INTERSECT", "Intersections", ""), ("CENTER", "Centers", ""), ("EDGE", "Edge Midpoints", ""), ("RANDOM", "Random", "")], default="CENTER", update=update_grid)
    square_density: bpy.props.FloatProperty(name="Square Density", default=1.0, min=0.1, max=2.0, subtype='FACTOR', update=update_grid)
    square_random_count: bpy.props.IntProperty(name="Square Count (Random)", default=64, min=0, max=1000, subtype='FACTOR', update=update_grid)
    square_spacing: bpy.props.FloatProperty(name="Square Spacing", default=0.0, min=0.0, max=10.0, subtype='FACTOR', update=update_grid)
    square_size_random: bpy.props.FloatProperty(name="Size Random %", default=0.0, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    square_seed: bpy.props.IntProperty(name="Square Seed", default=33, min=0, subtype='FACTOR', update=update_grid)

    # Ticks
    show_ticks: bpy.props.BoolProperty(name="Ticks", default=False, update=update_grid)
    tick_length: bpy.props.FloatProperty(name="Tick Length", default=0.15, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    tick_thick: bpy.props.FloatProperty(name="Tick Thickness", default=0.02, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    tick_angle: bpy.props.FloatProperty(name="Tick Angle (°)", default=90.0, min=-360.0, max=360.0, subtype='FACTOR', update=update_grid)
    tick_step: bpy.props.FloatProperty(name="Tick Spacing (Edge Path)", default=0.5, min=0.001, max=1.0, subtype='FACTOR', update=update_grid)
    tick_placement: bpy.props.EnumProperty(name="Tick Placement", items=[("INTERSECT", "Intersections", ""), ("CENTER", "Centers", ""), ("EDGE", "Edge Midpoints", ""), ("RANDOM", "Random", ""), ("EDGE_PATH", "Edge Path", "March along edges using Tick Spacing")], default="EDGE_PATH", update=update_grid)
    tick_density: bpy.props.FloatProperty(name="Tick Density", default=1.0, min=0.1, max=2.0, subtype='FACTOR', update=update_grid)
    tick_random_count: bpy.props.IntProperty(name="Tick Count (Random)", default=150, min=0, max=10000000, subtype='FACTOR', update=update_grid)
    tick_spacing_points: bpy.props.FloatProperty(name="Tick Spacing (Points)", default=0.0, min=0.0, max=10000.0, subtype='FACTOR', update=update_grid)
    tick_size_random: bpy.props.FloatProperty(name="Size Random %", default=0.0, min=0.0, max=1.0, subtype='FACTOR', update=update_grid)
    tick_seed: bpy.props.IntProperty(name="Tick Seed", default=44, min=0, subtype='FACTOR', update=update_grid)

# ---------------------------------------------------------
# Operator 
# ---------------------------------------------------------

class GRIDGEN_OT_generate(bpy.types.Operator):
    bl_idname = "grid.generate_fast"
    bl_label = "Generate Grid"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        generate_grid(context)
        return {"FINISHED"}
    
class GRIDGEN_OT_reset(bpy.types.Operator):
    bl_idname = "grid.reset_sliders"
    bl_label = "Reset"
    bl_options = {"UNDO"}

    def execute(self, context):
        p = context.scene.gridgen_props

        keep_toggles = {k: getattr(p, k) for k in dir(p) if k.startswith("show_")}

        live_state = p.live_update

        for prop_name, prop in p.bl_rna.properties.items():
            if not prop.is_readonly and not prop_name.startswith("rna_"):
                try:
                    default_val = prop.default
                    setattr(p, prop_name, default_val)
                except Exception:
                    pass

        for k, v in keep_toggles.items():
            setattr(p, k, v)
        p.live_update = live_state

        if p.live_update:
            update_grid(p, context)

        self.report({'INFO'}, "Grid sliders reset to default values.")
        return {'FINISHED'}

class GRIDGEN_OT_delete(bpy.types.Operator):
    bl_idname = "grid.delete_selected"
    bl_label = "Delete Grid"
    bl_options = {"UNDO"}

    def execute(self, context):
        o = context.object
        target = None

        if o and o.type == "EMPTY" and "grid_generator" in o:
            target = o
        elif o and o.parent and o.parent.type == "EMPTY" and "grid_generator" in o.parent:
            target = o.parent

        if not target:
            self.report({'WARNING'}, "No grid selected.")
            return {'CANCELLED'}

        safe_delete_children(target)

        deactivate_all()
        target.select_set(True)
        bpy.ops.object.delete()

        self.report({'INFO'}, "Grid and all child objects deleted.")
        return {'FINISHED'}

# ---------------------------------------------------------
# UI
# ---------------------------------------------------------

class VIEW3D_PT_grid_generator(bpy.types.Panel):
    bl_label = "Grid"
    bl_idname = "VIEW3D_PT_grid_generator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Grid"

    def draw(self, context):
        if relay_updater:
            relay_updater.draw(self.layout)
        layout = self.layout
        p = context.scene.gridgen_props
        o = context.object

        layout.operator("grid.generate_fast", icon="MESH_GRID")

        row = layout.row(align=True)
        row.prop(p, "live_update", toggle=True)
        row.operator("grid.reset_sliders", text="Reset")

        layout.separator(factor=0.5)

        layout.prop(p, "grid_shape")
        shape = p.grid_shape

        if shape == "RECTANGULAR":
            layout.prop(p, "rect_cols")
            layout.prop(p, "rect_rows")
            layout.prop(p, "rect_step_x")
            layout.prop(p, "rect_step_y")

        elif shape == "CIRCULAR":
            layout.prop(p, "circ_rings")
            layout.prop(p, "circ_segments")
            layout.prop(p, "circ_radius")
            layout.prop(p, "circ_inner_radius")

        elif shape == "HEXAGONAL":
            layout.prop(p, "hex_rings")
            layout.prop(p, "hex_radius")

        elif shape == "VORONOI":
            layout.prop(p, "voro_cols")
            layout.prop(p, "voro_rows")
            layout.prop(p, "voro_relax")
            layout.prop(p, "rect_step_x", text="Site Step X")
            layout.prop(p, "rect_step_y", text="Site Step Y")

        layout.prop(p, "grid_scale")

        # --- Main lines ---
        layout.prop(p, "show_main", toggle=True)
        if p.show_main:
            layout.prop(p, "main_thick")

        # --- Subgrid ---
        layout.prop(p, "show_sub", toggle=True)
        if p.show_sub:
            layout.prop(p, "sub_factor")
            layout.prop(p, "sub_thick")

        # --- Dots ---
        layout.prop(p, "show_dots", toggle=True)
        if p.show_dots:
            layout.prop(p, "dot_placement")
            layout.prop(p, "dot_radius")
            layout.prop(p, "dot_inner_radius")
            layout.prop(p, "dot_segments")
            if p.dot_placement == "RANDOM":
                layout.prop(p, "dot_random_count")
            else:
                layout.prop(p, "dot_density")
            layout.prop(p, "dot_spacing")
            layout.prop(p, "dot_size_random")
            layout.prop(p, "dot_seed")

        # --- Crosses ---
        layout.prop(p, "show_crosses", toggle=True)
        if p.show_crosses:
            layout.prop(p, "cross_placement")
            layout.prop(p, "cross_size")
            layout.prop(p, "cross_thick")
            if p.cross_placement == "RANDOM":
                layout.prop(p, "cross_random_count")
            else:
                layout.prop(p, "cross_density")
            layout.prop(p, "cross_spacing")
            layout.prop(p, "cross_size_random")
            layout.prop(p, "cross_seed")

        # --- Squares ---
        layout.prop(p, "show_squares", toggle=True)
        if p.show_squares:
            layout.prop(p, "square_placement")
            layout.prop(p, "square_size")
            layout.prop(p, "square_inner")
            if p.square_placement == "RANDOM":
                layout.prop(p, "square_random_count")
            else:
                layout.prop(p, "square_density")
            layout.prop(p, "square_spacing")
            layout.prop(p, "square_size_random")
            layout.prop(p, "square_seed")

        # --- Ticks ---
        layout.prop(p, "show_ticks", toggle=True)
        if p.show_ticks:
            layout.prop(p, "tick_placement")
            layout.prop(p, "tick_length")
            layout.prop(p, "tick_thick")

            if p.tick_placement == "EDGE_PATH":
                layout.prop(p, "tick_step")
                layout.prop(p, "tick_density")
            else:
                layout.prop(p, "tick_angle")
                if p.tick_placement == "RANDOM":
                    layout.prop(p, "tick_random_count")
                else:
                    layout.prop(p, "tick_density")
                layout.prop(p, "tick_spacing_points")

            layout.prop(p, "tick_size_random")
            layout.prop(p, "tick_seed")

        layout.separator(factor=0.5)

        target = None
        if o and o.type == "EMPTY" and "grid_generator" in o and o.select_get():
            target = o
        elif o and o.parent and o.parent.type == "EMPTY" and "grid_generator" in o.parent and o.parent.select_get():
            target = o.parent

        if target:
            layout.operator("grid.delete_selected", icon="TRASH", text="Delete Grid")
            layout.separator(factor=0.3)
            layout.label(text=f"Editing Grid: {target.name}", icon="MESH_GRID")
        else:
            layout.label(text="No grid selected", icon="INFO")

# ---------------------------------------------------------
# Registration
# ---------------------------------------------------------

classes = (
    GridGenProperties,
    GRIDGEN_OT_generate,
    GRIDGEN_OT_reset,
    GRIDGEN_OT_delete,
    VIEW3D_PT_grid_generator, 
)

def register():
    if relay_updater:
        relay_updater.register("blender-grid")
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.gridgen_props = bpy.props.PointerProperty(type=GridGenProperties)

def unregister():
    if relay_updater:
        relay_updater.unregister()
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.gridgen_props

if __name__ == "__main__":
    register()