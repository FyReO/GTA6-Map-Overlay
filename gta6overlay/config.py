import math

APP_NAME = "GTA 6 Map Overlay"
APP_DIR_NAME = "GTA6MapOverlay"
EXE_NAME = "GTA6MapOverlay.exe"
DATA_ASSET = "data-pack.zip"
GITHUB_REPO = "FyReO/GTA6-Map-Overlay"
YOUTUBE_URL = "https://www.youtube.com/@fyreo"
DONATE_URL = "https://www.paypal.com/paypalme/fyreoyt"
API_BASE = "https://api.github.com"
ALLOWED_HOSTS = ("github.com", "githubusercontent.com")

PROC_WIDTH = 1280        # width used by the slow background matcher
REF_TILE = 2400          # reference images are scanned at FULL resolution in tiles this big
REF_TILE_OVERLAP = 200   # tile overlap (px) so nothing on a tile border is missed
REF_TILE_FEATURES = 5000 # SIFT features kept per tile
ALIGN_MODEL = "similarity"   # how the map is fitted to the screen: "similarity" (scale + shift, steadiest),
                             # "affine" or "homography" (try these if similarity ever looks stretched)
ALIGN_THRESH = 3.0       # max error (px) for a feature match to count as agreeing with the fit
REFINE_MIN_INLIERS = 15  # matches needed for the per-cycle re-fit against the reference
FIX_SNAP = 0.03          # fixes that move things more than this (fraction of width) are applied at once
FAST_WIDTH = 480         # width of the fast per-frame tracker (smaller = faster)
ANCHOR_TIMEOUT = 3.0     # hide markers if no accurate position fix for this many seconds
LOST_FRAMES = 8          # keep last markers this many failed frames
RECHECK_EVERY = 12       # try to re-lock onto the references every N frames
MIN_TRACK_INLIERS = 15   # frame-to-frame tracking needs at least this many matches
KEYFRAME_INLIERS = 70    # below this many matches, the current frame becomes the new keyframe
MEMORY_KEYFRAMES = 4     # remembered map views; reopening the map near one of them re-locks instantly
RECOVER_INLIERS = 25     # matches needed to re-lock onto a remembered view
NO_SIGNAL_SECONDS = 2.0  # the camera counts as disconnected after this long without a frame

HIT_RADIUS = 18          # how close (screen px) a click must be to a marker
POPUP_WIDTH = 380        # width of the info popup (px)
DEFAULT_GROUP = "Collectible Cards"
GROUP_SHAPES = {"Collectible Cards": "circle", "Waink Locations": "diamond", "Exploration": "square",
                "Activities": "triangle", "Stunts": "hexagon"}      # marker shape per group
SHAPE_POINTS = {   # unit outlines, scaled by the marker size
    "diamond": [(0, -1.3), (1.2, 0), (0, 1.3), (-1.2, 0)],
    "square": [(-0.95, -0.95), (0.95, -0.95), (0.95, 0.95), (-0.95, 0.95)],
    "triangle": [(0, -1.25), (1.2, 0.95), (-1.2, 0.95)],
    "hexagon": [(1.1 * math.cos(math.radians(60 * k + 30)), 1.1 * math.sin(math.radians(60 * k + 30)))
                for k in range(6)],
}
# Game HUD areas (x0, y0, x1, y1 as fractions of the screen). Ignored for matching,
# and no markers are drawn there.
HUD_ZONES = [(0, 0, 1, 0.09), (0, 0.09, 0.055, 0.6),
             (0.88, 0.09, 1, 0.2), (0.85, 0.72, 1, 1)]

# Fixed on-screen items (centre cursor, controller icon). Ignored for matching only;
# markers are still drawn there.
STATIC_ZONES = [(0.47, 0.44, 0.53, 0.56), (0.052, 0.16, 0.08, 0.21)]

# A position correction that jumps further than FIX_SNAP and has fewer inliers than
# STRONG_FIX must be confirmed by a second, agreeing correction before it is applied.
STRONG_FIX = 45
