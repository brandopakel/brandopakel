"""SDF raymarcher — 'somewhere off the central finite curve': a green portal
blazing over alien dunes, monolith corridor receding. Portal is the key light."""
import numpy as np
from PIL import Image, ImageFilter

W, H = 1920, 640
OUT = "portal_dimension.png"

GREEN_CORE = np.array([0.62, 1.00, 0.22])   # portal core (yellow-green, kept saturated)
GREEN_MID  = np.array([0.38, 0.88, 0.16])   # the green
GREEN_DARK = np.array([0.06, 0.30, 0.05])   # swirl troughs
CYAN  = np.array([0.34, 0.84, 0.88])
MOON  = np.array([0.45, 0.55, 0.75])        # cool fill key
FOG   = np.array([0.012, 0.030, 0.030])
SKY_T = np.array([0.004, 0.007, 0.020])
SKY_B = np.array([0.020, 0.038, 0.052])

def hash2(ix, iz):
    v = np.sin(ix * 127.1 + iz * 311.7) * 43758.5453
    return v - np.floor(v)

def ground_h(x, z):
    return (0.55 * np.sin(0.13 * x + 0.9) * np.sin(0.10 * z)
            + 0.22 * np.sin(0.31 * x - 0.4) * np.sin(0.27 * z + 1.7)
            + 0.08 * np.sin(0.9 * x + 0.5 * z))

# portal placement: standing disc, slightly tilted toward camera
P0 = np.array([3.0, 4.9, 21.0])
PN = np.array([-0.22, 0.05, -1.0]); PN /= np.linalg.norm(PN)
PU = np.array([0.0, 1.0, 0.0]); PU = PU - PN * (PU @ PN); PU /= np.linalg.norm(PU)
PV = np.cross(PN, PU)
PRAD, PTH = 4.3, 0.10

MONO_REP = 14.0
def _box(px, py, pz, bx, by, bz):
    qx, qy, qz = np.abs(px) - bx, np.abs(py) - by, np.abs(pz) - bz
    ax, ay, az = np.maximum(qx, 0), np.maximum(qy, 0), np.maximum(qz, 0)
    return np.sqrt(ax*ax + ay*ay + az*az) + np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0)

def scene(p):
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    d_ground = y - ground_h(x, z)

    zc = np.round(z / MONO_REP)
    qz = z - zc * MONO_REP
    h = 5.5 + 3.0 * hash2(zc, 1.0)
    lean = 0.35 * (hash2(zc, 7.0) - 0.5)
    dl = _box(x + 9.0 + lean * y, y - h, qz, 0.55, h, 1.1)
    keepr = hash2(zc, 13.0) > 0.45
    hr = 7.0 + 4.0 * hash2(zc, 3.0)
    dr = _box(x - 16.0 - lean * y, y - hr, qz - 4.0, 0.7, hr, 1.4)
    dr = np.where(keepr, dr, 1e5)
    d_mono = np.minimum(dl, dr)

    # portal: rounded disc in its own frame
    rel = p - P0
    pn = rel @ PN
    pu = rel @ PU
    pv = rel @ PV
    prad = np.sqrt(pu*pu + pv*pv)
    d_portal = np.sqrt(np.maximum(prad - PRAD, 0)**2 + np.maximum(np.abs(pn) - PTH, 0)**2) - 0.05

    d = np.minimum(np.minimum(d_ground, d_mono), d_portal)
    mat = np.where(d_portal <= d, 2.0, np.where(d_mono < d_ground, 1.0, 0.0))
    return d, mat

def normal(p):
    e = 0.02
    d0, _ = scene(p)
    n = np.stack([scene(p + np.array([e,0,0]))[0] - d0,
                  scene(p + np.array([0,e,0]))[0] - d0,
                  scene(p + np.array([0,0,e]))[0] - d0], axis=-1)
    return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9)

cam = np.array([-1.5, 2.8, -6.0])
look = np.array([2.0, 3.8, 26.0])
fwd = look - cam; fwd /= np.linalg.norm(fwd)
right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right)
up = np.cross(right, fwd)

u = (np.arange(W) + 0.5) / W * 2 - 1
v = 1 - (np.arange(H) + 0.5) / H * 2
uu, vv = np.meshgrid(u, v)
aspect = W / H
rd = (fwd[None,None,:] + uu[...,None] * right * aspect * 0.62 + vv[...,None] * up * 0.62)
rd = rd / np.linalg.norm(rd, axis=-1, keepdims=True)

moon_dir = np.array([-0.6, 0.45, 0.35]); moon_dir /= np.linalg.norm(moon_dir)

MAXD = 220.0
t = np.zeros((H, W)); hit = np.zeros((H, W), dtype=bool); alive = np.ones((H, W), dtype=bool)
for i in range(140):
    if not alive.any(): break
    p = cam[None,None,:] + rd * t[...,None]
    d, _ = scene(p)
    d = np.where(alive, d, 1e5)
    newly = alive & (d < 0.004 * (1 + t * 0.15))
    hit |= newly; alive &= ~newly
    t = np.where(alive, np.minimum(t + d * 0.9, MAXD), t)
    alive &= t < MAXD

p_hit = cam[None,None,:] + rd * t[...,None]
_, mat = scene(p_hit)
n = normal(p_hit)

def soft_shadow(p, ldir):
    res = np.ones(p.shape[:-1]); ts = np.full(p.shape[:-1], 0.15)
    for _ in range(20):
        q = p + ldir[None,None,:] * ts[...,None]
        d, _ = scene(q)
        res = np.minimum(res, np.clip(8.0 * d / np.maximum(ts, 1e-3), 0, 1))
        ts = ts + np.clip(d, 0.08, 2.2)
    return np.clip(res, 0, 1)

# portal as a POINT light on the world
to_p = P0[None,None,:] - p_hit
dist_p = np.linalg.norm(to_p, axis=-1)
ldir_p = to_p / (dist_p[...,None] + 1e-9)
ndl_p = np.clip((n * ldir_p).sum(-1), 0, 1)
atten = 130.0 / (4.0 + dist_p**2)
sh = soft_shadow(p_hit, moon_dir)
ndl_m = np.clip((n * moon_dir).sum(-1), 0, 1) * sh
fresnel = np.clip(1 + (rd * n).sum(-1), 0, 1) ** 3

alb_ground = np.array([0.075, 0.085, 0.105])
alb_mono   = np.array([0.050, 0.058, 0.075])
albedo = np.where(mat[...,None] > 0.5, alb_mono, alb_ground)
col = (albedo * (0.08
                 + 1.15 * ndl_m[...,None] * MOON
                 + 3.4 * (ndl_p * atten)[...,None] * GREEN_MID)
       + 0.12 * fresnel[...,None] * CYAN * np.where(mat[...,None] > 0.5, 1.0, 0.25))

# monolith cyan seams (kept from the house style)
x, y, z = p_hit[...,0], p_hit[...,1], p_hit[...,2]
zc = np.round(z / MONO_REP); qz = z - zc * MONO_REP
seam = (mat > 0.5) & (mat < 1.5) & (np.abs(qz) < 0.10) & (y < 6.0)
glow = np.exp(-np.abs(qz) * 30.0) * np.exp(-0.10 * y) * 1.8
col = np.where(seam[...,None], col + CYAN[None,None,:] * glow[...,None], col)

# ── animated portal: world rendered once above; only the portal re-shades ──
GIF_OUT = "portal_dimension.gif"
FRAMES, FPS = 36, 14
OUT_W = 1280

rel = p_hit - P0
pu_h = rel @ PU; pv_h = rel @ PV
prad = np.sqrt(pu_h**2 + pv_h**2) / PRAD
pang = np.arctan2(pv_h, pu_h)
is_portal = mat > 1.5

# static world with fog (portal pixels get overwritten per frame)
elev = np.clip(rd[...,1], -0.2, 1)
sky = SKY_B[None,None,:] + (SKY_T - SKY_B)[None,None,:] * np.clip(elev*2.4, 0, 1)[...,None]
sq = np.floor(rd[...,:2] / np.maximum(np.abs(rd[...,2:3]), .2) * 400)
sv = np.sin(sq[...,0]*127.1 + sq[...,1]*311.7)*43758.5453; sv -= np.floor(sv)
stars = ((sv > 0.9975) & (rd[...,1] > 0.02)).astype(float) * (sv - 0.9975) * 380
sky += stars[...,None] * np.array([0.85, 0.95, 1.0])
world = np.where(hit[...,None], col, sky)
fog_f = np.where(hit & ~is_portal, 1 - np.exp(-t * 0.014), 0)[...,None]
world = world * (1 - fog_f) + FOG[None,None,:] * fog_f * 1.4
world = np.where(~hit[...,None] & (np.abs(rd[...,1:2]) < 0.06),
                 world + FOG[None,None,:]*np.exp(-np.abs(rd[...,1:2])*40)*0.8, world)
seam_emis = np.where(seam[...,None], CYAN[None,None,:] * glow[...,None] * 0.6, 0)

def portal_shader(phase):
    wob = (0.045 * np.sin(pang * 3 + prad * 2.0 + 0.6*np.sin(phase))
           + 0.025 * np.sin(pang * 7 - 2.0 - phase))
    rr = np.clip(prad + wob, 0, 1.3)
    rings = 0.5 + 0.5 * np.sin(rr * 26.0 - 2.2 - phase * 2.0)
    shade = np.clip(rings, 0, 1) ** 1.6
    base = GREEN_DARK[None,None,:] + (GREEN_MID - GREEN_DARK)[None,None,:] * shade[...,None]
    pulse = 1.0 + 0.10 * np.sin(phase)
    core = np.clip(1 - rr * 1.05, 0, 1) ** 1.3
    rim = np.exp(-((prad - 0.97) / 0.05) ** 2)
    return (base * (0.55 + 1.1 * core * pulse)[...,None]
            + GREEN_CORE[None,None,:] * (core ** 2 * 1.1 * pulse)[...,None]
            + GREEN_CORE[None,None,:] * (rim * (2.0 + 0.6*np.sin(phase*2)))[...,None])

frames = []
for f in range(FRAMES):
    phase = 2 * np.pi * f / FRAMES
    pem = portal_shader(phase)
    img = np.where(is_portal[...,None], pem, world)
    emis = np.where(is_portal[...,None], pem * 0.7, 0) + seam_emis
    e_src = Image.fromarray((np.clip(emis/(1+emis),0,1)*255).astype(np.uint8))
    img = img + np.asarray(e_src.filter(ImageFilter.GaussianBlur(14)), dtype=float)/255.0 * 0.85
    img = img + np.asarray(e_src.filter(ImageFilter.GaussianBlur(38)), dtype=float)/255.0 * 0.45
    lum = img @ np.array([0.2126, 0.7152, 0.0722])
    scale = (lum / (1 + lum)) / np.maximum(lum, 1e-6)
    img = np.clip(img * scale[..., None], 0, 1) ** (1/2.2)
    vx = (uu**2 + vv**2) * 0.16
    img *= (1 - vx)[...,None]
    fr = Image.fromarray((img*255).astype(np.uint8)).resize(
        (OUT_W, int(OUT_W*H/W)), Image.LANCZOS)
    frames.append(fr.convert("P", palette=Image.ADAPTIVE, colors=256, dither=Image.FLOYDSTEINBERG))
    print(f"frame {f+1}/{FRAMES}", flush=True)

frames[0].save(GIF_OUT, save_all=True, append_images=frames[1:],
               duration=int(1000/FPS), loop=0, optimize=True)
import os
print("saved", GIF_OUT, f"{os.path.getsize(GIF_OUT)/1e6:.1f} MB")
