"""Session-state key names and builders.

Centralizes the ~40 magic strings that were scattered through app.py. The
string *values* are frozen: they must match the legacy app.py keys exactly,
or existing widget state silently resets. Tests lock the contract.
"""

# --- fixed keys ---
N = "n"                          # number of palette layers (slider)
COV_N = "cov_n"                  # layer count the coverage sliders were seeded for
LOADED_G = "_loaded_g"           # region index currently loaded into widget keys
BOOK = "book"                    # RegionBook in session
DRAW_MODE = "draw_mode"          # region-lasso draw mode toggle
REGION_RADIO = "region_radio"    # region selector radio
ADHOC_HEX = "adhoc_hex"          # ad-hoc match colour picker
ADHOC_ON = "adhoc_on"            # include ad-hoc colour checkbox
EDGE_HL = "edge_hl"              # edge highlights checkbox
EDGE_EXTREME = "edge_extreme"    # extreme edge highlight checkbox
EDGE_SENS = "edge_sens"          # edge sensitivity slider
RELIEF_CAP = "relief_cap"        # auto-reduce bands on flat regions checkbox
PER_REGION_NORM = "per_region_norm"  # colored/painted mini toggle
SHADES = "shades"                # recess shades checkbox (PS mode only)
MATERIAL = "material_select"     # per-region material selector (PS mode only)
NMM_HORIZON = "nmm_horizon"      # global NMM horizon slider (PS mode only)

# --- photometric-stereo (PS) mode ---
NORMALS = "ps_normals"           # decoded (H,W,3) unit normals in session
PS_MASK = "ps_mask"              # (H,W) bool foreground mask from the imported bundle
PS_BOOK = "ps_book"              # RegionBook for PS mode, kept separate from the
                                 # photo-mode BOOK so switching modes can't apply a
                                 # photo-sized region to the PS mask (shape mismatch)
LIGHT_AZ = "light_az"            # virtual-light azimuth slider (deg)
LIGHT_EL = "light_el"            # virtual-light elevation slider (deg)
LIGHT_PRESET = "light_preset"    # nonce to force slider re-seed after a preset click

SAVE_NAME = "save_name"          # recipe save name text input
OWNED = "owned"                  # owned-paints multiselect
RENAME_PREFIX = "rename_"        # prefix of per-region rename text-input keys
ANGLE_LABEL_PREFIX = "angle_label_"  # prefix of per-angle rename text-input keys

# --- projects (mini library) ---
LOADED_PHOTO = "loaded_photo"          # {"bytes":..., "suffix":...} for a loaded project
LOADED_NAME = "loaded_project_name"    # display name of the loaded project (save default)
SAVE_PROJECT_NAME = "save_project_name"
LOAD_SELECT = "load_project_select"

# --- angles (multi-angle view) ---
ANGLES = "angles"                # list[AngleData] in session: the angle records
ACTIVE_ANGLE = "active_angle"    # int index into ANGLES of the active angle
ANGLE_SELECT = "angle_select"    # active-angle selector widget key


# --- per-index builders ---
def slot_code(i: int) -> str: return f"slot_code_{i}"
def slot_hex(i: int) -> str: return f"slot_hex_{i}"
def slot_hexinput(i: int) -> str: return f"slot_hexinput_{i}"
def cov_pct(i: int) -> str: return f"cov_pct_{i}"
def blend(i: int) -> str: return f"blend_{i}"
def rename(i: int) -> str: return f"rename_{i}"
def canvas(n: int) -> str: return f"canvas_{n}"
def angle_label(i: int) -> str: return f"{ANGLE_LABEL_PREFIX}{i}"
