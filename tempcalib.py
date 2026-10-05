# -*- coding: utf-8 -*-
"""
tempcalib.py
Universal temperature calibration (1D/2D/3D, incl. CON spectra).
- Direct disk read access to acqus and procs for 100% precision (SFO, BF1, TE).
- Automatic TROSY correction.
- Intelligently detects nuclei and uses up to 64-bit precision.
- Smart dialog: Warns and asks for nominal water shift if 1H transmitter is off-resonance.
"""

import os

cd = CURDATA()
if cd is None:
    ERRMSG("No dataset open! Please load a dataset first.")
    EXIT()

acqus_path = os.path.join(cd[3], cd[0], str(cd[1]), "acqus")
pdata_path = os.path.join(cd[3], cd[0], str(cd[1]), "pdata", str(cd[2]))

def get_par(param, default=""):
    try:
        val = GETPAR(param)
        if val is None: return default
        return str(val).strip()
    except:
        return default

def get_par_float(param, default=0.0):
    try:
        val = get_par(param, "")
        return float(val) if val != "" else default
    except:
        return default

def get_exact_float(filepath, param, default=0.0):
    try:
        with open(filepath, "r") as f:
            for line in f:
                if line.startswith("##$" + param + "="):
                    return float(line.split("=")[1].strip())
    except:
        pass
    return default

XI_FACTORS = {
    "1H":  1.0,
    "15N": 0.101329118,
    "13C": 0.251449530
}

# 1. Dimensionality
parmode = get_par("PARMODE", "0").upper()
if parmode in ("2", "3D", "3"): dim = 3
elif parmode in ("1", "2D"): dim = 2
else: dim = 1

# 2. Find exact 1H reference frequency (SFO) and channel (1-4)
sfo_1h = 0.0
ch_1h = 1
for ch in range(1, 5):
    nuc = get_par("NUC%d" % ch, "").upper()
    if "1H" in nuc or "H1" in nuc:
        ch_1h = ch
        sfo_1h = get_exact_float(acqus_path, "SFO%d" % ch, 0.0)
        if sfo_1h == 0.0:
            sfo_1h = get_par_float("SFO%d" % ch, 0.0)
        break

if sfo_1h <= 0.0:
    ERRMSG("Could not find a 1H reference frequency. Aborting.")
    EXIT()

# 3. Detect TROSY
pulprog = get_par("PULPROG", "").lower()
is_trosy = "trosy" in pulprog or pulprog.startswith("tr")

# 4. Assign nuclei to processing dimensions (F1, F2, F3)
nuclei = {}
for d in range(1, dim + 1):
    # TopSpin param prefix: F2 (or 1D F1) = no prefix, F1 = "1 ", F2 in 3D = "2 " (varies, check NUC1)
    prefix = "" if d == 1 else "%d " % (d - 1)
    nuc = get_par(prefix + "NUC1", "").upper()
    if "15N" in nuc or "N15" in nuc: nuclei[d] = "15N"
    elif "13C" in nuc or "C13" in nuc: nuclei[d] = "13C"
    else: nuclei[d] = "1H"

# 5. Read TRUE temperature safely
# Use 298.0 K only if the read value is physically impossible for liquid NMR (< 250 or > 400 K)
te_val = get_exact_float(acqus_path, "TE", 0.0)
if not (250.0 < te_val < 400.0): 
    te_val = get_par_float("TE", 0.0)
if not (250.0 < te_val < 400.0):
    te_val = 298.0

# Read offset (O1P, O2P...) to check for off-resonance
# We read it safely via GETPAR. If it fails, fallback to 4.7
o_ppm_1h = get_par_float("O%dP" % ch_1h, 4.700)
is_off_resonance = abs(o_ppm_1h - 4.700) > 0.5

# Build dialog labels
dim_nucs = []
for d in range(1, dim + 1):
    # Proper dimension mapping for output display:
    # 1D: F1=1
    # 2D: F2=1, F1=2
    # 3D: F3=1, F2=2, F1=3
    if dim == 1: d_name = "F1"
    elif dim == 2: d_name = "F2" if d == 1 else "F1"
    else: d_name = "F3" if d == 1 else ("F2" if d == 2 else "F1")
    dim_nucs.append("%s=%s" % (d_name, nuclei[d]))

labels = ["True temperature [K] (from acqus):"]
defaults = ["%.2f" % te_val]

dialog_title = "Temperature Calibration"
trosy_label = " [TROSY active]" if is_trosy else ""
dialog_header = "Dataset: %dD (%s)%s" % (dim, ", ".join(dim_nucs), trosy_label)

if is_off_resonance:
    dialog_header += "\n\nWARNING: 1H transmitter (Channel %d) is at %.2f ppm (Off-Resonance)!\nPlease confirm the correct nominal water shift for back-calculation." % (ch_1h, o_ppm_1h)
    labels.append("Nominal water shift [ppm]:")
    defaults.append("4.700")
else:
    dialog_header += "\n\nPlease confirm temperature:"

result = INPUT_DIALOG(dialog_title, dialog_header, labels, defaults)

if result is None: EXIT()

try:
    temp = float(result[0])
    if is_off_resonance:
        nom_water = float(result[1])
    else:
        nom_water = 4.700
except ValueError:
    ERRMSG("Invalid input! Please enter valid numbers.")
    EXIT()

# 6. Calculate calibration
shift_h2o = -(temp / 96.9) + 7.83

if is_off_resonance:
    # Back-calculate physical SFO of water based on the distance between current offset and nominal water
    f_water = sfo_1h - ((o_ppm_1h - nom_water) * sfo_1h / 1000000.0)
else:
    f_water = sfo_1h

sf_1h = f_water - ((shift_h2o * f_water) / 1000000.0)

html = [
    "<html>",
    "<font size=\"4\"><b>Calibration Complete</b></font><br><br>",
    "Temperature: <b>%.2f K</b><br>" % temp,
    "H<sub>2</sub>O Shift: <b>%.3f ppm</b><br><hr>" % shift_h2o
]

for d in range(1, dim + 1):
    nuc = nuclei[d]
    sf_base = sf_1h * XI_FACTORS.get(nuc, 1.0)
    
    # TROSY offset (46 Hz = 0.000046 MHz)
    # Applied dynamically based purely on nucleus, regardless of dimension index
    trosy_offset = 0.0
    if is_trosy:
        if nuc == "1H":
            trosy_offset = -0.000046
        elif nuc == "15N":
            trosy_offset = 0.000046
            
    sf_final = sf_base + trosy_offset
    prefix = "" if d == 1 else "%d " % (d - 1)
    
    PUTPAR(prefix + "SF", "%.15f" % sf_final)
    
    proc_files = {1: "procs", 2: "proc2s", 3: "proc3s"}
    proc_path = os.path.join(pdata_path, proc_files[d])
    bf1_d = get_exact_float(proc_path, "BF1", 0.0)
    
    if bf1_d <= 0.0: bf1_d = get_par_float(prefix + "BF1", 0.0)
    if bf1_d <= 0.0: bf1_d = sf_final
        
    sr_d = (sf_final - bf1_d) * 1000000.0
    
    if dim == 1: d_name = "F1"
    elif dim == 2: d_name = "F2" if d == 1 else "F1"
    else: d_name = "F3" if d == 1 else ("F2" if d == 2 else "F1")
        
    nuc_fmt = "<sup>%s</sup>%s" % (nuc[:-1], nuc[-1])
    
    trosy_text = ""
    if trosy_offset != 0.0:
        sign = "+" if trosy_offset > 0 else "-"
        trosy_text = " <font color='blue'><i>(TROSY: %s46 Hz)</i></font>" % sign
        
    html.append("<b>%s (%s):</b>%s<br>" % (d_name, nuc_fmt, trosy_text))
    html.append("&bull; SF: <b>%.6f MHz</b><br>" % sf_final)
    html.append("&bull; SR: <b>%.2f Hz</b>%s" % (sr_d, "" if d == dim else "<br><br>"))

html.append("</html>")

PUTPAR("USERP1", "%.2f" % temp)
PUTPAR("USERP2", "%.4f" % shift_h2o)

# 7. Output & Processing
if dim == 3:
    run_ftnd = CONFIRM("Calibration saved", "The values have been saved.\nShould 'ftnd' be executed now (might take a while)?")
    if not run_ftnd:
        html.insert(1, "<font color='red'><i>Please start FT manually!</i></font><br>")
    
    MSG("".join(html))
    
    if run_ftnd:
        XCMD("ftnd 0")
        XCMD("tabs3")
        XCMD("tabs2")
        XCMD("tabs1")                                
elif dim == 2:
    MSG("".join(html))
    XCMD("xfb")
    XCMD("abs2")
    XCMD("abs1")     
else:
    MSG("".join(html))
    XCMD("efp")
    XCMD("apbk")