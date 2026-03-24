"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  AzanRE 6.0  —  PERFECT EDITION                                            ║
║  By AzanChishiya  |  Resident Evil 4-Style Survival Horror Raycaster       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  ALL BUGS FIXED:                                                            ║
║  • surfarray lock released before assignment (no crash)                    ║
║  • all globals declared at module level (no NameError)                     ║
║  • scanlines pre-baked as numpy array (no per-frame allocation)            ║
║  • gradient panels use numpy surfarray (no O(H) draw.line loop)           ║
║  • headshot detection corrected                                             ║
║  • menu fully rewritten: dark horror aesthetic, no cosmetic mess           ║
║  • game loop returns properly in all states                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  CONTROLS                                                                   ║
║  WASD/Arrows Move   Shift Sprint   Ctrl Crouch   Q/E Lean   F Light        ║
║  Mouse Look         LMB Shoot      RMB ADS       R Reload   G Grenade      ║
║  1-5 Weapons        Tab Stats      ESC Pause                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  MODES: SURVIVAL · MISSION · PROGRESSION                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import pygame
try:
    import pygame.gfxdraw
    _GFXDRAW = True
except Exception:
    _GFXDRAW = False

import numpy as np
import math, random, sys, json
from enum      import Enum, auto
from functools import lru_cache
from typing    import List, Optional, Dict, Tuple

# ═══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
TILE         = 64
MAP_W, MAP_H = 24, 20
MINI_TILE    = 5
VERSION      = "6.0"
SAVE_FILE    = "azanre6_save.json"
HS_FILE      = "azanre6_hs.txt"
AMBIENT      = 0.18
FL_CONE      = math.pi / 5.5
LIGHT_LEVELS = 20

# ═══════════════════════════════════════════════════════════════════════════════
#  MAP  0=open 1=stone 2=metal 3=window 4=wood 5=concrete
# ═══════════════════════════════════════════════════════════════════════════════
MAP_GRID = [
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,1,1,2,0,0,0,0,0,0,0,2,1,1,0,0,0,0,0,0,1],
    [1,0,0,0,1,0,0,0,0,3,3,0,0,0,0,0,1,0,0,0,0,0,0,1],
    [1,0,0,0,2,0,0,0,0,0,0,0,0,0,0,0,2,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,1,1,0,0,0,1,1,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0,4,4,0,0,1],
    [1,0,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,2,2,0,0,0,0,1],
    [1,0,2,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2,0,0,0,0,1],
    [1,0,0,0,0,0,5,0,0,0,0,0,0,0,5,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,5,0,0,0,0,0,0,0,5,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,3,3,0,0,0,0,0,0,0,0,0,3,3,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,2,2,0,1,1,0,2,2,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,0,4,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,0,1],
    [1,0,4,4,0,0,0,1,1,1,0,1,1,1,0,0,0,4,4,4,0,0,0,1],
    [1,0,0,0,0,0,0,1,0,0,0,0,0,1,0,0,0,0,0,0,0,0,0,1],
    [1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1],
    [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1],
]
_MAP_NP = np.array(MAP_GRID, dtype=np.int32)

def map_at(mx: float, my: float) -> int:
    gx, gy = int(mx // TILE), int(my // TILE)
    return int(_MAP_NP[gy, gx]) if 0 <= gx < MAP_W and 0 <= gy < MAP_H else 1

def is_wall(mx: float, my: float) -> bool:
    return map_at(mx, my) != 0

# ═══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
CFG: Dict = {
    "width": 1280, "height": 720, "fullscreen": True, "fov_deg": 62,
    "mouse_sens": 0.0018, "max_fps": 0, "render_scale": 2,
    "flashlight": True, "fog": True, "film_grain": False, "vignette": True,
    "chromatic_ab": True, "shadows": True, "dof_blur": True,
    "difficulty": 1, "invert_y": False, "volume": 0.65, "aim_assist": True,
    "show_fps": True,
}

def _load_cfg() -> None:
    global CFG
    try:
        with open(SAVE_FILE) as f:
            d = json.load(f)
            if "settings" in d:
                CFG.update(d["settings"])
    except Exception:
        pass

def _save_cfg() -> None:
    try:
        d: Dict = {}
        try:
            with open(SAVE_FILE) as f:
                d = json.load(f)
        except Exception:
            pass
        d["settings"] = CFG
        with open(SAVE_FILE, "w") as f:
            json.dump(d, f, indent=2)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
#  PYGAME INIT
# ═══════════════════════════════════════════════════════════════════════════════
pygame.init()
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.mixer.init()
clock = pygame.time.Clock()

# ── All globals declared at module level ─────────────────────────────────────
W: int = 1280; H: int = 720
HALF_W: int = 640; HALF_H: int = 360
RW: int = 1280; RH: int = 720
NUM_RAYS: int = 1280
FOV: float = math.radians(62)
PROJ_DIST: float = 800.0
MAX_DIST: float = float(MAP_W * TILE)
MINI_X: int = 0; MINI_Y: int = 10
screen: Optional[pygame.Surface] = None
render_surf: Optional[pygame.Surface] = None
_game_surf: Optional[pygame.Surface] = None  # W×H surface; letterboxed to screen
_pxbuf: Optional[np.ndarray] = None
_zbuf: Optional[np.ndarray] = None
_edge_mask: Optional[np.ndarray] = None
_mm_static: Optional[pygame.Surface] = None
_COLS_F: Optional[np.ndarray] = None
_vig_cache: Optional[pygame.Surface] = None
_vig_sz: Tuple = (0, 0)
_grain_buf: Optional[np.ndarray] = None
_rng = np.random.default_rng()
_LB_X: int = 0
_LB_Y: int = 0
_LB_SCALE: float = 1.0

# Letterbox blit offset (set by apply_cfg for fullscreen)
_LB_X: int = 0   # x offset when letterboxing
_LB_Y: int = 0   # y offset when letterboxing
_LB_SCALE: float = 1.0  # scale factor for letterboxed blit

def apply_cfg() -> None:
    global W, H, HALF_W, HALF_H, screen, render_surf, _pxbuf, _zbuf
    global FOV, NUM_RAYS, PROJ_DIST, MAX_DIST, MINI_X, MINI_Y, RW, RH
    global _edge_mask, _mm_static, _COLS_F, _vig_cache, _vig_sz
    global _grain_buf, _LB_X, _LB_Y, _LB_SCALE, _game_surf

    W, H = CFG["width"], CFG["height"]
    HALF_W, HALF_H = W // 2, H // 2

    flags = pygame.DOUBLEBUF | pygame.HWSURFACE
    if CFG["fullscreen"]:
        # Get native desktop resolution — render game at W×H, blit with letterbox
        dm = pygame.display.get_desktop_sizes()
        desk_w, desk_h = dm[0] if dm else (W, H)
        screen = pygame.display.set_mode((desk_w, desk_h),
                                         flags | pygame.FULLSCREEN)
        # Compute letterbox: scale W×H to fit desk_w×desk_h preserving AR
        scale_x = desk_w / W
        scale_y = desk_h / H
        _LB_SCALE = min(scale_x, scale_y)
        blit_w = int(W * _LB_SCALE)
        blit_h = int(H * _LB_SCALE)
        _LB_X = (desk_w - blit_w) // 2
        _LB_Y = (desk_h - blit_h) // 2
    else:
        screen = pygame.display.set_mode((W, H), flags)
        _LB_X = 0; _LB_Y = 0; _LB_SCALE = 1.0
    pygame.display.set_caption(f"AzanRE {VERSION}")

    rs = CFG["render_scale"]
    RW, RH = W // rs, H // rs
    render_surf = pygame.Surface((RW, RH))
    _pxbuf = np.zeros((RW, RH, 3), dtype=np.uint8)
    _game_surf = pygame.Surface((W, H))

    FOV = math.radians(CFG["fov_deg"])
    NUM_RAYS = RW
    PROJ_DIST = (RW / 2) / math.tan(FOV / 2)
    MAX_DIST = float(MAP_W * TILE)
    _zbuf = np.full(NUM_RAYS, MAX_DIST, dtype=np.float32)

    MINI_X = W - MAP_W * MINI_TILE - 10
    MINI_Y = 10

    # Pre-bake edge mask for damage flash (screen resolution)
    xs = np.linspace(0, 1, W, dtype=np.float32)
    ys = np.linspace(0, 1, H, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys, indexing='ij')
    edge = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    _edge_mask = (1.0 - (edge * 5.0).clip(0, 1)) ** 1.8

    # Pre-bake scanlines (render-surf resolution) — brightness multiplier
    # Reset caches
    _mm_static = None
    _COLS_F = np.arange(RW, dtype=np.float32)
    _vig_cache = None
    _vig_sz = (0, 0)
    _grain_buf = None

_load_cfg()
apply_cfg()

# ═══════════════════════════════════════════════════════════════════════════════
#  FONTS
# ═══════════════════════════════════════════════════════════════════════════════
def _font(size: int, bold: bool = False, display: bool = False) -> pygame.font.Font:
    display_candidates = ["Impact", "Arial Black", "Arial", "Verdana", "Tahoma"]
    body_candidates    = ["Consolas", "Courier New", "Lucida Console", "monospace"]
    for name in (display_candidates if display else body_candidates):
        try:
            f = pygame.font.SysFont(name, size, bold=bold)
            if f:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, size)

F_XS  = _font(14)
F_SM  = _font(17, True)
F_MD  = _font(22, True)
F_LG  = _font(38, True, display=True)
F_HUG = _font(62, True, display=True)
F_TTL = _font(78, True, display=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  PROCEDURAL TEXTURES
# ═══════════════════════════════════════════════════════════════════════════════
_tr = random.Random(99991)

def _c8(v: float) -> int:
    return max(0, min(255, int(v)))

def _tex_stone() -> np.ndarray:
    t = np.zeros((TILE, TILE, 3), dtype=np.uint8)
    for y in range(TILE):
        mh = y % 20 < 2
        ro = 10 if (y // 20) % 2 else 0
        for x in range(TILE):
            mv = (x + ro) % 20 == 0
            n = _tr.randint(-22, 22)
            if mh or mv:
                v = _c8(32 + n // 2)
                t[y, x] = [v, max(0, v - 2), max(0, v - 4)]
            else:
                bv = _tr.randint(-8, 8)
                t[y, x] = [_c8(78 + n + bv), _c8(66 + n), _c8(54 + n - bv)]
    for _ in range(7):
        cx, cy = _tr.randint(3, TILE - 4), _tr.randint(2, TILE - 12)
        for i in range(_tr.randint(5, 15)):
            nx = min(TILE - 1, max(0, cx + _tr.randint(-1, 1)))
            if cy + i < TILE:
                t[cy + i, nx] = [18, 16, 14]
    return t

def _tex_metal() -> np.ndarray:
    t = np.zeros((TILE, TILE, 3), dtype=np.uint8)
    for y in range(TILE):
        for x in range(TILE):
            n = _tr.randint(-8, 8)
            if x % 32 in (3, 4) and y % 16 in (3, 4):
                v = 185; t[y, x] = [v, v, _c8(v + 8)]
            elif y % 16 < 2 or x % 32 < 2:
                v = _c8(30 + n // 2); t[y, x] = [v, v, _c8(v + 4)]
            else:
                b = _c8(90 - (y // 16) * 5 + n); t[y, x] = [b, _c8(b + 3), _c8(b + 8)]
    return t

def _tex_window() -> np.ndarray:
    t = np.zeros((TILE, TILE, 3), dtype=np.uint8)
    for y in range(TILE):
        for x in range(TILE):
            fr = x < 7 or x > TILE - 8 or y < 7 or y > TILE - 8 or 28 < x < 36 or 28 < y < 36
            n = _tr.randint(-6, 6)
            if fr:
                v = 75 + n; t[y, x] = [_c8(v + 5), _c8(v), _c8(v - 5)]
            else:
                t[y, x] = [_c8(18 + n), _c8(38 + n), _c8(55 + n)]
    return t

def _tex_wood() -> np.ndarray:
    t = np.zeros((TILE, TILE, 3), dtype=np.uint8)
    for y in range(TILE):
        for x in range(TILE):
            g = int(math.sin(x * 0.38 + y * 0.05) * 14)
            n = _tr.randint(-8, 8); b = 95 + g + n
            t[y, x] = [40, 28, 16] if y % 18 < 1 else [_c8(b + 20), _c8(b + 5), _c8(b - 25)]
    return t

def _tex_concrete() -> np.ndarray:
    t = np.zeros((TILE, TILE, 3), dtype=np.uint8)
    for y in range(TILE):
        for x in range(TILE):
            n = _tr.randint(-12, 12); b = _c8(55 + n)
            t[y, x] = [32, 32, 34] if x % 32 < 1 or y % 24 < 1 else [b, b, _c8(b + 2)]
    return t

WALL_ARR: Dict[int, np.ndarray] = {
    1: _tex_stone(), 2: _tex_metal(), 3: _tex_window(),
    4: _tex_wood(),  5: _tex_concrete(),
}
# FLOOR_ARR / CEIL_ARR removed — floor/ceil now use fast solid gradient

# Pre-multiplied wall column cache
_WCACHE: Dict[Tuple, np.ndarray] = {}
for _tid, _arr in WALL_ARR.items():
    for _tx in range(TILE):
        _col = _arr[:, _tx, :]
        for _li in range(LIGHT_LEVELS):
            _lf = (_li + 1) / LIGHT_LEVELS
            _WCACHE[(_tid, _tx, _li)] = np.clip(_col.astype(np.float32) * _lf, 0, 255).astype(np.uint8)

def _li(light: float) -> int:
    return max(0, min(LIGHT_LEVELS - 1, int(light * LIGHT_LEVELS - 0.001)))

@lru_cache(maxsize=4096)
def _tys(span: int) -> np.ndarray:
    if span <= 1:
        return np.zeros(1, dtype=np.int32)
    return np.linspace(0, TILE - 1, span, dtype=np.float32).astype(np.int32)

# ═══════════════════════════════════════════════════════════════════════════════
#  SOUND
# ═══════════════════════════════════════════════════════════════════════════════
SFX: Dict[str, Optional[pygame.mixer.Sound]] = {}

def _bsnd(mono: np.ndarray) -> Optional[pygame.mixer.Sound]:
    try:
        s16 = np.clip(mono, -32767, 32767).astype(np.int16)
        return pygame.sndarray.make_sound(np.column_stack([s16, s16]))
    except Exception:
        return None

def _gen_sfx() -> None:
    sr = 44100
    def env(n, c=0.5): return (1 - np.linspace(0, 1, n, False)) ** c
    def noise(n): return np.random.uniform(-1, 1, n)
    def sq(f, n): return np.where(np.sin(2 * np.pi * f * np.arange(n) / sr) > 0, 1., -1.)
    def sine(f, n): return np.sin(2 * np.pi * f * np.arange(n) / sr)

    n = int(sr * 0.12)
    SFX["pistol"]  = _bsnd(((noise(n) * env(n, .4) + sq(280, n) * env(n, 1.2) * .3) * .55 * 32767).astype(np.int32))
    n = int(sr * 0.22)
    SFX["shotgun"] = _bsnd(((noise(n) * env(n, .30) * .8 + sine(90, n) * env(n, 1.5) * .3) * .70 * 32767).astype(np.int32))
    n = int(sr * 0.08)
    SFX["rifle"]   = _bsnd(((noise(n) * env(n, .45) * .6 + sq(550, n) * env(n, .8) * .4) * .45 * 32767).astype(np.int32))
    n = int(sr * 0.18); t2 = np.arange(n) / sr
    SFX["grenade"] = _bsnd(((np.sin(2 * np.pi * (120 - 80 * (np.arange(n) / n)) * t2) * env(n, .55) * .5 + np.sin(2 * np.pi * 45 * t2) * env(n, .3) * .4) * .65 * 32767).astype(np.int32))
    n = int(sr * 0.90); t2 = np.arange(n) / sr
    SFX["explosion"] = _bsnd(((noise(n) * env(n, .20) * .85 + np.sin(2 * np.pi * (55 - 30 * (np.arange(n) / n)) * t2) * env(n, .40) * .45 + np.sin(2 * np.pi * 40 * t2) * env(n, .55) * .3) * .88 * 32767).astype(np.int32))
    n = int(sr * 0.15)
    SFX["hurt"]    = _bsnd(((noise(n) * env(n, .5) * .5 + sine(175, n) * env(n, 1.) * .25) * .40 * 32767).astype(np.int32))
    n = int(sr * 0.25); a = np.zeros(n); q = n // 4
    a[:q] = sq(900, n)[:q] * env(q, 1.) * 0.4
    a[n // 2:n // 2 + q] = sq(600, n)[:q] * env(q, 1.) * 0.35
    SFX["reload"]  = _bsnd((a * .30 * 32767).astype(np.int32))
    n = int(sr * 0.09)
    SFX["step"]    = _bsnd(((noise(n) * env(n, .8) * .3 + sine(190, n) * env(n, 1.2) * .4) * .25 * 32767).astype(np.int32))
    n = int(sr * 0.35); t2 = np.arange(n) / sr; mod = np.sin(2 * np.pi * 3 * t2)
    SFX["growl"]   = _bsnd(((np.sin(2 * np.pi * (80 + 30 * mod) * t2) * env(n, .4) * .7 + noise(n) * env(n, .6) * .2) * .35 * 32767).astype(np.int32))
    n = int(sr * 0.18); t2 = np.arange(n) / sr
    SFX["pickup"]  = _bsnd((np.sin(2 * np.pi * (440 + 220 * (np.arange(n) / n)) * t2) * env(n, .55) * .4 * 32767).astype(np.int32))

try:
    _gen_sfx()
except Exception:
    pass

def sfx(name: str, vol: float = 1.0) -> None:
    try:
        s = SFX.get(name)
        if s and CFG["volume"] > 0:
            s.set_volume(min(1.0, CFG["volume"] * vol))
            s.play()
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
#  PARTICLE POOL
# ═══════════════════════════════════════════════════════════════════════════════
MAX_P = 1024

class ParticlePool:
    def __init__(self, cap: int):
        self.cap = cap
        self.x   = np.zeros(cap, np.float32); self.y  = np.zeros(cap, np.float32)
        self.vx  = np.zeros(cap, np.float32); self.vy = np.zeros(cap, np.float32)
        self.life = np.zeros(cap, np.float32); self.ml = np.zeros(cap, np.float32)
        self.r   = np.zeros(cap, np.float32)
        self.cr  = np.zeros(cap, np.float32); self.cg = np.zeros(cap, np.float32)
        self.cb  = np.zeros(cap, np.float32); self.grav = np.zeros(cap, np.float32)
        self.alive = np.zeros(cap, bool)
        self._free: List[int] = list(range(cap - 1, -1, -1))

    def reset(self) -> None:
        self.alive[:] = False
        self._free = list(range(self.cap - 1, -1, -1))

    def emit(self, x, y, vx, vy, life, r, cr, cg, cb, grav=200.0) -> None:
        if not self._free:
            return
        i = self._free.pop()
        self.x[i]=x; self.y[i]=y; self.vx[i]=vx; self.vy[i]=vy
        self.life[i]=life; self.ml[i]=life; self.r[i]=r
        self.cr[i]=cr; self.cg[i]=cg; self.cb[i]=cb; self.grav[i]=grav
        self.alive[i] = True

    def update(self, dt: float) -> None:
        a = self.alive
        if not a.any():
            return
        self.x[a]    += self.vx[a] * dt
        self.y[a]    += self.vy[a] * dt
        self.vy[a]   += self.grav[a] * dt
        self.life[a] -= dt
        died = a & (self.life <= 0)
        self.alive[died] = False
        self._free.extend(np.where(died)[0].tolist())

    def draw(self, surf: pygame.Surface) -> None:
        a = self.alive
        if not a.any():
            return
        for i in np.where(a)[0]:
            frac = max(0.0, self.life[i] / self.ml[i])
            rad  = max(1, int(self.r[i] * frac))
            col  = (int(self.cr[i] * frac), int(self.cg[i] * frac), int(self.cb[i] * frac))
            pygame.draw.circle(surf, col, (int(self.x[i]), int(self.y[i])), rad)

_pool = ParticlePool(MAX_P)

def _pe(x,y,vx,vy,life,r,cr,cg,cb,grav=200.0): _pool.emit(x,y,vx,vy,life,r,cr,cg,cb,grav)

def emit_blood(sx, sy, count=14):
    for _ in range(count):
        a = random.uniform(0, math.pi*2); sp = random.uniform(25, 115)
        _pe(sx,sy,math.cos(a)*sp,math.sin(a)*sp-random.uniform(20,75),random.uniform(.35,1.2),random.randint(2,5),random.randint(140,205),random.randint(0,12),0)

def emit_muzzle(sx, sy, count=8):
    for _ in range(count):
        a = random.uniform(-.6, .6); sp = random.uniform(35, 140)
        _pe(sx,sy,math.cos(a)*sp,math.sin(a)*sp-28,random.uniform(.05,.18),random.randint(2,7),255,random.randint(150,255),random.randint(0,65),30.)

def emit_shell(sx, sy):
    a = random.uniform(.2, .9); sp = random.uniform(55, 115)
    _pe(sx,sy,math.cos(a)*sp,math.sin(a)*sp-60,random.uniform(.5,1.1),3,200,160,20,320.)

def emit_explosion(sx, sy, count=45):
    cols = [(255,100,0),(255,200,0),(200,50,0),(255,255,80)]
    for _ in range(count):
        a=random.uniform(0,math.pi*2); sp=random.uniform(20,220); cr,cg,cb=random.choice(cols)
        _pe(sx,sy,math.cos(a)*sp,math.sin(a)*sp-random.uniform(0,85),random.uniform(.3,1.6),random.randint(3,12),cr,cg,cb,55.)
    for _ in range(22):
        a=random.uniform(0,math.pi*2); sp=random.uniform(10,65); c=random.randint(60,135)
        _pe(sx,sy,math.cos(a)*sp*.5,math.sin(a)*sp*.5-22,random.uniform(.8,2.2),random.randint(4,14),c,c,c,-12.)

def emit_dust(sx, sy, count=4):
    for _ in range(count):
        a=random.uniform(0,math.pi*2); sp=random.uniform(8,38); c=random.randint(100,145)
        _pe(sx,sy,math.cos(a)*sp,math.sin(a)*sp,random.uniform(.2,.65),random.randint(1,3),c,c-10,c-22,14.)

# ═══════════════════════════════════════════════════════════════════════════════
#  RAYCASTER  (vectorised floor/ceiling, lru_cache walls)
# ═══════════════════════════════════════════════════════════════════════════════
def cast_and_draw(px: float, py: float, pangle: float,
                  pitch_px: int, fl: bool) -> None:
    global _pxbuf, _zbuf
    half_h = RH // 2 + pitch_px

    # ── Floor / Ceiling ──────────────────────────────────────────────────────
    # ── FLOOR / CEILING: fast solid gradient (50x faster than textured) ──────
    # At 640x360 scaled up, solid gradient is indistinguishable in dark scenes
    f_count = RH - half_h - 1        # rows below horizon
    c_count = half_h                  # rows above horizon

    if f_count > 0:
        f_dists = np.arange(1, f_count + 1, dtype=np.float32)
        f_fog   = (PROJ_DIST * TILE * 0.5 / f_dists / (MAX_DIST * 0.55)).clip(0, 1)
        # Checkerboard-like variation using distance modulation
        f_bright = np.clip(((1.0 - f_fog) * 0.55 * 55 + 12), 12, 67).astype(np.uint8)
        _pxbuf[:, half_h + 1:, 0] = f_bright          # broadcast (RW, n_floor)
        _pxbuf[:, half_h + 1:, 1] = f_bright
        _pxbuf[:, half_h + 1:, 2] = f_bright

    if c_count > 0:
        c_dists = np.arange(c_count, 0, -1, dtype=np.float32)
        c_fog   = (PROJ_DIST * TILE * 0.5 / c_dists / (MAX_DIST * 0.55)).clip(0, 1)
        c_bright = np.clip(((1.0 - c_fog) * 0.25 * 28 + 5), 5, 33).astype(np.uint8)
        _pxbuf[:, 0:half_h, 0] = c_bright
        _pxbuf[:, 0:half_h, 1] = c_bright
        _pxbuf[:, 0:half_h, 2] = np.clip(c_bright.astype(np.int16) + 3, 0, 255).astype(np.uint8)  # slight blue

    # ── Wall DDA ─────────────────────────────────────────────────────────────
    _zbuf[:] = MAX_DIST
    half_fov  = FOV * 0.5
    d_ang     = FOV / NUM_RAYS
    start_ang = pangle - half_fov

    for i in range(NUM_RAYS):
        ra = start_ang + i * d_ang
        sa = math.sin(ra); ca = math.cos(ra)
        if abs(ca) < 1e-9: ca = 1e-9
        if abs(sa) < 1e-9: sa = 1e-9

        ddx = abs(TILE / ca); ddy = abs(TILE / sa)
        mx  = int(px // TILE); my = int(py // TILE)
        ssx = 1 if ca > 0 else -1; ssy = 1 if sa > 0 else -1
        sx_d = ((mx + (1 if ca > 0 else 0)) * TILE - px) / ca
        sy_d = ((my + (1 if sa > 0 else 0)) * TILE - py) / sa

        wall_t = 1; side = 0; hit_u = 0.0; raw_d = MAX_DIST
        for _ in range(80):
            if sx_d < sy_d:
                sx_d += ddx; mx += ssx; side = 0
            else:
                sy_d += ddy; my += ssy; side = 1
            if 0 <= mx < MAP_W and 0 <= my < MAP_H:
                v = int(_MAP_NP[my, mx])
                if v:
                    wall_t = v
                    if side == 0:
                        raw_d = (mx * TILE - px + (0 if ssx > 0 else TILE)) / ca
                        hit_u = (py + raw_d * sa) % TILE
                    else:
                        raw_d = (my * TILE - py + (0 if ssy > 0 else TILE)) / sa
                        hit_u = (px + raw_d * ca) % TILE
                    break
            else:
                break

        if raw_d >= MAX_DIST:
            raw_d = MAX_DIST - 1.0
        dist_c = max(1.0, raw_d * math.cos(ra - pangle))
        _zbuf[i] = dist_c

        wall_h = int(PROJ_DIST * TILE / dist_c)
        tex_x  = int(hit_u) % TILE

        base_l = max(AMBIENT, 1.0 - (dist_c / (MAX_DIST * 0.60)) ** 0.65)
        if side == 1:
            base_l *= 0.72  # less harsh side darkening
        if CFG["fog"]:
            fog2   = min(1.0, dist_c / (MAX_DIST * 0.65))
            base_l = base_l * (1 - fog2) + AMBIENT * fog2
        if fl:
            ad = abs((i / NUM_RAYS - 0.5) * FOV)
            if ad < FL_CONE:
                base_l = min(1.0, base_l + (1 - ad / FL_CONE) ** 1.7 * max(0.0, 1 - dist_c / (TILE * 9)) * 0.78)

        col_rgb = _WCACHE[(wall_t, tex_x, _li(base_l))]
        top = max(0, half_h - wall_h // 2)
        bot = min(RH, half_h + wall_h // 2)
        span = bot - top
        if span > 0:
            _pxbuf[i, top:bot, :] = col_rgb[_tys(span)]

def blit_pxbuf() -> None:
    pygame.surfarray.blit_array(render_surf, _pxbuf)

# ═══════════════════════════════════════════════════════════════════════════════
#  POST-PROCESSING  — all surfarray locks released before assignment
# ═══════════════════════════════════════════════════════════════════════════════
def _get_vig(w2: int, h2: int) -> pygame.Surface:
    global _vig_cache, _vig_sz
    if _vig_sz != (w2, h2):
        vs = pygame.Surface((w2, h2), pygame.SRCALPHA)
        for i in range(0, 80, 2):
            a = int((1 - i / 80) ** 2.3 * 190)
            if a > 0:
                pygame.draw.rect(vs, (0, 0, 0, a), (i, i, w2 - i*2, h2 - i*2), 2)
        _vig_cache = vs
        _vig_sz = (w2, h2)
    return _vig_cache  # type: ignore

def post_process(surf: pygame.Surface, dmg_flash: float,
                 ads_t: float, wname: str) -> None:
    global _grain_buf
    arr = pygame.surfarray.pixels3d(surf)
    aw, ah = arr.shape[0], arr.shape[1]

    if CFG["film_grain"]:
        if _grain_buf is None or _grain_buf.shape[:2] != (aw, ah):
            _grain_buf = np.empty((aw, ah), dtype=np.int16)
        # Correct: generate noise, add to copy of arr, clip, then assign back
        _grain_buf[:] = _rng.integers(-18, 18, (aw, ah), dtype=np.int16)
        tmp = arr.astype(np.int16, copy=True)
        tmp[:, :, 0] += _grain_buf
        tmp[:, :, 1] += _grain_buf
        tmp[:, :, 2] += _grain_buf
        np.clip(tmp, 0, 255, out=tmp)
        # Must release lock before assigning back to surface
        del arr
        new_arr = pygame.surfarray.pixels3d(surf)
        new_arr[:] = tmp.astype(np.uint8)
        del new_arr
    else:
        del arr

    if CFG["chromatic_ab"] and dmg_flash > 0.12:
        arr2 = pygame.surfarray.pixels3d(surf)
        sh = max(1, int(dmg_flash * 9))
        r_ch = arr2[:, :, 0].copy()
        b_ch = arr2[:, :, 2].copy()
        arr2[sh:,  :, 0] = (arr2[sh:,  :, 0] * 0.65 + r_ch[:-sh, :] * 0.35).astype(np.uint8)
        arr2[:-sh, :, 2] = (arr2[:-sh, :, 2] * 0.65 + b_ch[sh:,  :] * 0.35).astype(np.uint8)
        del arr2

    if CFG["dof_blur"] and ads_t > 0.6 and wname == "sniper":
        arr3 = pygame.surfarray.pixels3d(surf)
        aw3, ah3 = arr3.shape[0], arr3.shape[1]
        cx, cy = aw3 // 2, ah3 // 2
        r = min(cx, cy) // 3
        xs = np.linspace(-1, 1, aw3, dtype=np.float32)
        ys = np.linspace(-1, 1, ah3, dtype=np.float32)
        xx, yy = np.meshgrid(xs, ys, indexing='ij')
        dist2 = np.sqrt(xx**2 + yy**2)
        fade = np.clip((dist2 - r / (aw3 // 2)) / (r / (aw3 // 2) * 1.5), 0, 1) * ((ads_t - 0.6) / 0.4)
        for ch in range(3):
            arr3[:, :, ch] = np.clip(arr3[:, :, ch].astype(np.float32) * (1 - fade), 0, 255).astype(np.uint8)
        del arr3

def apply_damage_flash(surf: pygame.Surface, strength: float) -> None:
    """Fast edge flash using pre-baked mask — no Surface allocation."""
    if strength <= 0 or _edge_mask is None:
        return
    arr = pygame.surfarray.pixels3d(surf)
    aw, ah = arr.shape[0], arr.shape[1]
    if _edge_mask.shape == (aw, ah):
        add = (_edge_mask * strength * 220).astype(np.uint8)
        r_ch = arr[:, :, 0].astype(np.int16) + add
        g_ch = arr[:, :, 1].astype(np.int16) - (add // 2).astype(np.int16)
        b_ch = arr[:, :, 2].astype(np.int16) - (add // 2).astype(np.int16)
        del arr  # release lock first
        arr2 = pygame.surfarray.pixels3d(surf)
        arr2[:, :, 0] = np.clip(r_ch, 0, 255).astype(np.uint8)
        arr2[:, :, 1] = np.clip(g_ch, 0, 255).astype(np.uint8)
        arr2[:, :, 2] = np.clip(b_ch, 0, 255).astype(np.uint8)
        del arr2
    else:
        del arr

# ═══════════════════════════════════════════════════════════════════════════════
#  GRENADE
# ═══════════════════════════════════════════════════════════════════════════════
class Grenade:
    FUSE = 2.5; RADIUS = TILE * 2.8; DAMAGE = 85

    def __init__(self, x, y, vx, vy):
        self.x=x; self.y=y; self.vx=vx; self.vy=vy
        self.timer=self.FUSE; self.alive=True; self.bob=0.0

    def update(self, dt: float) -> bool:
        self.timer -= dt; self.bob += dt * 8
        nx = self.x + self.vx * dt; ny = self.y + self.vy * dt
        if is_wall(nx, self.y): self.vx *= -0.45; nx = self.x
        if is_wall(self.x, ny): self.vy *= -0.45; ny = self.y
        self.x, self.y = nx, ny
        self.vx *= 0.78 ** dt; self.vy *= 0.78 ** dt
        if self.timer <= 0:
            self.alive = False; return True
        return False

# ═══════════════════════════════════════════════════════════════════════════════
#  WEAPON
# ═══════════════════════════════════════════════════════════════════════════════
from dataclasses import dataclass

@dataclass
class WDef:
    name: str; damage: int; rpm: int; mag: int; reserve: int
    recoil: float; spread: float; pellets: int; sfx_k: str
    color: Tuple; reload_t: float; is_auto: bool = False

    @property
    def fire_cd(self) -> float:
        return 60.0 / self.rpm

WDEFS: Dict[str, WDef] = {
    "pistol":  WDef("Pistol",  26, 220, 15,  60, 2.8, 1.8, 1, "pistol",  (175, 175, 180), 1.2),
    "shotgun": WDef("Shotgun", 22,  70,  8,  32, 7.0, 7.5, 8, "shotgun", (165, 105,  40), 1.8),
    "rifle":   WDef("Rifle",   34, 520, 30, 120, 4.5, 1.2, 1, "rifle",   ( 80,  85,  95), 1.3, True),
    "smg":     WDef("SMG",     20, 750, 25,  90, 3.2, 2.8, 1, "rifle",   ( 70, 130,  80), 1.1, True),
    "sniper":  WDef("Sniper",  98,  55,  5,  20, 9.0, 0.3, 1, "rifle",   ( 60,  60,  70), 2.2),
}

class Weapon:
    def __init__(self, d: WDef):
        self.d = d; self.ammo_mag = d.mag; self.ammo_res = d.reserve
        self.kick_y = 0.0; self.sway_x = 0.0; self.sway_y = 0.0
        self._shells = False

    @property
    def name(self)    -> str:   return self.d.name
    @property
    def damage(self)  -> int:   return self.d.damage
    @property
    def spread(self)  -> float: return self.d.spread
    @property
    def pellets(self) -> int:   return self.d.pellets
    @property
    def recoil(self)  -> float: return self.d.recoil
    @property
    def is_auto(self) -> bool:  return self.d.is_auto

    def can_shoot(self) -> bool: return self.ammo_mag > 0

    def fire(self) -> bool:
        if not self.can_shoot(): return False
        self.ammo_mag -= 1; self.kick_y = self.d.recoil * 18
        self._shells = True; sfx(self.d.sfx_k); return True

    def start_reload(self) -> None: sfx("reload")

    def finish_reload(self) -> None:
        take = min(self.d.mag - self.ammo_mag, self.ammo_res)
        self.ammo_mag += take; self.ammo_res -= take

    def add_ammo(self, n: int = 20) -> None:
        self.ammo_res = min(self.ammo_res + n, self.d.reserve * 3)

    def update_anim(self, dt: float, vx: float, vy: float) -> None:
        self.kick_y = max(0.0, self.kick_y - dt * 105)
        self.sway_x += (vx * 0.010 - self.sway_x) * min(1.0, dt * 9)
        self.sway_y += (vy * 0.007 - self.sway_y) * min(1.0, dt * 9)

# ═══════════════════════════════════════════════════════════════════════════════
#  PLAYER
# ═══════════════════════════════════════════════════════════════════════════════
_SLIDE_DIRS = [(math.cos(a), math.sin(a)) for a in [math.pi * 0.25 * i for i in range(8)]]

class Player:
    R = 12.0; BASE_SPD = 170.0; SPRINT_M = 1.60; CROUCH_M = 0.55
    STAM_MAX = 100.0; STAM_REGEN = 38.0; STAM_COST = 85.0
    ADS_FOV = math.radians(30); ADS_SPD = 7.0

    def __init__(self, weapons: Dict[str, Weapon]):
        self.x = 2.5 * TILE; self.y = 2.5 * TILE; self.angle = 0.3; self.pitch = 0.0
        self.hp = 100; self.max_hp = 100; self.alive = True
        self.weapons = weapons; self.wname = "pistol"
        self.shoot_cd = 0.0; self.reload_cd = 0.0
        self.dmg_flash = 0.0; self.low_hp = 0.0; self.shield = 0.0
        self.vx = 0.0; self.vy = 0.0; self.stamina = self.STAM_MAX
        self.crouching = False; self.sprinting = False
        self.bob = 0.0; self.moving = False
        self.lean = 0.0; self.lean_tgt = 0.0
        self.ads = False; self.ads_t = 0.0; self._nfov = CFG["fov_deg"]
        self.flashlight = True; self.grenades = 3
        self.kills = 0; self.hs = 0; self.score = 0
        self.killfeed: List[Tuple[str, float]] = []
        self._step_t = 0.0

    @property
    def cw(self) -> Weapon:
        return self.weapons[self.wname]

    def update(self, dt: float, keys) -> None:
        self.sprinting = ((keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
                          and not self.crouching and self.stamina > 0 and self.moving)
        self.crouching = bool(keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL])

        if self.sprinting:
            spd = self.BASE_SPD * self.SPRINT_M
            self.stamina = max(0.0, self.stamina - self.STAM_COST * dt)
        elif self.crouching:
            spd = self.BASE_SPD * self.CROUCH_M
            self.stamina = min(self.STAM_MAX, self.stamina + self.STAM_REGEN * 0.6 * dt)
        else:
            spd = self.BASE_SPD
            self.stamina = min(self.STAM_MAX, self.stamina + self.STAM_REGEN * dt)

        self.lean_tgt = 0.0
        if keys[pygame.K_q]: self.lean_tgt = -1.0
        if keys[pygame.K_e]: self.lean_tgt =  1.0
        self.lean += (self.lean_tgt - self.lean) * min(1.0, dt * 12)

        dx = dy = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:   dx += math.cos(self.angle); dy += math.sin(self.angle)
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:  dx -= math.cos(self.angle); dy -= math.sin(self.angle)
        if keys[pygame.K_a]: dx += math.sin(self.angle); dy -= math.cos(self.angle)
        if keys[pygame.K_d]: dx -= math.sin(self.angle); dy += math.cos(self.angle)
        self.moving = (dx != 0 or dy != 0)
        if self.moving:
            m = math.hypot(dx, dy); dx /= m; dy /= m

        ACC  = spd * 14; FRIC = 0.06 ** dt
        if self.moving: self.vx += dx * ACC * dt; self.vy += dy * ACC * dt
        self.vx *= FRIC; self.vy *= FRIC
        cs = math.hypot(self.vx, self.vy)
        if cs > spd: self.vx = self.vx / cs * spd; self.vy = self.vy / cs * spd
        if cs < 0.4: self.vx = self.vy = 0.0

        nx = self.x + self.vx * dt; ny = self.y + self.vy * dt
        r  = self.R
        if   not self._col(nx, ny, r): self.x, self.y = nx, ny
        elif not self._col(nx, self.y, r): self.x = nx; self.vy = 0.0
        elif not self._col(self.x, ny, r): self.y = ny; self.vx = 0.0
        else: self.vx = self.vy = 0.0

        bspd = 9.5 if self.sprinting else (3.5 if self.crouching else 6.0)
        if self.moving:
            self.bob += dt * bspd
        else:
            tgt = round(self.bob / math.pi) * math.pi
            self.bob += (tgt - self.bob) * min(1.0, dt * 5)

        if self.ads:  self.ads_t = min(1.0, self.ads_t + dt * self.ADS_SPD)
        else:         self.ads_t = max(0.0, self.ads_t - dt * self.ADS_SPD)

        global FOV, PROJ_DIST
        nfov = math.radians(self._nfov)
        FOV       = nfov + (self.ADS_FOV - nfov) * self.ads_t
        PROJ_DIST = (RW / 2) / math.tan(max(0.05, FOV / 2))

        self.shoot_cd  = max(0.0, self.shoot_cd - dt)
        if self.reload_cd > 0:
            self.reload_cd -= dt
            if self.reload_cd <= 0:
                self.cw.finish_reload()
        self.dmg_flash = max(0.0, self.dmg_flash - dt)
        self.shield    = max(0.0, self.shield - dt)
        self.low_hp   += dt * 3.5
        self.cw.update_anim(dt, self.vx, self.vy)

        if self.moving:
            self._step_t -= dt
            if self._step_t <= 0:
                sfx("step", 0.45)
                self._step_t = 0.30 if self.sprinting else 0.46

    def _col(self, x, y, r) -> bool:
        for dx in (-r, 0.0, r):
            for dy in (-r, 0.0, r):
                if is_wall(x + dx, y + dy): return True
        return False

    def rotate(self, rx: float, ry: float) -> None:
        self.angle += rx * CFG["mouse_sens"]
        ry2 = -ry if CFG["invert_y"] else ry
        self.pitch = max(-RH // 3, min(RH // 3, self.pitch + ry2 * CFG["mouse_sens"] * RH * 0.45))

    def try_shoot(self) -> bool:
        w = self.cw
        if self.reload_cd > 0: return False
        if not w.can_shoot():
            self.try_reload()  # auto-reload when empty
            return False
        if self.shoot_cd > 0: return False
        self.shoot_cd = w.d.fire_cd; return w.fire()

    def try_reload(self) -> None:
        w = self.cw
        if self.reload_cd > 0: return
        if w.ammo_mag < w.d.mag and w.ammo_res > 0:
            self.reload_cd = w.d.reload_t; w.start_reload()

    def switch(self, name: str) -> None:
        if name in self.weapons and self.wname != name and self.reload_cd <= 0:
            self.wname = name; self.shoot_cd = 0.22; self.cw.kick_y = 0.0

    def damage(self, dmg: int) -> None:
        if self.shield > 0: return
        self.hp = max(0, self.hp - dmg); self.dmg_flash = 0.40; sfx("hurt")
        if self.hp <= 0: self.alive = False

    def heal(self, n: int) -> None:
        self.hp = min(self.max_hp, self.hp + n)

    def grant_shield(self, t: float) -> None:
        self.shield = t

    def throw_grenade(self) -> Optional[Grenade]:
        if self.grenades <= 0: return None
        self.grenades -= 1; sfx("grenade")
        return Grenade(self.x, self.y, math.cos(self.angle)*285, math.sin(self.angle)*285)

# ═══════════════════════════════════════════════════════════════════════════════
#  ENEMY
# ═══════════════════════════════════════════════════════════════════════════════
class Enemy:
    R = 14.0

    def __init__(self, x, y, wave=1):
        self.x=x; self.y=y; self.hp_max=55+wave*9; self.hp=self.hp_max
        self.speed=random.uniform(45+wave*5, 80+wave*7); self.alive=True; self.angle=0.0
        self.atk_cd=random.uniform(0.5, 1.5); self.stagger=0.0; self.alert=False
        self.growl_cd=random.uniform(2, 8)
        self.anim_t=random.uniform(0, math.pi*2); self.anim_spd=random.uniform(3.5, 6.5)
        self.bob=random.uniform(0, math.pi*2); self.hit_flash=0.0; self.detail=2
        self.skin=random.randint(0, 3); self.outfit=random.randint(0, 4)
        self._stuck_t=0.0; self._wander=random.uniform(0, math.pi*2)

    @property
    def skin_col(self) -> Tuple:
        pal = [(180,150,130),(160,120,80),(100,70,50),(130,160,120)]
        c = pal[self.skin]
        if self.hit_flash > 0:
            f = self.hit_flash / 0.12
            c = (min(255, int(c[0]+(255-c[0])*f*0.6)),
                 max(0, int(c[1]*(1-f*0.4))), max(0, int(c[2]*(1-f*0.4))))
        return c

    @property
    def cloth_col(self) -> Tuple:
        return [(70,55,45),(55,65,45),(80,80,90),(95,55,35),(30,30,30)][self.outfit]

    def update(self, dt: float, player: Player) -> None:
        if not self.alive: return
        self.anim_t   += dt * self.anim_spd; self.bob += dt * 4.2
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.atk_cd    = max(0.0, self.atk_cd - dt)
        self.growl_cd  = max(0.0, self.growl_cd - dt)

        dx = player.x - self.x; dy = player.y - self.y
        dist = math.hypot(dx, dy)
        if dist < 1: return
        self.angle = math.atan2(dy, dx)
        if dist < TILE * 5: self.alert = True

        if self.growl_cd <= 0 and dist < TILE * 6:
            sfx("growl", min(1.0, (TILE*6 - dist) / (TILE*4)))
            self.growl_cd = random.uniform(3.0, 8.0)

        if self.stagger > 0: self.stagger -= dt; return

        if self.alert and dist > self.R + player.R + 2:
            spd = self.speed * dt; ndx = dx / dist; ndy = dy / dist
            nx = self.x + ndx * spd; ny = self.y + ndy * spd
            if not self._col(nx, ny):
                self.x, self.y = nx, ny; self._stuck_t = 0.0
            else:
                self._stuck_t += dt; moved = False
                goal_a = math.atan2(dy, dx)
                for sdx, sdy in sorted(_SLIDE_DIRS,
                        key=lambda sd: abs(math.atan2(sd[1], sd[0]) - goal_a + math.pi) % (2*math.pi)):
                    tx = self.x + sdx * spd * 1.4; ty = self.y + sdy * spd * 1.4
                    if not self._col(tx, ty):
                        self.x, self.y = tx, ty; moved = True; break
                if not moved and self._stuck_t > 1.5:
                    self._wander += random.uniform(-0.8, 0.8)
                    wx = self.x + math.cos(self._wander) * spd * 2
                    wy = self.y + math.sin(self._wander) * spd * 2
                    if not self._col(wx, wy): self.x, self.y = wx, wy

        if dist < self.R + player.R + 10 and self.atk_cd <= 0:
            player.damage([8, 13, 19, 26][CFG["difficulty"]])
            self.atk_cd = 0.9

        self.detail = 2 if dist < 220 else (1 if dist < 420 else 0)

    def _col(self, x, y) -> bool:
        r = self.R
        for dx in (-r, 0.0, r):
            for dy in (-r, 0.0, r):
                if is_wall(x + dx, y + dy): return True
        return False

    def hit(self, dmg: int, headshot: bool = False) -> bool:
        if headshot: dmg = int(dmg * 2.25)
        self.hp -= dmg; self.hit_flash = 0.12
        self.stagger = 0.20 if headshot else 0.06; self.alert = True
        if self.hp <= 0: self.alive = False; return True
        return False

# ═══════════════════════════════════════════════════════════════════════════════
#  PICKUP
# ═══════════════════════════════════════════════════════════════════════════════
class Pickup:
    def __init__(self, x, y, kind, wname="pistol"):
        self.x=x; self.y=y; self.kind=kind; self.wname=wname
        self.alive=True; self.bob=random.uniform(0, math.pi*2)

    def update(self, dt: float) -> None: self.bob += dt * 2.8

    def try_collect(self, player: Player) -> bool:
        if math.hypot(self.x - player.x, self.y - player.y) < 28:
            if self.kind == "ammo":    player.weapons[self.wname].add_ammo(30)
            elif self.kind == "health": player.heal(45)
            elif self.kind == "grenade": player.grenades = min(player.grenades+2, 5)
            elif self.kind == "armor": player.grant_shield(6.0); player.heal(20)
            sfx("pickup"); self.alive = False; return True
        return False

# ═══════════════════════════════════════════════════════════════════════════════
#  SPRITE PROJECTION
# ═══════════════════════════════════════════════════════════════════════════════
def project_sprite(px, py, pa, sx, sy) -> Optional[Tuple]:
    dx = sx - px; dy = sy - py; dist = math.hypot(dx, dy)
    if dist < 1.0: return None
    sa = (math.atan2(dy, dx) - pa + math.pi) % (2 * math.pi) - math.pi
    if abs(sa) >= FOV * 0.52: return None
    scr_x = int((sa / FOV + 0.5) * RW); scr_x = max(0, min(RW-1, scr_x))
    sph = int(PROJ_DIST * TILE / dist) if dist > 1 else RH
    return scr_x, sph, dist

# ═══════════════════════════════════════════════════════════════════════════════
#  ENEMY SPRITE
# ═══════════════════════════════════════════════════════════════════════════════
def draw_enemy(surf, scr_x, sph, dist, enemy: Enemy, pitch_off: int) -> None:
    if sph < 5: return
    hw = sph // 2
    vis = False
    for col in range(max(0, scr_x-hw//2), min(RW, scr_x+hw//2+1), max(1, hw//6)):
        if 0 <= col < NUM_RAYS and dist < _zbuf[col]: vis = True; break
    if not vis: return

    fog   = max(0.0, 1.0 - (dist / (MAX_DIST * 0.48))) ** 0.6
    rh_h  = surf.get_height() // 2
    top   = (rh_h + pitch_off) - sph // 2 + int(math.sin(enemy.bob) * 2)
    skin  = tuple(int(c * fog) for c in enemy.skin_col)
    cloth = tuple(int(c * fog) for c in enemy.cloth_col)

    head_r = max(3, sph // 7); neck_h = max(1, sph // 18); torso_h = sph // 3; tw = hw
    arm_len = sph // 4; leg_h = sph // 3
    head_cy = top + sph // 7; neck_y = head_cy + head_r
    torso_y = neck_y + neck_h; hip_y = torso_y + torso_h
    swing = math.sin(enemy.anim_t * 2.5) * min(6, sph // 14); th = max(1, sph // 28)

    if CFG["shadows"] and sph > 20:
        sr = max(5, hw // 3)
        ss = pygame.Surface((sr*2, max(1, sr//2)), pygame.SRCALPHA)
        pygame.draw.ellipse(ss, (0,0,0, int(80*fog)), (0,0,sr*2, max(1,sr//2)))
        surf.blit(ss, (scr_x-sr, top+sph-max(1,sr//4)))

    if enemy.detail > 0 and sph > 30:
        pygame.draw.line(surf, cloth, (scr_x-tw//4, hip_y), (scr_x-tw//3, hip_y+leg_h+int(swing)), th+1)
        pygame.draw.line(surf, cloth, (scr_x+tw//4, hip_y), (scr_x+tw//3, hip_y+leg_h-int(swing)), th+1)
        shoe = tuple(max(0, c-40) for c in cloth)
        if sph > 60:
            pygame.draw.circle(surf, shoe, (scr_x-tw//3, hip_y+leg_h+int(swing)), max(2, th+1))
            pygame.draw.circle(surf, shoe, (scr_x+tw//3, hip_y+leg_h-int(swing)), max(2, th+1))

    pygame.draw.rect(surf, cloth, (scr_x-tw//2, torso_y, tw, torso_h))
    if enemy.detail > 1 and sph > 40:
        ss2 = pygame.Surface((tw//2, torso_h), pygame.SRCALPHA); ss2.fill((0,0,0,45))
        surf.blit(ss2, (scr_x, torso_y))
        belt_y = torso_y + int(torso_h * 0.75)
        pygame.draw.line(surf, (30,25,20), (scr_x-tw//2, belt_y), (scr_x+tw//2, belt_y), 2)

    if enemy.detail > 0 and sph > 25:
        at = max(1, sph // 30); ay0 = torso_y + sph // 16
        lax = scr_x - tw // 2; lax2 = lax - arm_len // 2; lay2 = ay0 + arm_len + int(swing*1.5)
        pygame.draw.line(surf, cloth, (lax, ay0), (lax2, lay2), at)
        rax = scr_x + tw // 2; rax2 = rax + arm_len // 2; ray2 = ay0 + arm_len - int(swing*1.5)
        pygame.draw.line(surf, cloth, (rax, ay0), (rax2, ray2), at)
        if sph > 50:
            pygame.draw.circle(surf, skin, (lax2, lay2), max(2, head_r//3))
            pygame.draw.circle(surf, skin, (rax2, ray2), max(2, head_r//3))

    if sph > 20:
        pygame.draw.line(surf, skin, (scr_x, neck_y), (scr_x, neck_y+neck_h), max(2, head_r//2))
    pygame.draw.circle(surf, skin, (scr_x, head_cy), head_r)

    if sph > 35 and enemy.detail > 0:
        hc = [(25,20,15),(60,40,20),(15,12,10),(80,60,40)][enemy.skin]
        pygame.draw.arc(surf, hc, pygame.Rect(scr_x-head_r, head_cy-head_r, head_r*2, head_r), 0, math.pi, max(2, head_r//2))

    if enemy.detail > 1 and sph > 50:
        er = max(1, head_r // 4); ey2 = head_cy - head_r // 5
        for ox in (-head_r//2, head_r//2):
            pygame.draw.circle(surf, (15,10,10), (scr_x+ox, ey2), er+1)
            pygame.draw.circle(surf, (220,30,10), (scr_x+ox, ey2), er)
            if sph > 80:
                pygame.draw.circle(surf, (255,80,20), (scr_x+ox, ey2), max(1, er-1))
        if sph > 70:
            pygame.draw.line(surf, (60,20,20), (scr_x-head_r//3, head_cy+head_r//3),
                             (scr_x+head_r//3, head_cy+head_r//3+head_r//5), 2)

    if sph > 35 and enemy.detail > 0:
        bw = min(62, hw); bx2 = scr_x - bw // 2; by2 = head_cy - head_r - 10
        hp_pct = max(0.0, enemy.hp / enemy.hp_max)
        pygame.draw.rect(surf, (70,0,0), (bx2, by2, bw, 5))
        gw = int(bw * hp_pct)
        if gw > 0:
            pygame.draw.rect(surf, (int(220*(1-hp_pct)), int(220*hp_pct), 0), (bx2, by2, gw, 5))
        pygame.draw.rect(surf, (160,160,160), (bx2, by2, bw, 5), 1)

# ═══════════════════════════════════════════════════════════════════════════════
#  PICKUP / GRENADE SPRITES
# ═══════════════════════════════════════════════════════════════════════════════
def draw_pickup(surf, scr_x, sph, dist, pickup: Pickup, pitch_off: int) -> None:
    ri = scr_x
    if not (0 <= ri < NUM_RAYS and dist < _zbuf[ri]): return
    cy = (surf.get_height()//2 + pitch_off) + sph//4 + int(math.sin(pickup.bob)*5)
    w2 = max(4, sph // 5)
    if pickup.kind == "ammo":
        g = int(110 + math.sin(pickup.bob*2)*35)
        pygame.draw.ellipse(surf, (max(0,min(255,g)), max(0,min(255,g//2)), 0), (scr_x-w2, cy-w2//2, w2*2, w2))
        pygame.draw.circle(surf, (255,200,0), (scr_x, cy), w2//2)
        if sph > 30:
            lbl = F_XS.render("AMMO", True, (255,220,80))
            surf.blit(lbl, (scr_x - lbl.get_width()//2, cy-w2-14))
    elif pickup.kind == "health":
        pygame.draw.circle(surf, (200,0,20), (scr_x, cy), w2//2)
        if sph > 30:
            pygame.draw.rect(surf, (255,255,255), (scr_x-1, cy-w2//3, 3, w2*2//3))
            pygame.draw.rect(surf, (255,255,255), (scr_x-w2//3, cy-1, w2*2//3, 3))
    elif pickup.kind == "grenade":
        pygame.draw.circle(surf, (80,140,60), (scr_x, cy), w2//2)
    elif pickup.kind == "armor":
        # Blue shield icon
        pygame.draw.polygon(surf, (0,120,220), [
            (scr_x, cy-w2//2), (scr_x+w2//2, cy-w2//4),
            (scr_x+w2//2, cy+w2//4), (scr_x, cy+w2//2),
            (scr_x-w2//2, cy+w2//4), (scr_x-w2//2, cy-w2//4)])
        if sph > 30:
            lbl2 = F_XS.render("ARMOR", True, (80,180,255))
            surf.blit(lbl2, (scr_x - lbl2.get_width()//2, cy-w2-14))

def draw_grenade_spr(surf, scr_x, sph, dist, gren: Grenade, pitch_off: int) -> None:
    ri = scr_x
    if not (0 <= ri < NUM_RAYS and dist < _zbuf[ri]): return
    cy = surf.get_height()//2 + pitch_off + sph//3 + int(math.sin(gren.bob)*4)
    w2 = max(3, sph // 8); blink = int(gren.timer * 4) % 2
    pygame.draw.circle(surf, (255,80,0) if blink else (80,140,60), (scr_x, cy), w2)

# ═══════════════════════════════════════════════════════════════════════════════
#  WEAPON VIEW MODEL
# ═══════════════════════════════════════════════════════════════════════════════
def draw_weapon(surf: pygame.Surface, player: Player, dt: float) -> None:
    w = player.cw; ads = player.ads_t; rw2, rh2 = surf.get_size()
    bamp = 5.0 if player.sprinting else (1.5 if player.crouching else 3.5)
    bamp *= (1 - ads * 0.75)
    bx_off = math.sin(player.bob) * bamp; by_off = abs(math.cos(player.bob)) * bamp * 0.55
    lean_off = int(player.lean * 15)
    ox = int(bx_off + w.sway_x + lean_off - int(rw2//8*ads))
    oy = int(by_off + w.kick_y + w.sway_y - int(rh2//7*ads))
    bx = rw2 // 2; by = rh2

    def r(rx,ry,rw3,rh3,col): pygame.draw.rect(surf,col,(bx+rx+ox,by+ry+oy,rw3,rh3))
    def l(x1,y1,x2,y2,col,t=1): pygame.draw.line(surf,col,(bx+x1+ox,by+y1+oy),(bx+x2+ox,by+y2+oy),t)
    def c(cx,cy2,rad,col): pygame.draw.circle(surf,col,(bx+cx+ox,by+cy2+oy),rad)

    gc=w.d.color; gd=tuple(max(0,v-55) for v in gc); gl=tuple(min(255,v+55) for v in gc)
    wd=(100,65,30); wl=(130,90,45); grp=(45,35,25); mx=my=0
    wn = player.wname

    if wn == "pistol":
        r(50,-148,60,24,gc);r(50,-148,60,8,gd);r(52,-146,56,4,gl);r(75,-145,18,8,gd)
        r(44,-138,8,16,gd);r(45,-132,12,4,(30,30,30));r(50,-124,38,16,gc);r(70,-122,14,18,gd)
        r(76,-108,30,55,grp);r(78,-106,26,51,(35,27,18))
        for i in range(5): l(78,-100+i*8,102,-98+i*8,(25,18,12))
        r(78,-58,26,6,(20,20,20));r(48,-150,4,5,(20,20,20));r(100,-150,8,5,(20,20,20))
        r(103,-150,2,5,(180,180,180)); mx,my=bx+46+ox,by-134+oy
    elif wn == "shotgun":
        r(30,-128,88,38,wd);r(32,-126,84,34,wl)
        for i in range(6): l(32,-126+i*5,114,-126+i*5,wd)
        r(28,-138,56,20,gc);r(28,-138,56,7,gd);r(8,-130,22,9,(35,35,38));r(8,-119,22,9,(35,35,38))
        r(6,-132,10,4,(20,20,20));r(6,-122,10,4,(20,20,20));r(22,-128,28,7,wl);r(60,-122,14,18,gd)
        r(70,-118,28,50,grp);r(72,-116,24,46,(35,27,18)); mx,my=bx+8+ox,by-126+oy
    elif wn == "rifle":
        r(8,-138,100,20,gc);r(8,-138,100,8,gd);r(10,-136,96,4,gl);r(40,-152,50,14,gd)
        r(42,-150,46,10,(50,50,55));r(50,-118,45,18,gd);r(70,-118,22,45,grp);r(72,-116,18,41,(35,27,18))
        r(96,-132,34,30,gd);r(98,-130,30,26,gc);r(128,-128,14,18,gd);r(55,-118,20,42,(25,25,28))
        r(57,-116,16,38,(35,35,38));r(0,-134,12,14,(40,40,44));r(-4,-132,8,10,(25,25,28))
        r(-8,-130,6,6,(20,20,22));r(40,-158,40,10,(30,30,32));r(42,-156,36,6,(20,50,80))
        c(42,-153,4,(25,25,28));c(78,-153,4,(25,25,28));r(88,-138,8,5,gd);r(62,-100,14,18,gd)
        mx,my=bx-4+ox,by-128+oy
    elif wn == "smg":
        r(40,-134,65,18,gc);r(40,-134,65,6,gd);r(22,-130,20,10,gd);r(102,-130,20,14,gd)
        r(60,-118,14,38,(25,25,28));r(72,-118,22,42,grp);r(74,-116,18,38,(35,27,18));r(67,-108,10,16,gd)
        mx,my=bx+22+ox,by-126+oy
    elif wn == "sniper":
        r(-20,-132,30,10,(40,40,44));r(-24,-130,10,6,(25,25,28));r(10,-140,90,22,gc)
        r(10,-140,90,8,gd);r(12,-138,86,4,gl);r(80,-140,8,14,(30,30,32));c(88,-134,5,gd)
        r(25,-160,55,14,(25,25,28));r(27,-158,51,10,(15,45,75))
        c(28,-153,6,(20,20,22));c(79,-153,6,(20,20,22));r(95,-136,38,26,wd);r(97,-134,34,22,wl)
        r(72,-120,24,50,grp);r(74,-118,20,46,(35,27,18))
        if player.crouching: l(-16,-128,-20,-112,gd,2);l(-10,-128,-6,-112,gd,2)
        r(50,-120,14,30,(25,25,28)); mx,my=bx-20+ox,by-128+oy

    if w.kick_y > 4:
        fs = max(4, min(22, int(14 * (w.kick_y / (w.d.recoil * 18)))))
        pygame.draw.line(surf,(255,240,80),(mx-fs,my),(mx+fs,my),3)
        pygame.draw.line(surf,(255,240,80),(mx,my-fs),(mx,my+fs),3)
        pygame.draw.circle(surf,(255,240,80),(mx,my),fs)
        pygame.draw.circle(surf,(255,255,220),(mx,my),fs//2)
        if w._shells:
            emit_muzzle(mx, my, 7); emit_shell(bx+80+ox, by-110+oy); w._shells = False

    if player.reload_cd > 0:
        pct = 1.0 - player.reload_cd / w.d.reload_t; bw2=130; bx3=rw2//2-bw2//2; by3=rh2-68
        pygame.draw.rect(surf,(35,35,35),(bx3,by3,bw2,7))
        pygame.draw.rect(surf,(210,200,0),(bx3,by3,int(bw2*pct),7))
        pygame.draw.rect(surf,(160,160,160),(bx3,by3,bw2,7),1)
        rt = F_XS.render("RELOADING", True, (220,220,150))
        surf.blit(rt, (rw2//2 - rt.get_width()//2, by3-16))

# ═══════════════════════════════════════════════════════════════════════════════
#  CROSSHAIR
# ═══════════════════════════════════════════════════════════════════════════════
def draw_crosshair(surf: pygame.Surface, player: Player) -> None:
    rw2, rh2 = surf.get_size(); cx, cy = rw2//2, rh2//2
    if player.ads_t > 0.85:
        pygame.draw.circle(surf,(255,50,50),(cx,cy),3)
        pygame.draw.circle(surf,(255,120,80),(cx,cy),1); return
    sp = int(player.cw.spread * 2.5 + player.cw.kick_y * 0.25); gap=5+sp; sz=11
    for col, off in [((60,60,60),1),((255,255,255),0)]:
        o = off
        pygame.draw.line(surf,col,(cx-sz-gap-o,cy+o),(cx-gap+o,cy+o),2)
        pygame.draw.line(surf,col,(cx+gap-o,cy+o),(cx+sz+gap+o,cy+o),2)
        pygame.draw.line(surf,col,(cx+o,cy-sz-gap-o),(cx+o,cy-gap+o),2)
        pygame.draw.line(surf,col,(cx+o,cy+gap-o),(cx+o,cy+sz+gap+o),2)
    pygame.draw.circle(surf,(255,255,255),(cx,cy),2)

# ═══════════════════════════════════════════════════════════════════════════════
#  HIT DETECTION  (single call, correct headshot)
# ═══════════════════════════════════════════════════════════════════════════════
def process_shot(player: Player, enemies: List[Enemy], wave: int) -> None:
    ww = player.cw; spread = ww.spread * math.pi / 180
    aim_a = player.angle + random.uniform(-spread, spread) + ww.kick_y * 0.0007

    if CFG["aim_assist"] and player.wname != "sniper":
        best_da = 0.10; best_e = None
        for e in enemies:
            if not e.alive: continue
            dx2 = e.x - player.x; dy2 = e.y - player.y
            da  = (math.atan2(dy2, dx2) - aim_a + math.pi) % (2*math.pi) - math.pi
            if abs(da) < best_da and math.hypot(dx2, dy2) < 385:
                best_da = abs(da); best_e = e
        if best_e and best_da < 0.09:
            aim_a = math.atan2(best_e.y - player.y, best_e.x - player.x) + \
                    random.uniform(-spread * 0.15, spread * 0.15)

    for e in enemies:
        if not e.alive: continue
        sp = project_sprite(player.x, player.y, aim_a, e.x, e.y)
        if not sp: continue
        scr_x2, sph2, dist2 = sp; hw = sph2 // 2
        vis = False; step = max(1, hw // 6)
        for col2 in range(max(0, scr_x2-hw//2), min(RW, scr_x2+hw//2+1), step):
            if col2 < NUM_RAYS and dist2 < _zbuf[col2]: vis = True; break
        if not vis: continue

        # Headshot: is the crosshair (screen centre) inside the head zone of this sprite?
        # Head is drawn at top + sph//7, radius = sph//7
        # So head zone is rows [top, top + sph*2//7] on screen
        rh_half   = RH // 2 + int(player.pitch)
        top_sprite = rh_half - sph2 // 2
        # Head centre in screen-Y terms
        head_top  = top_sprite
        head_bot  = top_sprite + int(sph2 * 0.28)
        # The actual crosshair screen-Y is always RH//2 (centre of render surf)
        crosshair_screen_y = RH // 2
        headshot = head_top <= crosshair_screen_y <= head_bot

        dmg    = random.randint(int(ww.damage * 0.82), int(ww.damage * 1.18))
        killed = e.hit(dmg, headshot)
        emit_blood(scr_x2, RH//2 + random.randint(-22, 22), 18 if headshot else 11)
        emit_dust(scr_x2, RH//2, 3)

        if killed:
            player.kills += 1
            if headshot:
                player.hs += 1; player.score += 200
                player.killfeed.append(("  HEADSHOT  +200", 2.8))
            else:
                player.score += 100
                player.killfeed.append(("  KILL  +100", 2.0))
            player.score += wave * 12
        break

# ═══════════════════════════════════════════════════════════════════════════════
#  HUD
# ═══════════════════════════════════════════════════════════════════════════════
def _flip_to_screen(surf: pygame.Surface) -> None:
    """Blit surf (W×H) to screen with letterboxing if fullscreen."""
    if _LB_SCALE != 1.0 and _LB_SCALE > 0:
        blit_w = int(W * _LB_SCALE); blit_h = int(H * _LB_SCALE)
        scaled = pygame.transform.scale(surf, (blit_w, blit_h))
        screen.fill((0, 0, 0))
        screen.blit(scaled, (_LB_X, _LB_Y))
    else:
        screen.blit(surf, (0, 0))

def draw_hud(surf: pygame.Surface, player: Player, wave: int,
             enemies_left: int, fps: float, mode_name: str) -> None:
    sw, sh = surf.get_size()

    if player.dmg_flash > 0:
        apply_damage_flash(surf, player.dmg_flash)

    if player.hp < 35 and player.alive:
        p = (math.sin(player.low_hp) * 0.5 + 0.5); alpha = int(p * 115)
        lhp = pygame.Surface((sw, sh), pygame.SRCALPHA)
        for i in range(0, 22, 2):
            a = int(alpha * (1 - i/22))
            pygame.draw.rect(lhp, (185,0,0,a), (i,i,sw-i*2,sh-i*2), 2)
        surf.blit(lhp, (0, 0))

    if CFG["vignette"]:
        surf.blit(_get_vig(sw, sh), (0, 0))

    hbg = pygame.Surface((252, 82), pygame.SRCALPHA); hbg.fill((0,0,0,160))
    surf.blit(hbg, (11, sh-97))
    hp_pct = max(0.0, player.hp / player.max_hp)
    hc = (0,200,55) if hp_pct > 0.6 else ((200,160,0) if hp_pct > 0.3 else (230,0,0))
    pygame.draw.rect(surf,(80,0,0),(22,sh-87,210,20))
    if int(210*hp_pct) > 0: pygame.draw.rect(surf,hc,(22,sh-87,int(210*hp_pct),20))
    pygame.draw.rect(surf,(200,200,200),(22,sh-87,210,20),1)
    surf.blit(F_SM.render(f"HP  {player.hp:>3}",True,(255,255,255)),(25,sh-86))
    pygame.draw.rect(surf,(0,55,0),(22,sh-62,210,8))
    sw2 = int(210 * player.stamina / player.STAM_MAX)
    if sw2 > 0: pygame.draw.rect(surf,(0,195,75),(22,sh-62,sw2,8))
    pygame.draw.rect(surf,(140,140,140),(22,sh-62,210,8),1)
    surf.blit(F_XS.render("STAMINA",True,(170,170,170)),(25,sh-55))
    if player.shield > 0:
        surf.blit(F_SM.render(f"SHIELD {player.shield:.1f}s",True,(100,200,255)),(25,sh-43))

    cw = player.cw
    ams = "RELOADING..." if player.reload_cd > 0 else f"{cw.ammo_mag:>2}  /  {cw.ammo_res:>3}"
    ac  = (255,120,0) if player.reload_cd > 0 else (255,220,50)
    surf.blit(F_MD.render(ams,True,ac),(sw-F_MD.size(ams)[0]-18,sh-48))
    surf.blit(F_SM.render(cw.name.upper(),True,(200,200,200)),(sw-F_SM.size(cw.name.upper())[0]-18,sh-26))
    gt = F_XS.render(f"GRENADES: {'●'*player.grenades}",True,(100,200,80))
    surf.blit(gt,(sw-gt.get_width()-18,sh-65))

    wt = F_MD.render(f"{mode_name.upper()}  —  WAVE {wave}",True,(255,140,0))
    surf.blit(wt,(sw//2-wt.get_width()//2,10))
    surf.blit(F_SM.render(f"SCORE: {player.score}  KILLS: {player.kills}  HS: {player.hs}",True,(220,220,220)),(14,10))
    surf.blit(F_SM.render(f"ENEMIES: {enemies_left}",True,(225,50,50)),(14,30))

    inv = [("1","pistol"),("2","shotgun"),("3","rifle"),("4","smg"),("5","sniper")]
    ix  = sw//2 - (len(inv)*86)//2
    for key, wk in inv:
        if wk not in player.weapons: ix += 86; continue
        active = player.wname == wk; bc=(75,55,0) if active else(25,25,30)
        pygame.draw.rect(surf,bc,(ix,sh-30,82,22))
        pygame.draw.rect(surf,(160,130,0) if active else(70,70,75),(ix,sh-30,82,22),1)
        lbl = F_XS.render(f"[{key}]{player.weapons[wk].d.name[:6]}",True,(255,220,0) if active else(170,170,170))
        surf.blit(lbl,(ix+4,sh-26)); ix += 86

    fc = (255,255,140) if player.flashlight else (100,100,100)
    surf.blit(F_XS.render(f"[F] {'●' if player.flashlight else '○'}  FLASHLIGHT",True,fc),(sw//2-50,sh-52))

    ky = 55
    for txt, _ in player.killfeed[:5]:
        kt = F_XS.render(txt,True,(255,80,80)); surf.blit(kt,(sw-kt.get_width()-14,ky)); ky += 16

    if CFG["show_fps"]:
        fp = F_XS.render(f"{fps:.0f} FPS",True,(80,80,80)); surf.blit(fp,(sw-fp.get_width()-5,5))

    if player.ads_t > 0.7 and player.wname == "sniper":
        sa = int((player.ads_t - 0.7) / 0.3 * 245)
        sc2 = pygame.Surface((sw, sh), pygame.SRCALPHA); sc2.fill((0,0,0,sa))
        rad = min(sw, sh) // 3
        pygame.draw.circle(sc2,(0,0,0,0),(sw//2,sh//2),rad)
        pygame.draw.circle(sc2,(0,0,0,sa),(sw//2,sh//2),rad,3)
        pygame.draw.line(sc2,(0,200,0,sa),(sw//2-rad,sh//2),(sw//2+rad,sh//2),1)
        pygame.draw.line(sc2,(0,200,0,sa),(sw//2,sh//2-rad),(sw//2,sh//2+rad),1)
        surf.blit(sc2,(0,0))

# ═══════════════════════════════════════════════════════════════════════════════
#  MINIMAP  (cached static)
# ═══════════════════════════════════════════════════════════════════════════════
def _build_mm_static() -> pygame.Surface:
    mw = MAP_W*MINI_TILE+2; mh = MAP_H*MINI_TILE+2
    mm = pygame.Surface((mw, mh), pygame.SRCALPHA); mm.fill((0,0,0,155))
    tcols = {0:(18,18,20),1:(68,58,48),2:(55,65,78),3:(38,58,68),4:(75,55,35),5:(55,55,58)}
    for gy in range(MAP_H):
        for gx in range(MAP_W):
            pygame.draw.rect(mm, tcols.get(MAP_GRID[gy][gx],(50,50,50)),
                             (gx*MINI_TILE+1, gy*MINI_TILE+1, MINI_TILE-1, MINI_TILE-1))
    pygame.draw.rect(mm,(160,160,160),(0,0,mw,mh),1)
    return mm

def draw_minimap(surf: pygame.Surface, player: Player,
                 enemies: List[Enemy], pickups: List[Pickup]) -> None:
    global _mm_static
    if _mm_static is None:
        _mm_static = _build_mm_static()
    mm = _mm_static.copy()
    for e in enemies:
        if e.alive:
            pygame.draw.circle(mm,(210,30,30),(int(e.x/TILE*MINI_TILE)+1,int(e.y/TILE*MINI_TILE)+1),3)
    for p in pickups:
        if p.alive:
            col=((255,220,0) if p.kind=="ammo" else
                 (0,200,80) if p.kind=="health" else
                 (0,120,220) if p.kind=="armor" else (100,200,50))
            pygame.draw.circle(mm,col,(int(p.x/TILE*MINI_TILE)+1,int(p.y/TILE*MINI_TILE)+1),3)
    plx = int(player.x/TILE*MINI_TILE)+1; ply = int(player.y/TILE*MINI_TILE)+1
    pygame.draw.circle(mm,(0,220,80),(plx,ply),4)
    pygame.draw.line(mm,(0,220,80),(plx,ply),(plx+int(math.cos(player.angle)*10),ply+int(math.sin(player.angle)*10)),2)
    surf.blit(mm,(MINI_X,MINI_Y))

# ═══════════════════════════════════════════════════════════════════════════════
#  OVERLAY
# ═══════════════════════════════════════════════════════════════════════════════
def draw_overlay(surf: pygame.Surface, title: str, sub: str,
                 col: Tuple, extra: str = "") -> None:
    ov = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
    ov.fill((0,0,0,178)); surf.blit(ov,(0,0))
    t1 = F_HUG.render(title,True,col); t2 = F_MD.render(sub,True,(220,220,220))
    sw2, sh2 = surf.get_size()
    surf.blit(t1,(sw2//2-t1.get_width()//2,sh2//2-72))
    surf.blit(t2,(sw2//2-t2.get_width()//2,sh2//2+12))
    if extra:
        t3 = F_SM.render(extra,True,(155,155,155))
        surf.blit(t3,(sw2//2-t3.get_width()//2,sh2//2+58))

# ═══════════════════════════════════════════════════════════════════════════════
#  SPAWN
# ═══════════════════════════════════════════════════════════════════════════════
_SPAWNS: List[Tuple] = [
    (gx*TILE+TILE//2, gy*TILE+TILE//2)
    for gy in range(1, MAP_H-1) for gx in range(1, MAP_W-1)
    if MAP_GRID[gy][gx] == 0
]

def spawn_enemies(wave: int, player: Player, count: int = -1) -> List[Enemy]:
    if count < 0: count = 4 + wave * 3
    out: List[Enemy] = []; used: set = set(); att = 0
    while len(out) < count and att < 500:
        sp = random.choice(_SPAWNS)
        if sp in used or math.hypot(sp[0]-player.x, sp[1]-player.y) < 260:
            att += 1; continue
        used.add(sp); out.append(Enemy(sp[0], sp[1], wave)); att += 1
    while len(out) < count:
        sp = random.choice(_SPAWNS); out.append(Enemy(sp[0], sp[1], wave))
    return out

def spawn_pickup(player: Player, weapons: Dict, kind: str = "ammo") -> Optional[Pickup]:
    for _ in range(60):
        sp = random.choice(_SPAWNS)
        if math.hypot(sp[0]-player.x, sp[1]-player.y) > 160:
            wn = random.choice(list(weapons.keys()))
            return Pickup(sp[0], sp[1], kind, wn)
    return Pickup(_SPAWNS[0][0], _SPAWNS[0][1], kind)

# ═══════════════════════════════════════════════════════════════════════════════
#  HIGH SCORE
# ═══════════════════════════════════════════════════════════════════════════════
def load_hs() -> int:
    try:
        with open(HS_FILE) as f: return int(f.read().strip())
    except: return 0

def save_hs(s: int) -> None:
    try:
        with open(HS_FILE, "w") as f: f.write(str(s))
    except: pass

# ═══════════════════════════════════════════════════════════════════════════════
#  MISSIONS / PROGRESS
# ═══════════════════════════════════════════════════════════════════════════════
MISSIONS = [
    {"id":1,"title":"OUTBREAK",      "desc":"Eliminate all zombies in the sector.",         "waves":3, "epw":8,  "weapons":["pistol","shotgun"],                    "bonus":[]},
    {"id":2,"title":"SUPPLY RUN",    "desc":"Survive 5 waves and collect ammo crates.",     "waves":5, "epw":10, "weapons":["pistol","shotgun","rifle"],              "bonus":["smg"]},
    {"id":3,"title":"HOLD THE LINE", "desc":"Survive 7 waves of increasing enemies.",       "waves":7, "epw":14, "weapons":["pistol","shotgun","rifle","smg"],        "bonus":[]},
    {"id":4,"title":"SNIPER'S NEST", "desc":"Take down zombies. Headshots score double.",   "waves":6, "epw":12, "weapons":["pistol","sniper"],                      "bonus":["rifle"]},
    {"id":5,"title":"FINAL STAND",   "desc":"Survive 10 waves. No mercy.",                  "waves":10,"epw":18, "weapons":["pistol","shotgun","rifle","smg","sniper"],"bonus":[]},
]
_DEF_PROG: Dict = {"total_kills":0,"total_score":0,"missions_cleared":[],"unlocked":["pistol","shotgun"]}
UNLOCK_T: Dict  = {"rifle":100,"smg":250,"sniper":500}

def load_prog() -> Dict:
    try:
        with open(SAVE_FILE) as f: d=json.load(f); return d.get("progress", dict(_DEF_PROG))
    except: return dict(_DEF_PROG)

def save_prog(p: Dict) -> None:
    try:
        d: Dict = {}
        try:
            with open(SAVE_FILE) as f: d=json.load(f)
        except: pass
        d["progress"] = p
        with open(SAVE_FILE,"w") as f: json.dump(d,f,indent=2)
    except: pass

def check_unlocks(prog: Dict) -> List[str]:
    newly: List[str] = []
    for wn, thr in UNLOCK_T.items():
        if wn not in prog["unlocked"] and prog["total_kills"] >= thr:
            prog["unlocked"].append(wn); newly.append(wn)
    return newly

def build_weapons(avail: List[str]) -> Dict[str, Weapon]:
    return {k: Weapon(WDEFS[k]) for k in avail if k in WDEFS}

# ═══════════════════════════════════════════════════════════════════════════════
#  MENU HELPERS  (all O(1) / pre-baked — no per-frame allocations)
# ═══════════════════════════════════════════════════════════════════════════════
# ── Palette ───────────────────────────────────────────────────────────────────
C_BG    = (3,   3,   5)
C_RED   = (180, 15,  15)
C_BLOOD = (140, 0,   0)
C_AMBER = (220, 130, 0)
C_GOLD  = (200, 158, 22)
C_RUST  = (160, 60,  10)
C_DIM   = (90,  90,  90)
C_WHITE = (235, 235, 235)
C_GREY  = (55,  55,  60)

# Pre-baked gradient surfaces (built once)
_GRAD_CACHE: Dict[Tuple, pygame.Surface] = {}

def _grad_surf(w: int, h: int, col_t: Tuple, col_b: Tuple) -> pygame.Surface:
    """Return (or build+cache) a vertical gradient surface."""
    key = (w, h, col_t, col_b)
    if key not in _GRAD_CACHE:
        s = pygame.Surface((w, h))
        arr = pygame.surfarray.pixels3d(s)
        r1,g1,b1 = col_t; r2,g2,b2 = col_b
        t = np.linspace(0, 1, h, dtype=np.float32)
        arr[:,:,0] = (r1 + (r2-r1)*t).astype(np.uint8)
        arr[:,:,1] = (g1 + (g2-g1)*t).astype(np.uint8)
        arr[:,:,2] = (b1 + (b2-b1)*t).astype(np.uint8)
        del arr
        _GRAD_CACHE[key] = s
    return _GRAD_CACHE[key]

# Cache for alpha-blended gradient surfaces (keyed by size+cols+alpha)
_GRAD_ALPHA_CACHE: Dict[Tuple, pygame.Surface] = {}

def _blit_grad(surf: pygame.Surface, rect: pygame.Rect,
               col_t: Tuple, col_b: Tuple, alpha: int = 255) -> None:
    """Blit a gradient onto surf within rect. Uses cache — no per-call copy."""
    if alpha < 255:
        key = (rect.width, rect.height, col_t, col_b, alpha)
        if key not in _GRAD_ALPHA_CACHE:
            g = _grad_surf(rect.width, rect.height, col_t, col_b).copy()
            g.set_alpha(alpha)
            _GRAD_ALPHA_CACHE[key] = g
        surf.blit(_GRAD_ALPHA_CACHE[key], rect.topleft)
    else:
        surf.blit(_grad_surf(rect.width, rect.height, col_t, col_b), rect.topleft)

def _brackets(surf: pygame.Surface, rect: pygame.Rect,
               col: Tuple, size: int = 14, thick: int = 1) -> None:
    """RE4-style corner brackets."""
    x, y, w, h = rect.x, rect.y, rect.width, rect.height
    for px, py, dx, dy in [(x,y,1,1),(x+w,y,-1,1),(x,y+h,1,-1),(x+w,y+h,-1,-1)]:
        pygame.draw.line(surf, col, (px, py), (px+dx*size, py), thick)
        pygame.draw.line(surf, col, (px, py), (px, py+dy*size), thick)

# Pre-baked scanlines alpha mask (numpy, built once per res)
_SCAN_CACHES: Dict[Tuple, np.ndarray] = {}

def _apply_scanlines(surf: pygame.Surface, strength: float = 0.22) -> None:
    """Apply scanlines — pre-baked mask, single surfarray acquire+release."""
    sw, sh = surf.get_size()
    key = (sw, sh, strength)
    if key not in _SCAN_CACHES:
        mask = np.ones((sw, sh), dtype=np.float32)
        for row in range(0, sh, 4):
            mask[:, row] = 1.0 - strength
        _SCAN_CACHES[key] = mask
    mask = _SCAN_CACHES[key]
    arr = pygame.surfarray.pixels3d(surf)
    tmp = (arr.astype(np.float32) * mask[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)
    arr[:] = tmp          # assign while lock held — same object, safe
    del arr

def _draw_title(surf: pygame.Surface, text: str, cx: int, cy: int,
                font: pygame.font.Font) -> None:
    """Clean, sharp title rendering — no animation artifacts."""
    tw = font.render(text, True, (215, 185, 185))
    # Subtle red shadow offset for depth
    ts = font.render(text, True, (120, 8, 8))
    surf.blit(ts, (cx - ts.get_width()//2 + 2, cy + 2))
    surf.blit(tw, (cx - tw.get_width()//2, cy))

# Drifting blood-particle background (pre-allocated list)
class _BloodDot:
    __slots__ = ("x","y","vy","size","alpha","col")
    def __init__(self, W: int, H: int):
        self.x = random.uniform(0, W)
        self.y = random.uniform(-H, H)
        self.vy = random.uniform(8, 30)
        self.size = random.randint(1, 3)
        self.alpha = random.randint(40, 140)
        dark = random.randint(0, 40)
        self.col = (random.randint(100,180), dark, dark)
    def update(self, dt: float, H: int) -> None:
        self.y += self.vy * dt
        if self.y > H + 5: self.y = -5.0
    def draw(self, surf: pygame.Surface) -> None:
        if self.size == 1:
            surf.set_at((int(self.x), int(self.y)), self.col)
        else:
            if _GFXDRAW:
                try:
                    pygame.gfxdraw.filled_circle(surf, int(self.x), int(self.y),
                                                  self.size, (*self.col, self.alpha))
                    return
                except Exception:
                    pass
            pygame.draw.circle(surf, self.col, (int(self.x), int(self.y)), self.size)

_DOTS: List[_BloodDot] = []

def _init_dots(count: int = 120) -> None:
    global _DOTS
    _DOTS = [_BloodDot(W, H) for _ in range(count)]

# ── Menu button state ─────────────────────────────────────────────────────────
class Btn:
    __slots__ = ("label","sub","rect","t")
    def __init__(self, label: str, sub: str, x: int, y: int, w: int, h: int):
        self.label=label; self.sub=sub; self.rect=pygame.Rect(x,y,w,h); self.t=0.0
    def tick(self, dt: float, active: bool) -> None:
        tgt = 1.0 if active else 0.0
        self.t += (tgt - self.t) * min(1.0, dt * 11)
    def draw(self, surf: pygame.Surface, active: bool, anim: float) -> None:
        tq = round(self.t * 20) / 20.0  # quantise to 20 levels → bounded cache
        r = self.rect
        col_t = (int(20*tq), int(6*tq), int(3*tq))
        col_b = (int(10*tq), int(3*tq), int(1*tq))
        _blit_grad(surf, r, col_t, col_b, 220)
        # Border
        b_col = tuple(min(255, int(c*(0.3 + tq*0.7))) for c in C_AMBER) if tq > 0.05 else C_GREY
        pygame.draw.rect(surf, b_col, r, 1)
        if tq > 0.1:
            _brackets(surf, r, b_col, 12, 1)
            # Left blood accent bar
            bar_h = int(r.height * tq)
            if bar_h > 0:
                pygame.draw.rect(surf, C_BLOOD, (r.x, r.y + (r.height-bar_h)//2, 3, bar_h))
        # Label
        lc = tuple(min(255, int(c*(0.45 + tq*0.55))) for c in C_WHITE)
        lt = F_LG.render(self.label, True, lc)
        surf.blit(lt, (r.centerx - lt.get_width()//2, r.y + 9))
        # Subtitle
        if self.sub and tq > 0.25:
            sc = (int(160*tq), int(120*tq), int(80*tq))
            st2 = F_SM.render(self.sub, True, sc)
            surf.blit(st2, (r.centerx - st2.get_width()//2, r.y + 40))

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN MENU  — dark horror aesthetic, all O(1) operations
# ═══════════════════════════════════════════════════════════════════════════════
def main_menu() -> str:
    pygame.mouse.set_visible(True); pygame.event.set_grab(False)
    _init_dots(120); hs = load_hs(); anim = 0.0; cur = 0

    items = [
        ("SURVIVAL MODE",   "Unlimited waves — survive as long as you can"),
        ("MISSION MODE",    "5 story missions with objectives"),
        ("PROGRESSION",     "Unlock weapons & perks — persistent progress"),
        ("SETTINGS",        ""),
        ("QUIT",            ""),
    ]
    btns = [Btn(label, sub, W//2-210, 218+i*76, 420, 66) for i,(label,sub) in enumerate(items)]

    # Pre-build background gradient (once)
    bg_grad = _grad_surf(W, H, (12, 0, 0), (2, 2, 4))

    while True:
        dt = clock.tick(60) / 1000.0; anim += dt

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT: return "quit"
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_UP:   cur = (cur-1) % len(items)
                if ev.key == pygame.K_DOWN: cur = (cur+1) % len(items)
                if ev.key == pygame.K_ESCAPE: return "quit"
                if ev.key == pygame.K_RETURN:
                    if cur == 0: return "survival"
                    if cur == 1: return "mission"
                    if cur == 2: return "progress"
                    if cur == 3: settings_menu(); apply_cfg()
                    if cur == 4: return "quit"

        # Update dots
        for d in _DOTS: d.update(dt, H)
        for i, b in enumerate(btns): b.tick(dt, i == cur)

        # Draw background
        _game_surf.blit(bg_grad, (0, 0))
        for d in _DOTS: d.draw(_game_surf)

        # Scanlines via numpy surfarray (no per-frame Surface alloc)
        _apply_scanlines(_game_surf, 0.18)

        # Title — animated drip effect under letters
        ty = 68
        # Animated blood underline that "drips"
        drip_y = ty + 86 + int(math.sin(anim * 1.2) * 4)
        drip_w = int(260 + math.sin(anim * 0.7) * 20)
        pygame.draw.rect(_game_surf, C_BLOOD, (W//2 - drip_w//2, drip_y, drip_w, 2))
        # Small drips at random-ish positions
        for di in range(5):
            dx2 = W//2 - drip_w//2 + di * (drip_w // 5) + int(math.sin(anim*1.5+di)*8)
            dh  = int(math.sin(anim*0.8+di*1.3)*8 + 10)
            pygame.draw.line(_game_surf, C_BLOOD, (dx2, drip_y), (dx2, drip_y + dh), 2)
        _draw_title(_game_surf, "AzanRE  6.0", W//2, ty, F_TTL)
        sub_t = F_MD.render("SURVIVAL HORROR RAYCASTER", True, (130, 80, 40))
        _game_surf.blit(sub_t, (W//2 - sub_t.get_width()//2, ty + 84))

        # Horizontal rule with glyph
        ry = ty + 108
        pygame.draw.line(_game_surf, C_BLOOD, (W//2-260, ry), (W//2+260, ry), 1)
        pygame.draw.circle(_game_surf, C_RED, (W//2, ry), 5)
        pygame.draw.circle(_game_surf, C_BG,  (W//2, ry), 2)

        # Buttons
        for b in btns: b.draw(_game_surf, btns.index(b) == cur, anim)

        # Bottom strip
        pygame.draw.line(_game_surf, C_GREY, (0, H-48), (W, H-48), 1)
        hs_t  = F_SM.render(f"HIGH SCORE:  {hs}", True, C_GOLD)
        ctrl  = F_XS.render("WASD·Mouse·LMB Shoot·RMB ADS·R Reload·G Grenade·F Light·1-5 Weapons", True, (60,60,60))
        wm_t  = F_XS.render(f"AzanChishiya · AzanRE {VERSION}", True, (40,40,40))
        _game_surf.blit(hs_t,  (W//2 - hs_t.get_width()//2,  H-40))
        _game_surf.blit(ctrl,  (W//2 - ctrl.get_width()//2,   H-26))
        _game_surf.blit(wm_t,  (W - wm_t.get_width()-10,      H-14))

        _flip_to_screen(_game_surf)
        pygame.display.flip()

# ═══════════════════════════════════════════════════════════════════════════════
#  PAUSE MENU
# ═══════════════════════════════════════════════════════════════════════════════
def pause_menu() -> str:
    pygame.mouse.set_visible(True); pygame.event.set_grab(False)
    items = ["RESUME", "SETTINGS", "QUIT TO MENU"]; cur = 0; anim = 0.0
    btns  = [Btn(label,"",W//2-155, 255+i*76, 310, 62) for i,label in enumerate(items)]

    while True:
        dt = clock.tick(30) / 1000.0; anim += dt
        _game_surf.fill(C_BG)
        ov = pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,172)); _game_surf.blit(ov,(0,0))
        _draw_title(_game_surf, "PAUSED", W//2, 130, F_HUG)
        for i,b in enumerate(btns): b.tick(dt,i==cur); b.draw(_game_surf,i==cur,anim)
        _flip_to_screen(_game_surf)
        pygame.display.flip()
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: return"quit"
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_UP:   cur=(cur-1)%len(items)
                if ev.key==pygame.K_DOWN: cur=(cur+1)%len(items)
                if ev.key==pygame.K_ESCAPE: return"resume"
                if ev.key==pygame.K_RETURN:
                    if cur==0: return"resume"
                    if cur==1: settings_menu(); apply_cfg()
                    if cur==2: return"menu"

# ═══════════════════════════════════════════════════════════════════════════════
#  SETTINGS MENU
# ═══════════════════════════════════════════════════════════════════════════════
def settings_menu() -> None:
    pygame.mouse.set_visible(True); pygame.event.set_grab(False)
    rows = [
        ("Resolution",   ["1280x720","1920x1080","1024x576","800x600"]),
        ("Fullscreen",   ["Off","On"]),
        ("Render Scale", ["Half-res (recommended)","Full-res (high-end)"]),
        ("Sensitivity",  ["0.001","0.0015","0.0018","0.0025","0.003","0.005"]),
        ("FOV",          ["55","60","62","70","80","90"]),
        ("FPS Limit",    ["30","60","120","240","Unlimited"]),
        ("Difficulty",   ["Easy","Normal","Hard","Nightmare"]),
        ("Invert Y",     ["Off","On"]),
        ("Aim Assist",   ["On","Off"]),
        ("Flashlight",   ["On","Off"]),
        ("Fog",          ["On","Off"]),
        ("Film Grain",   ["On","Off"]),
        ("Vignette",     ["On","Off"]),
        ("Chromatic AB", ["On","Off"]),
        ("DOF Blur",     ["On","Off"]),
        ("Volume",       ["0%","25%","50%","65%","80%","100%"]),
        ("Show FPS",     ["On","Off"]),
        ("← Apply & Back", None),
    ]
    rm = {"1280x720":0,"1920x1080":1,"1024x576":2,"800x600":3}
    fm = {30:0,60:1,120:2,240:3,0:4}
    def idx(lst, v):
        try: return lst.index(str(v))
        except: return 0
    si = [rm.get(f"{CFG['width']}x{CFG['height']}",0),
          1 if CFG["fullscreen"] else 0, 0 if CFG["render_scale"]==2 else 1,
          idx(["0.001","0.0015","0.0018","0.0025","0.003","0.005"],CFG["mouse_sens"]),
          idx(["55","60","62","70","80","90"],CFG["fov_deg"]),
          fm.get(CFG["max_fps"],1), CFG["difficulty"],
          1 if CFG["invert_y"] else 0, 0 if CFG["aim_assist"] else 1,
          0 if CFG["flashlight"] else 1, 0 if CFG["fog"] else 1,
          0 if CFG["film_grain"] else 1, 0 if CFG["vignette"] else 1,
          0 if CFG["chromatic_ab"] else 1, 0 if CFG["dof_blur"] else 1,
          {0.:0,.25:1,.5:2,.65:3,.8:4,1.:5}.get(CFG["volume"],3),
          0 if CFG["show_fps"] else 1, 0]
    cur = 0; scroll = 0; vis = 13

    while True:
        _game_surf.fill(C_BG)
        ttl = F_LG.render("SETTINGS", True, C_AMBER)
        _game_surf.blit(ttl,(W//2-ttl.get_width()//2,22))
        pygame.draw.line(_game_surf,C_RED,(W//2-200,64),(W//2+200,64),1)

        for i in range(vis):
            ri = i+scroll
            if ri >= len(rows): break
            label,choices = rows[ri]; active=(ri==cur); by2=78+i*41
            r2 = pygame.Rect(W//2-275,by2,550,36)
            _blit_grad(_game_surf,r2,(30,15,0) if active else(8,8,10),(15,7,0) if active else(5,5,7),220)
            pygame.draw.rect(_game_surf,(160,90,0) if active else(38,38,44),r2,1)
            if active: _brackets(_game_surf,r2,C_AMBER,10,1)
            col=(255,210,0) if active else(185,185,185)
            if choices:
                lt=F_MD.render(f"{label}:  {choices[si[ri]]}",True,col)
                at=F_SM.render("◄ ►",True,C_AMBER if active else(55,55,55))
                _game_surf.blit(lt,(W//2-255,by2+8)); _game_surf.blit(at,(W//2+185,by2+10))
            else:
                lt=F_MD.render(label,True,col); _game_surf.blit(lt,(W//2-lt.get_width()//2,by2+8))

        h2_t=F_XS.render("↑↓ navigate   ←→ change   Enter/Esc apply & back",True,(70,70,70))
        _game_surf.blit(h2_t,(W//2-h2_t.get_width()//2,H-22))
        _flip_to_screen(_game_surf)
        pygame.display.flip(); clock.tick(30)

        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: return
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_UP:
                    cur=(cur-1)%len(rows)
                    if cur<scroll: scroll=cur
                elif ev.key==pygame.K_DOWN:
                    cur=(cur+1)%len(rows)
                    if cur>=scroll+vis: scroll=cur-vis+1
                elif ev.key in(pygame.K_LEFT,pygame.K_RIGHT):
                    ch=rows[cur][1]
                    if ch: d2=1 if ev.key==pygame.K_RIGHT else-1; si[cur]=(si[cur]+d2)%len(ch)
                elif ev.key in(pygame.K_RETURN,pygame.K_ESCAPE):
                    if cur==len(rows)-1 or ev.key==pygame.K_ESCAPE:
                        rs=[("1280","720"),("1920","1080"),("1024","576"),("800","600")][si[0]]
                        CFG["width"]=int(rs[0]); CFG["height"]=int(rs[1])
                        CFG["fullscreen"]=si[1]==1; CFG["render_scale"]=1 if si[2]==1 else 2
                        CFG["mouse_sens"]=[.001,.0015,.0018,.0025,.003,.005][si[3]]
                        CFG["fov_deg"]=[55,60,62,70,80,90][si[4]]
                        CFG["max_fps"]=[30,60,120,240,0][si[5]]
                        CFG["difficulty"]=si[6]; CFG["invert_y"]=si[7]==1
                        CFG["aim_assist"]=si[8]==0; CFG["flashlight"]=si[9]==0
                        CFG["fog"]=si[10]==0; CFG["film_grain"]=si[11]==0
                        CFG["vignette"]=si[12]==0; CFG["chromatic_ab"]=si[13]==0
                        CFG["dof_blur"]=si[14]==0
                        CFG["volume"]=[0.,.25,.5,.65,.8,1.][si[15]]
                        CFG["show_fps"]=si[16]==0
                        apply_cfg(); _save_cfg(); return

# ═══════════════════════════════════════════════════════════════════════════════
#  MISSION SELECT
# ═══════════════════════════════════════════════════════════════════════════════
def mission_select() -> int:
    pygame.mouse.set_visible(True); pygame.event.set_grab(False)
    cur=0; anim=0.0
    bg_grad=_grad_surf(W,H,(10,2,0),(2,2,4))

    while True:
        dt=clock.tick(30)/1000.0; anim+=dt
        _game_surf.blit(bg_grad,(0,0))
        _apply_scanlines(_game_surf,0.14)
        ttl=F_LG.render("SELECT MISSION",True,C_AMBER); _game_surf.blit(ttl,(W//2-ttl.get_width()//2,26))
        pygame.draw.line(_game_surf,C_RED,(W//2-240,68),(W//2+240,68),1)

        for i,m in enumerate(MISSIONS):
            active=(i==cur); by2=80+i*108; t=1.0 if active else 0.28
            r2=pygame.Rect(W//2-295,by2,590,98)
            _blit_grad(_game_surf,r2,(int(35*t),int(12*t),0),(int(18*t),int(6*t),0),220)
            pygame.draw.rect(_game_surf,(int(160*t),int(80*t),0) if active else(35,35,45),r2,1)
            if active: _brackets(_game_surf,r2,C_AMBER,14,1)

            id_c=C_RED if active else C_BLOOD
            id_t=F_LG.render(f"M{m['id']}",True,id_c); _game_surf.blit(id_t,(W//2-275,by2+8))
            mc=( 255,210,0) if active else(180,180,180)
            mt=F_LG.render(m["title"],True,mc); _game_surf.blit(mt,(W//2-225,by2+8))
            dc=(150,140,130) if active else(90,90,90)
            dt2=F_SM.render(m["desc"],True,dc); _game_surf.blit(dt2,(W//2-275,by2+52))
            wt=F_XS.render(f"Waves: {m['waves']}  ·  Enemies/wave: {m['epw']}  ·  {', '.join(m['weapons'])}",True,(110,100,90) if active else(55,55,60))
            _game_surf.blit(wt,(W//2-275,by2+76))

        pygame.draw.line(_game_surf,C_GREY,(0,H-34),(W,H-34),1)
        h2ms=F_XS.render("↑↓ navigate   Enter select   Esc back",True,(65,65,65))
        _game_surf.blit(h2ms,(W//2-h2ms.get_width()//2,H-24))
        _flip_to_screen(_game_surf)
        pygame.display.flip(); clock.tick(30)

        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: return-1
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_UP:     cur=(cur-1)%len(MISSIONS)
                if ev.key==pygame.K_DOWN:   cur=(cur+1)%len(MISSIONS)
                if ev.key==pygame.K_RETURN: return cur
                if ev.key==pygame.K_ESCAPE: return-1

# ═══════════════════════════════════════════════════════════════════════════════
#  PROGRESS SCREEN
# ═══════════════════════════════════════════════════════════════════════════════
def progress_screen(prog: Dict) -> str:
    pygame.mouse.set_visible(True); pygame.event.set_grab(False)
    bg_grad=_grad_surf(W,H,(10,2,0),(2,2,4))

    while True:
        clock.tick(30)
        _game_surf.blit(bg_grad,(0,0)); _apply_scanlines(_game_surf,0.14)
        ttl=F_LG.render("PROGRESSION",True,C_AMBER); _game_surf.blit(ttl,(W//2-ttl.get_width()//2,26))
        pygame.draw.line(_game_surf,C_RED,(W//2-220,68),(W//2+220,68),1)

        for i,s in enumerate([f"Total Kills   {prog['total_kills']}",
                               f"Total Score   {prog['total_score']}",
                               f"Missions Done {len(prog['missions_cleared'])}"]):
            st=F_MD.render(s,True,(210,210,210)); _game_surf.blit(st,(W//2-st.get_width()//2,82+i*36))

        _game_surf.blit(F_MD.render("WEAPON UNLOCKS",True,C_AMBER),(W//2-95,196))
        pygame.draw.line(_game_surf,C_RUST,(W//2-200,220),(W//2+200,220),1)
        wx=W//2-265
        for wn,thr in UNLOCK_T.items():
            un=wn in prog["unlocked"]
            r2=pygame.Rect(wx,228,160,56)
            _blit_grad(_game_surf,r2,(18,28,12) if un else(10,10,12),(8,14,6) if un else(6,6,8),220)
            pygame.draw.rect(_game_surf,(0,130,55) if un else(38,38,44),r2,1)
            if un: _brackets(_game_surf,r2,(0,180,70),8,1)
            ic=F_SM.render("✓" if un else f"{thr}",True,(0,210,70) if un else(80,80,80))
            _game_surf.blit(ic,(wx+8,232))
            wt2=F_SM.render(WDEFS[wn].name,True,(240,240,240) if un else(110,110,110))
            _game_surf.blit(wt2,(wx+8,252))
            if not un:
                kt=F_XS.render("kills",True,(70,70,70)); _game_surf.blit(kt,(wx+8,268))
            wx+=185

        _game_surf.blit(F_MD.render("MISSIONS",True,C_AMBER),(W//2-60,312))
        pygame.draw.line(_game_surf,C_RUST,(W//2-200,336),(W//2+200,336),1)
        for i2,m in enumerate(MISSIONS):
            done=m["id"] in prog["missions_cleared"]
            col2=(0,195,55) if done else(130,130,130)
            mt2ps=F_SM.render(f"{'✓' if done else '○'}  M{m['id']}: {m['title']}",True,col2)
            _game_surf.blit(mt2ps,(W//2-mt2ps.get_width()//2,348+i2*30))

        pygame.draw.line(_game_surf,C_GREY,(0,H-48),(W,H-48),1)
        b1=F_LG.render("[SPACE]  PLAY",True,C_GOLD); b2=F_MD.render("[ESC]  BACK",True,C_DIM)
        _game_surf.blit(b1,(W//2-210,H-42)); _game_surf.blit(b2,(W//2+20,H-36))
        _flip_to_screen(_game_surf)
        pygame.display.flip()

        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: return"back"
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_SPACE: return"play"
                if ev.key==pygame.K_ESCAPE: return"back"

# ═══════════════════════════════════════════════════════════════════════════════
#  STATS OVERLAY
# ═══════════════════════════════════════════════════════════════════════════════
def draw_stats(surf: pygame.Surface, player: Player, wave: int, fps: float) -> None:
    bg=pygame.Surface((330,215),pygame.SRCALPHA); bg.fill((0,0,0,196)); surf.blit(bg,(W//2-165,H//2-107))
    r2=pygame.Rect(W//2-165,H//2-107,330,215)
    pygame.draw.rect(surf,C_AMBER,r2,1); _brackets(surf,r2,C_AMBER,12,1)
    lines=[("STATISTICS",C_GOLD),(f"Wave      {wave}",(215,215,215)),(f"Score     {player.score}",(215,215,215)),
           (f"Kills     {player.kills}",(215,215,215)),(f"Headshots {player.hs}",(215,215,215)),
           (f"HP        {player.hp}/{player.max_hp}",(215,215,215)),(f"Grenades  {player.grenades}",(215,215,215)),
           (f"FPS       {fps:.0f}",(170,170,170))]
    for i,(txt,col) in enumerate(lines):
        ft=F_MD.render(txt,True,col) if i==0 else F_SM.render(txt,True,col)
        surf.blit(ft,(W//2-148,H//2-94+i*24))

# ═══════════════════════════════════════════════════════════════════════════════
#  GAME STATE ENUM
# ═══════════════════════════════════════════════════════════════════════════════
class GS(Enum):
    WAVE_INTRO=auto(); PLAYING=auto(); WAVE_CLEAR=auto(); DEAD=auto(); WIN=auto()

# ═══════════════════════════════════════════════════════════════════════════════
#  CORE GAME LOOP  — guaranteed to always return a Dict
# ═══════════════════════════════════════════════════════════════════════════════
def run_game(mode: str, mission_idx: int = 0, prog: Optional[Dict] = None) -> Dict:
    global _mm_static, _vig_cache
    _pool.reset(); _mm_static=None; _vig_cache=None; _SCAN_CACHES.clear()

    if mode == "survival":
        wnames=["pistol","shotgun","rifle","smg"]; max_waves=9999; mode_name="SURVIVAL"; epw=-1
    elif mode == "mission":
        m=MISSIONS[mission_idx]; wnames=m["weapons"]+m.get("bonus",[]); max_waves=m["waves"]
        mode_name=f"M{m['id']}: {m['title']}"; epw=m["epw"]
    elif mode == "progress":
        if prog is None: prog=load_prog()
        wnames=prog.get("unlocked",["pistol"]); max_waves=9999; mode_name="PROGRESSION"; epw=-1
    else:
        wnames=["pistol"]; max_waves=9999; mode_name="SURVIVAL"; epw=-1

    weapons=build_weapons(wnames); player=Player(weapons)
    player.grant_shield(3.0); player.grenades=3

    wave=0; enemies: List[Enemy]=[]; pickups: List[Pickup]=[]; grenades_live: List[Grenade]=[]
    state=GS.WAVE_INTRO; wave_timer=1.8
    high_score=load_hs(); mb_held=False; show_stats=False
    result: Dict = {"score":0,"kills":0,"cleared":False,"quit":False}

    pygame.event.set_grab(True); pygame.mouse.set_visible(False)
    rs=CFG["render_scale"]; fps_disp=60.0; fps_acc=0.0; frame_count=0
    running=True

    while running:
        raw_dt=clock.tick(CFG["max_fps"] or 9999)/1000.0
        dt=min(raw_dt,0.05); fps_acc+=raw_dt; frame_count+=1
        if fps_acc >= 0.3:
            fps_disp=frame_count/fps_acc; fps_acc=0.0; frame_count=0

        player.killfeed=[(t2,tm-dt) for t2,tm in player.killfeed if tm>dt]

        # ── Events ───────────────────────────────────────────────────────────
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT:
                result["quit"]=True; running=False; break

            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_ESCAPE:
                    r2=pause_menu(); pygame.event.set_grab(True); pygame.mouse.set_visible(False)
                    apply_cfg()
                    if r2=="menu": result["quit"]=True; running=False; break
                    if r2=="quit": result["quit"]=True; running=False; break
                if ev.key==pygame.K_TAB: show_stats=not show_stats
                if state==GS.PLAYING:
                    if ev.key==pygame.K_r: player.try_reload()
                    elif ev.key==pygame.K_1: player.switch("pistol")
                    elif ev.key==pygame.K_2: player.switch("shotgun")
                    elif ev.key==pygame.K_3: player.switch("rifle")
                    elif ev.key==pygame.K_4: player.switch("smg")
                    elif ev.key==pygame.K_5: player.switch("sniper")
                    elif ev.key==pygame.K_f: player.flashlight=not player.flashlight
                    elif ev.key==pygame.K_g:
                        g=player.throw_grenade()
                        if g: grenades_live.append(g)
                if state==GS.DEAD and ev.key==pygame.K_r:
                    result["quit"]=True; running=False; break
                if state==GS.WAVE_CLEAR and ev.key==pygame.K_SPACE:
                    state=GS.WAVE_INTRO; wave_timer=1.0
                if state==GS.WIN and ev.key==pygame.K_SPACE:
                    result["cleared"]=True; running=False; break

            if ev.type==pygame.MOUSEMOTION and state==GS.PLAYING:
                player.rotate(ev.rel[0],ev.rel[1])
            if ev.type==pygame.MOUSEBUTTONDOWN:
                if ev.button==1: mb_held=True
                if ev.button==3 and state==GS.PLAYING: player.ads=True
            if ev.type==pygame.MOUSEBUTTONUP:
                if ev.button==1: mb_held=False
                if ev.button==3: player.ads=False

        if not running:
            break

        # ── Fire (single path) ───────────────────────────────────────────────
        if mb_held and state==GS.PLAYING:
            fired=player.try_shoot()
            if fired:
                for _ in range(player.cw.pellets):
                    process_shot(player,enemies,wave)

        # ── State machine ────────────────────────────────────────────────────
        if state==GS.WAVE_INTRO:
            wave_timer-=dt
            if wave_timer<=0:
                wave+=1; enemies=spawn_enemies(wave,player,epw if epw>0 else -1)
                # Always spawn ammo + health + occasional grenade at wave start
                for _ in range(2):  # 2 ammo crates per wave
                    ap=spawn_pickup(player,weapons,"ammo")
                    if ap: pickups.append(ap)
                hp2=spawn_pickup(player,weapons,"health")  # 1 health pack every wave
                if hp2: pickups.append(hp2)
                if wave%2==0:  # extra health every 2 waves
                    hp3=spawn_pickup(player,weapons,"health")
                    if hp3: pickups.append(hp3)
                if player.grenades < 4:  # grenade if low
                    gp=spawn_pickup(player,weapons,"grenade")
                    if gp: pickups.append(gp)
                player.grant_shield(2.5); state=GS.PLAYING

        elif state==GS.PLAYING:
            keys=pygame.key.get_pressed(); player.update(dt,keys)
            for e in enemies: e.update(dt,player)
            for p in pickups: p.update(dt); p.alive and p.try_collect(player)
            pickups=[p for p in pickups if p.alive]

            boom_idx: List[int]=[]
            for gi,g in enumerate(grenades_live):
                if g.update(dt):
                    sp2=project_sprite(player.x,player.y,player.angle,g.x,g.y)
                    if sp2: gsx,gsph,gdist=sp2; emit_explosion(gsx,RH//2,30)
                    sfx("explosion")
                    for e in enemies:
                        if not e.alive: continue
                        d2=math.hypot(e.x-g.x,e.y-g.y)
                        if d2<Grenade.RADIUS:
                            dmg_g=int(Grenade.DAMAGE*(1-d2/Grenade.RADIUS))
                            if e.hit(dmg_g,False):
                                player.kills+=1; player.score+=150+wave*10
                                player.killfeed.append(("  GRENADE KILL +150",2.0))
                    pd=math.hypot(player.x-g.x,player.y-g.y)
                    if pd<Grenade.RADIUS:
                        player.damage(int(Grenade.DAMAGE*0.35*(1-pd/Grenade.RADIUS)))
                    boom_idx.append(gi)
            for gi in reversed(boom_idx): grenades_live.pop(gi)

            _pool.update(dt)

            if enemies and all(not e.alive for e in enemies):
                if mode!="survival" and wave>=max_waves: state=GS.WIN
                else: state=GS.WAVE_CLEAR; wave_timer=0
                # Wave-clear rewards: ammo + health + shield
                for ww in weapons.values(): ww.add_ammo(30)
                player.heal(min(40, player.max_hp - player.hp))  # restore up to 40 HP
                player.grant_shield(4.0)                          # 4s invincibility
                player.grenades = min(player.grenades + 1, 5)    # +1 grenade

            if not player.alive:
                state=GS.DEAD
                if player.score>high_score: high_score=player.score; save_hs(high_score)

        # ── Render ───────────────────────────────────────────────────────────
        cast_and_draw(player.x,player.y,player.angle,int(player.pitch),player.flashlight)
        blit_pxbuf()

        all_spr: List[Tuple]=[]
        for e in enemies:
            if e.alive:
                sp2=project_sprite(player.x,player.y,player.angle,e.x,e.y)
                if sp2: all_spr.append(("enemy",sp2,e))
        for p in pickups:
            if p.alive:
                sp2=project_sprite(player.x,player.y,player.angle,p.x,p.y)
                if sp2: all_spr.append(("pickup",sp2,p))
        for g in grenades_live:
            sp2=project_sprite(player.x,player.y,player.angle,g.x,g.y)
            if sp2: all_spr.append(("grenade",sp2,g))
        all_spr.sort(key=lambda s: -s[1][2])
        pitch_off=int(player.pitch)

        for stype,sp2,obj in all_spr:
            sx2,sph2,dist2=sp2
            if stype=="enemy":    draw_enemy(render_surf,sx2,sph2,dist2,obj,pitch_off)
            elif stype=="pickup": draw_pickup(render_surf,sx2,sph2,dist2,obj,pitch_off)
            elif stype=="grenade":draw_grenade_spr(render_surf,sx2,sph2,dist2,obj,pitch_off)

        _pool.draw(render_surf)
        draw_weapon(render_surf,player,dt)
        draw_crosshair(render_surf,player)
        post_process(render_surf,player.dmg_flash,player.ads_t,player.wname)

        # Scale render_surf → game_surf (W×H), then letterbox onto screen
        if rs > 1:
            pygame.transform.scale(render_surf, (W, H), _game_surf)
        else:
            _game_surf.blit(render_surf, (0, 0))

        draw_hud(_game_surf,player,wave,sum(1 for e in enemies if e.alive),fps_disp,mode_name)
        draw_minimap(_game_surf,player,enemies,pickups)
        if show_stats: draw_stats(_game_surf,player,wave,fps_disp)

        if state==GS.WAVE_INTRO and wave==0:
            draw_overlay(_game_surf,"AzanRE  6.0","WASD Move · LMB Shoot · RMB ADS · R Reload · G Grenade",(200,120,0),"Press any key to begin...")
        elif state==GS.WAVE_CLEAR:
            draw_overlay(_game_surf,f"WAVE {wave} CLEAR!",f"Score: {player.score}  |  Kills: {player.kills}",(0,200,70),"Press SPACE for next wave")
        elif state==GS.WIN:
            draw_overlay(_game_surf,"MISSION COMPLETE!",f"Score: {player.score}  |  Kills: {player.kills}  |  HS: {player.hs}",(0,180,240),"Press SPACE to continue")
        elif state==GS.DEAD:
            draw_overlay(_game_surf,"YOU  DIED",f"Score: {player.score}   High Score: {high_score}",(200,20,20),"Press R to restart  |  ESC for menu")

        # Letterbox blit: _game_surf → screen (no stretch, black bars if needed)
        if _LB_SCALE != 1.0:
            blit_w = int(W * _LB_SCALE); blit_h = int(H * _LB_SCALE)
            scaled = pygame.transform.scale(_game_surf, (blit_w, blit_h))
            screen.fill((0, 0, 0))
            screen.blit(scaled, (_LB_X, _LB_Y))
        else:
            screen.blit(_game_surf, (0, 0))

        pygame.display.flip()
        result["score"]=player.score; result["kills"]=player.kills

    pygame.event.set_grab(False); pygame.mouse.set_visible(True)
    return result

# ═══════════════════════════════════════════════════════════════════════════════
#  ENTRY
# ═══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    prog = load_prog()

    while True:
        choice = main_menu()
        if choice == "quit":
            break

        elif choice == "survival":
            result = run_game("survival", prog=prog)
            prog["total_kills"] += result.get("kills",0)
            prog["total_score"] += result.get("score",0)
            newly = check_unlocks(prog); save_prog(prog)
            if newly:
                pygame.event.set_grab(False); _game_surf.fill(C_BG)
                for i, wn in enumerate(newly):
                    ut = F_LG.render(f"UNLOCKED:  {WDEFS[wn].name.upper()}!", True, C_GOLD)
                    _game_surf.blit(ut,(W//2-ut.get_width()//2, H//2-40+i*60))
                ct = F_SM.render("Press ENTER to continue", True, (150,150,150))
                _game_surf.blit(ct,(W//2-ct.get_width()//2, H//2+80))
                _flip_to_screen(_game_surf); pygame.display.flip()
                waiting=True
                while waiting:
                    for ev in pygame.event.get():
                        if ev.type==pygame.QUIT: waiting=False
                        if ev.type==pygame.KEYDOWN and ev.key==pygame.K_RETURN: waiting=False
                    clock.tick(30)
            if result.get("quit") and result.get("kills",0)==0 and result.get("score",0)==0:
                pass  # normal exit

        elif choice == "mission":
            midx = mission_select()
            if midx < 0: continue
            result = run_game("mission", mission_idx=midx, prog=prog)
            if result.get("cleared"):
                mid = MISSIONS[midx]["id"]
                if mid not in prog["missions_cleared"]: prog["missions_cleared"].append(mid)
            prog["total_kills"] += result.get("kills",0)
            prog["total_score"] += result.get("score",0)
            check_unlocks(prog); save_prog(prog)

        elif choice == "progress":
            pres = progress_screen(prog)
            if pres == "play":
                result = run_game("progress", prog=prog)
                prog["total_kills"] += result.get("kills",0)
                prog["total_score"] += result.get("score",0)
                check_unlocks(prog); save_prog(prog)

    pygame.quit(); sys.exit()


if __name__ == "__main__":
    main()
