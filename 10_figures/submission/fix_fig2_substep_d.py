# Relabels Fig. 2's substep (d) from "Disengage Safety checks" to
# "Fail-open: clear blacklist", and rewrites the manuscript's
# figures/fig_process_views.pdf so that nothing else about the figure moves.
#
# Fig. 2 is a raster with no generator anywhere in the tree, so this is an
# in-place text edit, the same method fix_fig_process_views.py used in 2026-09.
#
# Why the label changes.  BORA does not disengage a safety check.  Substep (d)
# is the fail-open path: on sustained low confidence the advisor clears the
# blacklist and the cluster runs vanilla Raft, which removes advisory exclusion
# rather than any safety mechanism.  Algorithm 1 already calls the substep
# "Fail-open check", so the figure now agrees with it, and the manuscript's
# parenthetical reconciling the two words is no longer needed.
#
# Geometry, measured on fig_process_views.png (5690 x 2452, 330 dpi):
#   substep lines (a)..(d) sit at y = 870 + 77*i, ink band 73 px
#   line (d) body ink box   x 4665..5379, y 1110..1170   (width 714)
#   panel background        (243, 242, 241), right edge x 5531
#   Arial 63 reproduces the existing ink: width 716 vs 714, height 59 vs 60
#   the replacement measures 679 px, so it is SHORTER than what it replaces
#
# TWO THINGS THE PDF NEEDS, both found by diffing renders against the old file:
#   the master PNG is RGBA, so it must be composited onto WHITE -- converting
#   straight to RGB paints every transparent pixel black; and the embedded JPEG
#   is quality 95, which reproduces the previous file to the byte (1,823,5xx)
#   and leaves every untouched pixel identical.
import io
import os
import sys
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REV = os.path.normpath(os.path.join(HERE, "..", "..", "..", "리비전", "figures"))
ARIAL = "C:/Windows/Fonts/arial.ttf"

SRC = os.path.join(HERE, "fig_process_views.png")
OLD, NEW = "Disengage Safety checks", "Fail-open: clear blacklist"
INK = (4665, 1110, 5379, 1170)          # body of line (d), measured
BG = (243, 242, 241, 255)
PANEL_RIGHT = 5531
DPI, QUALITY = 330, 95

im = Image.open(SRC)
assert im.size == (5690, 2452), im.size
assert im.mode == "RGBA", im.mode
print("master %s %s" % (im.mode, im.size))

size = min(range(40, 100),
           key=lambda s: abs((lambda b: b[2] - b[0])(
               ImageFont.truetype(ARIAL, s).getbbox(OLD)) - (INK[2] - INK[0])))
font = ImageFont.truetype(ARIAL, size)
w_new = (lambda b: b[2] - b[0])(font.getbbox(NEW))
assert w_new <= PANEL_RIGHT - INK[0], "label would overrun the panel"

d = ImageDraw.Draw(im)
d.rectangle([INK[0] - 6, INK[1] - 8, PANEL_RIGHT - 3, INK[3] + 8], fill=BG)
bb = font.getbbox(NEW)
d.text((INK[0] - bb[0], INK[1] - bb[1]), NEW, font=font, fill=(0, 0, 0, 255))
im.save(SRC)

flat = Image.new("RGB", im.size, (255, 255, 255))
flat.paste(im, mask=im.split()[3])
pdf = os.path.join(REV, "fig_process_views.pdf")
flat.save(pdf, "PDF", resolution=DPI, quality=QUALITY)
flat.crop((4400, 700, 5600, 1230)).save(
    os.path.join(HERE, "fig2_substep_d_after.png"))

print("Arial %d: '%s' %d px -> '%s' %d px (panel allows %d)"
      % (size, OLD, INK[2] - INK[0], NEW, w_new, PANEL_RIGHT - INK[0]))
print("png ->", SRC)
print("pdf -> %s  (%d bytes)" % (pdf, os.path.getsize(pdf)))
