"""SDF raymarcher — 'the monolith approach': alien dunes, ringed gas giant,
receding monolith field with cyan seams. Palette matches the console SVG."""
import numpy as np
from PIL import Image

W, H = 1920, 640
OUT = "alien_hero.png"

# ── palette (console-matched) ────────────────────────────────────────────────
CYAN  = np.array([0.34, 0.84, 0.88])
AMBER = np.array([1.00, 0.71, 0.33])
FOG   = np.array([0.016, 0.028, 0.052])
SKY_T = np.array([0.004, 0.007, 0.020])   # zenith
SKY_B = np.array([0.030, 0.042, 0.080])   # horizon

rng = np.random.default_rng(2077)

def hash2(ix, iz):
    v = np.sin(ix * 127.1 + iz * 311.7) * 43758.5453
    return v - np.floor(v)

# ── SDF scene ────────────────────────────────────────────────────────────────
def ground_h(x, z):
    return (0.55 * np.sin(0.13 * x + 0.9) * np.sin(0.10 * z)
            + 0.22 * np.sin(0.31 * x - 0.4) * np.sin(0.27 * z + 1.7)
            + 0.08 * np.sin(0.9 * x + 0.5 * z))

MONO_REP = 14.0     # spacing of monolith rows along z
def scene(p):
    """returns (distance, material) material: 0 ground, 1 monolith"""
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    d_ground = y - ground_h(x, z)

    # monolith field: two staggered rows flanking the camera path
    zc = np.round(z / MONO_REP)
    qz = z - zc * MONO_REP
    h = 5.5 + 3.0 * hash2(zc, 1.0)              # per-cell height
    lean = 0.35 * (hash2(zc, 7.0) - 0.5)
    # left row
    qxl = x + 7.5 + lean * y
    dl = _box(qxl, y - h, qz, 0.55, h, 1.1)
    # right row (farther, taller, sparser: drop ~1/3 of cells)
    keepr = hash2(zc, 13.0) > 0.38
    qxr = x - 15.5 - lean * y
    hr = 7.0 + 4.0 * hash2(zc, 3.0)
    dr = _box(qxr, y - hr, qz - 4.0, 0.7, hr, 1.4)
    dr = np.where(keepr, dr, 1e5)
    d_mono = np.minimum(dl, dr)

    d = np.minimum(d_ground, d_mono)
    mat = np.where(d_mono < d_ground, 1.0, 0.0)
    return d, mat

def _box(px, py, pz, bx, by, bz):
    qx, qy, qz = np.abs(px) - bx, np.abs(py) - by, np.abs(pz) - bz
    ax, ay, az = np.maximum(qx, 0), np.maximum(qy, 0), np.maximum(qz, 0)
    outside = np.sqrt(ax*ax + ay*ay + az*az)
    inside = np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0)
    return outside + inside

def normal(p):
    e = 0.02
    d0, _ = scene(p)
    n = np.stack([
        scene(p + np.array([e,0,0]))[0] - d0,
        scene(p + np.array([0,e,0]))[0] - d0,
        scene(p + np.array([0,0,e]))[0] - d0], axis=-1)
    return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9)

# ── camera ───────────────────────────────────────────────────────────────────
cam = np.array([0.0, 2.6, -6.0])
look = np.array([1.2, 3.4, 30.0])
fwd = look - cam; fwd /= np.linalg.norm(fwd)
right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right)
up = np.cross(right, fwd)

u = (np.arange(W) + 0.5) / W * 2 - 1
v = 1 - (np.arange(H) + 0.5) / H * 2
uu, vv = np.meshgrid(u, v)
aspect = W / H
rd = (fwd[None,None,:] + uu[...,None] * right * aspect * 0.62 + vv[...,None] * up * 0.62)
rd = rd / np.linalg.norm(rd, axis=-1, keepdims=True)

# ── lights ───────────────────────────────────────────────────────────────────
planet_dir = np.array([0.42, 0.20, 1.0]); planet_dir /= np.linalg.norm(planet_dir)
key = planet_dir                                # amber key from the planet
fill = np.array([-0.5, 0.35, -0.2]); fill /= np.linalg.norm(fill)

# ── march ────────────────────────────────────────────────────────────────────
MAXD = 220.0
t = np.zeros((H, W))
hit = np.zeros((H, W), dtype=bool)
alive = np.ones((H, W), dtype=bool)
for i in range(140):
    if not alive.any(): break
    p = cam[None,None,:] + rd * t[...,None]
    d, _ = scene(p)
    d = np.where(alive, d, 1e5)
    newly = alive & (d < 0.004 * (1 + t * 0.15))
    hit |= newly
    alive &= ~newly
    t = np.where(alive, np.minimum(t + d * 0.9, MAXD), t)
    alive &= t < MAXD

p_hit = cam[None,None,:] + rd * t[...,None]
_, mat = scene(p_hit)
n = normal(p_hit)

# soft shadow toward key light (cheap: 24 steps)
def soft_shadow(p, ldir):
    res = np.ones(p.shape[:-1])
    ts = np.full(p.shape[:-1], 0.15)
    for _ in range(24):
        q = p + ldir[None,None,:] * ts[...,None]
        d, _ = scene(q)
        res = np.minimum(res, np.clip(8.0 * d / np.maximum(ts, 1e-3), 0, 1))
        ts = ts + np.clip(d, 0.08, 2.2)
    return np.clip(res, 0, 1)
sh = soft_shadow(p_hit, key)

ndl_key = np.clip((n * key).sum(-1), 0, 1) * sh
ndl_fill = np.clip((n * fill).sum(-1), 0, 1)
fresnel = np.clip(1 + (rd * n).sum(-1), 0, 1) ** 3

alb_ground = np.array([0.070, 0.082, 0.112])
alb_mono   = np.array([0.050, 0.058, 0.075])
albedo = np.where(mat[...,None] > 0.5, alb_mono, alb_ground)

col = (albedo * (0.10 + 1.9 * ndl_key[...,None] * AMBER + 0.30 * ndl_fill[...,None] * CYAN * np.array([0.7,0.85,1.15]))
       + 0.18 * fresnel[...,None] * CYAN * np.where(mat[...,None] > 0.5, 1.0, 0.25))

# cyan seam: thin vertical emissive slit on monolith faces
x, y, z = p_hit[...,0], p_hit[...,1], p_hit[...,2]
zc = np.round(z / MONO_REP); qz = z - zc * MONO_REP
seam = (mat > 0.5) & (np.abs(qz) < 0.10) & (y < 6.0)
glow = np.exp(-np.abs(qz) * 30.0) * np.exp(-0.10 * y) * 2.2
col = np.where(seam[...,None], col + CYAN[None,None,:] * glow[...,None], col)

# ── sky ──────────────────────────────────────────────────────────────────────
elev = np.clip(rd[...,1], -0.2, 1)
sky = SKY_B[None,None,:] + (SKY_T - SKY_B)[None,None,:] * np.clip(elev*2.4, 0, 1)[...,None]

# stars (only above horizon, sparse hash)
sq = np.floor(rd[...,:2] / np.maximum(np.abs(rd[...,2:3]), .2) * 400)
sv = np.sin(sq[...,0]*127.1 + sq[...,1]*311.7)*43758.5453; sv -= np.floor(sv)
stars = ((sv > 0.9975) & (rd[...,1] > 0.02)).astype(float) * (sv - 0.9975) * 380
sky += stars[...,None] * np.array([0.85, 0.95, 1.0])

# ringed gas giant
cosang = (rd * planet_dir).sum(-1)
ang = np.arccos(np.clip(cosang, -1, 1))
PR = 0.175
pmask = ang < PR
# fake sphere shading: offset from center in screen-ish coords
off = rd - cosang[...,None] * planet_dir[None,None,:]
sn = np.clip(1 - (ang / PR)**2, 0, 1) ** 0.5
lat = (off * up).sum(-1) / PR
bands = 0.5 + 0.5*np.sin(lat * 24 + 1.2)
pcol = (np.array([0.30,0.20,0.13])[None,None,:] * (0.5 + 0.5*bands)[...,None]
        + AMBER[None,None,:] * 0.28 * (sn**3)[...,None])
limb = np.clip((ang / PR - 0.75) * 4, 0, 1)
pcol += AMBER[None,None,:] * (limb * 0.5)[...,None]
sky = np.where(pmask[...,None], pcol, sky)
# planet glow
sky += AMBER[None,None,:] * np.exp(-np.clip(ang - PR, 0, None) * 22)[...,None] * 0.20
# ring: true annulus in a tilted plane through the planet center
D = 60.0                                   # planet center distance
C = planet_dir * D
ring_n = np.array([0.18, 0.94, -0.29]); ring_n /= np.linalg.norm(ring_n)
denom = (rd * ring_n).sum(-1)
t_pl = np.where(np.abs(denom) > 1e-4, (C * ring_n).sum() / denom, -1)
P = rd * t_pl[..., None]
r_in = np.linalg.norm(P - C, axis=-1)
R1, R2 = D * PR * 1.35, D * PR * 2.05
ring_hit = (t_pl > 0) & (r_in > R1) & (r_in < R2)
# ring texture: two density bands + soft edges
band = np.clip((r_in - R1) / (R2 - R1), 0, 1)
dens = (np.exp(-((band - 0.28) / 0.16) ** 2) * 0.9
        + np.exp(-((band - 0.72) / 0.20) ** 2) * 0.55)
edge = np.clip(np.minimum(r_in - R1, R2 - r_in) / (0.08 * (R2 - R1)), 0, 1)
ringi = dens * edge * np.clip(np.abs(denom) * 9, 0.35, 1)
# occlusion: ring behind the planet disc hides; ring in front draws over it
ring_behind = ring_hit & pmask & (t_pl > D)
ring_vis = ring_hit & ~ring_behind
ring_col = AMBER * 0.7 + np.array([0.25, 0.18, 0.10])
sky = np.where(ring_vis[..., None], sky * 0.25 + ring_col[None, None, :] * (ringi * 0.8)[..., None], sky)

# ── composite ────────────────────────────────────────────────────────────────
img = np.where(hit[...,None], col, sky)
fog_f = np.where(hit, 1 - np.exp(-t * 0.016), 0)[...,None]
img = img * (1 - fog_f) + FOG[None,None,:] * fog_f * 1.4
# horizon haze into sky too
img = np.where(~hit[...,None] & (np.abs(rd[...,1:2]) < 0.06),
               img + FOG[None,None,:]*np.exp(-np.abs(rd[...,1:2])*40)*0.8, img)

# tonemap + vignette
img = img / (1 + img)
img = np.clip(img, 0, 1) ** (1/2.2)
vx = (uu**2 + vv**2) * 0.18
img *= (1 - vx)[...,None]

# bloom: blur the bright emissives (seams, planet limb, ring) and add back
from PIL import ImageFilter
emis = np.zeros_like(img)
seam_g = np.where(seam[...,None] & hit[...,None], CYAN[None,None,:] * glow[...,None] * 0.8, 0)
sky_g = np.where(~hit[...,None], np.clip(img - 0.55, 0, None) * 1.2, 0)
emis = seam_g + sky_g
e8 = Image.fromarray((np.clip(emis,0,1)*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(9))
img = np.clip(img + np.asarray(e8, dtype=float)/255.0 * 0.55, 0, 1)

Image.fromarray((img*255).astype(np.uint8)).save(OUT)
print("saved", OUT)
