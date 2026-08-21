"""Blender Cycles scene: the portal in the monolith dune field.
Run: blender --background --python portal_cycles.py -- <out.png> <W> <H> <samples> [frame_phase]
"""
import bpy, sys, math, random

argv = sys.argv[sys.argv.index("--")+1:]
OUT, W, H, SAMPLES = argv[0], int(argv[1]), int(argv[2]), int(argv[3])
ANIM = len(argv) > 4 and argv[4] == "ANIM"
PHASE = float(argv[4]) if (len(argv) > 4 and not ANIM) else 0.0

random.seed(2077)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.sample_clamp_indirect = 8.0
sc.render.resolution_x, sc.render.resolution_y = W, H
sc.render.film_transparent = False
sc.render.filepath = OUT
sc.view_settings.view_transform = 'Filmic'
sc.view_settings.look = 'Medium High Contrast'

# GPU via Metal if available
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'METAL'
    prefs.get_devices()
    for d in prefs.devices: d.use = True
    sc.cycles.device = 'GPU'
except Exception as e:
    print("GPU setup failed, CPU fallback:", e)

def mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links

# ── world: near-black gradient + sparse stars ───────────────────────────────
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
wn, wl = w.node_tree.nodes, w.node_tree.links
bg = wn["Background"]
tex = wn.new("ShaderNodeTexCoord")
sep = wn.new("ShaderNodeSeparateXYZ"); wl.new(tex.outputs["Generated"], sep.inputs[0])
ramp = wn.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].color = (0.012, 0.018, 0.035, 1)
ramp.color_ramp.elements[1].color = (0.001, 0.002, 0.006, 1)
wl.new(sep.outputs["Z"], ramp.inputs[0])
vor = wn.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 260.0
wl.new(tex.outputs["Generated"], vor.inputs[0])
m1 = wn.new("ShaderNodeMath"); m1.operation = 'GREATER_THAN'; m1.inputs[1].default_value = 0.985
wl.new(vor.outputs["Distance"], m1.inputs[0])
starb = wn.new("ShaderNodeMath"); starb.operation = 'MULTIPLY'; starb.inputs[1].default_value = 2.2
wl.new(m1.outputs[0], starb.inputs[0])
addc = wn.new("ShaderNodeMixRGB"); addc.blend_type = 'ADD'; addc.inputs["Fac"].default_value = 1.0
wl.new(ramp.outputs["Color"], addc.inputs["Color1"])
wl.new(starb.outputs[0], addc.inputs["Color2"])
wl.new(addc.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0

# ── dunes ───────────────────────────────────────────────────────────────────
bpy.ops.mesh.primitive_grid_add(x_subdivisions=220, y_subdivisions=220, size=260, location=(0, 90, 0))
ground = bpy.context.object
disp_tex = bpy.data.textures.new("dunes", type='CLOUDS'); disp_tex.noise_scale = 34.0
dmod = ground.modifiers.new("disp", 'DISPLACE'); dmod.texture = disp_tex; dmod.strength = 4.2
bpy.ops.object.shade_smooth()
gm, gn, gl_ = mat("ground")
p = gn["Principled BSDF"]
p.inputs["Base Color"].default_value = (0.045, 0.055, 0.075, 1)
p.inputs["Roughness"].default_value = 0.55
ground.data.materials.append(gm)

# ── monoliths + cyan seams ──────────────────────────────────────────────────
mm, mn, ml_ = mat("mono")
pm = mn["Principled BSDF"]
pm.inputs["Base Color"].default_value = (0.030, 0.038, 0.050, 1)
pm.inputs["Roughness"].default_value = 0.35
sm, sn_, sl_ = mat("seam")
sn_.remove(sn_["Principled BSDF"])
em = sn_.new("ShaderNodeEmission")
em.inputs["Color"].default_value = (0.34, 0.84, 0.88, 1)
em.inputs["Strength"].default_value = 6.0
sl_.new(em.outputs[0], sn_["Material Output"].inputs["Surface"])

def monolith(x, y, h, lean):
    bpy.ops.mesh.primitive_cube_add(location=(x, y, h/2 - 0.4))
    ob = bpy.context.object
    ob.scale = (0.62, 1.15, h/2)
    ob.rotation_euler[1] = lean
    ob.data.materials.append(mm)
    bpy.ops.mesh.primitive_cube_add(location=(x - 0.66*math.cos(lean), y, h*0.42))
    s = bpy.context.object
    s.scale = (0.03, 0.09, h*0.36)
    s.rotation_euler[1] = lean
    s.data.materials.append(sm)

for i in range(7):
    yy = 6 + i * 13
    monolith(-8.5 + random.uniform(-0.6, 0.6), yy, 9.5 + random.uniform(0, 5), random.uniform(-0.05, 0.05))
    if random.random() > 0.4:
        monolith(14.0 + random.uniform(-0.8, 0.8), yy + 5, 12 + random.uniform(0, 6), random.uniform(-0.05, 0.05))

# ── the portal ──────────────────────────────────────────────────────────────
PLOC = (2.6, 26.0, 5.1)
# swirl disc
bpy.ops.mesh.primitive_circle_add(vertices=128, radius=3.9, fill_type='NGON',
                                  location=PLOC, rotation=(math.radians(90), 0, math.radians(-10)))
disc = bpy.context.object
dm, dn, dl = mat("portal")
dn.remove(dn["Principled BSDF"])
out = dn["Material Output"]
tc = dn.new("ShaderNodeTexCoord")
mapn = dn.new("ShaderNodeMapping"); mapn.inputs["Rotation"].default_value[2] = PHASE
dl.new(tc.outputs["Object"], mapn.inputs["Vector"])
noise = dn.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value = 1.8
noise.inputs["Distortion"].default_value = 1.2
dl.new(mapn.outputs[0], noise.inputs["Vector"])
mix = dn.new("ShaderNodeMixRGB"); mix.inputs["Fac"].default_value = 0.42
dl.new(mapn.outputs[0], mix.inputs["Color1"]); dl.new(noise.outputs["Color"], mix.inputs["Color2"])
wave = dn.new("ShaderNodeTexWave"); wave.wave_type = 'RINGS'; wave.rings_direction = 'SPHERICAL'
wave.inputs["Scale"].default_value = 0.85
dl.new(mix.outputs["Color"], wave.inputs["Vector"])
cr = dn.new("ShaderNodeValToRGB")
cr.color_ramp.elements[0].position = 0.15; cr.color_ramp.elements[0].color = (0.012, 0.10, 0.012, 1)
cr.color_ramp.elements[1].position = 0.75; cr.color_ramp.elements[1].color = (0.25, 1.0, 0.10, 1)
dl.new(wave.outputs["Color"], cr.inputs[0])
grad = dn.new("ShaderNodeTexGradient"); grad.gradient_type = 'SPHERICAL'
gm2 = dn.new("ShaderNodeMapping"); gm2.inputs["Scale"].default_value = (0.256, 0.256, 0.256)
dl.new(tc.outputs["Object"], gm2.inputs["Vector"]); dl.new(gm2.outputs[0], grad.inputs["Vector"])
corem = dn.new("ShaderNodeMixRGB"); corem.blend_type = 'ADD'
dl.new(grad.outputs["Color"], corem.inputs["Fac"])
dl.new(cr.outputs["Color"], corem.inputs["Color1"])
corem.inputs["Color2"].default_value = (0.30, 0.65, 0.12, 1)
pem = dn.new("ShaderNodeEmission"); pem.inputs["Strength"].default_value = 5.5
dl.new(corem.outputs["Color"], pem.inputs["Color"])
dl.new(pem.outputs[0], out.inputs["Surface"])

# rim torus
bpy.ops.mesh.primitive_torus_add(major_radius=4.05, minor_radius=0.09,
                                 location=PLOC, rotation=(math.radians(90), 0, math.radians(-10)))
rim = bpy.context.object
rm2, rn2, rl2 = mat("rim")
rn2.remove(rn2["Principled BSDF"])
rem = rn2.new("ShaderNodeEmission")
rem.inputs["Color"].default_value = (0.45, 1.0, 0.15, 1)
rem.inputs["Strength"].default_value = 3.0
rl2.new(rem.outputs[0], rn2["Material Output"].inputs["Surface"])


dm_ = dm; disc.data.materials.append(dm_)
rim.data.materials.append(rm2)

# faint cool moon key so the dark side isn't void
sun = bpy.data.lights.new("moon", 'SUN'); sun.energy = 0.35
sun.color = (0.45, 0.55, 0.85)
so = bpy.data.objects.new("moon", sun); sc.collection.objects.link(so)
so.rotation_euler = (math.radians(55), 0, math.radians(140))

# camera
cam = bpy.data.cameras.new("cam"); cam.lens = 32
co = bpy.data.objects.new("cam", cam); sc.collection.objects.link(co)
co.location = (-1.8, -20.0, 3.5)
co.rotation_euler = (math.radians(87), 0, math.radians(-4))
sc.camera = co

import math as _m
if ANIM:
    base = OUT
    FRAMES = 36
    for f in range(FRAMES):
        phase = 2 * _m.pi * f / FRAMES
        mapn.inputs["Rotation"].default_value[2] = phase
        pem.inputs["Strength"].default_value = 5.5 * (1.0 + 0.08 * _m.sin(phase))
        rem.inputs["Strength"].default_value = 3.0 * (1.0 + 0.15 * _m.sin(phase * 2))
        sc.render.filepath = f"{base}{f:03d}.png"
        bpy.ops.render.render(write_still=True)
        print("frame", f + 1, "/", FRAMES, flush=True)
else:
    bpy.ops.render.render(write_still=True)
print("rendered", OUT)
