# APPLIED 2026-09-02.  Reads the pre-fix backup and rewrites both the
# submission PNG and the manuscript's figures/fig_process_views.pdf
# (330 dpi JPEG, matching the original page box of 1241.47 x 534.99 pt).
#
# Fig. 2 (fig_process_views.pdf) is a raster with no generator anywhere in the
# tree, so the two defects are repaired in place rather than by re-authoring the
# diagram.  Both are text-only, so the layout is untouched.
#
#   A. Top pipeline strip reads  Risk head -> Temperature -> advisor.
#      model.py applies no temperature scaling anywhere, and after the item-(5)
#      edits the word no longer appears in the manuscript either, so the box is
#      wrong and orphaned.  What actually travels from the head to the advisor
#      is the risk score that Definition 2 and Algorithm 1 consume, so the box
#      is RELABELLED, not deleted: relabelling leaves the strip geometry, the
#      arrows and the box radii exactly as they are.
#      The fill is clipped to the measured salmon interior (x 4253..4625,
#      y 8..192 at mid-box) so the rounded grey border is never painted over.
#
#   B. Advisor panel line (a) reads "High confidence filer".
#      Line (b) already contains a correctly spelled "filter" in the same font,
#      size and colour, 77 px below, so that word is COPIED pixel-for-pixel
#      instead of re-rendered.  No font matching, no baseline guessing.
import os
import sys
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "fig_process_views_pre_fix.png")
OUT = HERE + os.sep
ARIAL = "C:/Windows/Fonts/arial.ttf"
SALMON = (226, 114, 107, 255)

im = Image.open(SRC).convert("RGBA")

# ---- A. "Temperature" -> "Risk score" --------------------------------------
# Calibrate on the neighbouring "Risk head" box, whose ink measures
# x 3853..4127, y 77..122: 45 px from ascender to baseline.
size = max(s for s in range(20, 140)
           if (lambda b: b[3] - b[1])(ImageFont.truetype(ARIAL, s)
                                      .getbbox("Risk head")) <= 45)
font = ImageFont.truetype(ARIAL, size)
ImageDraw.Draw(im).rectangle([4256, 60, 4622, 155], fill=SALMON)
bb = font.getbbox("Risk score")
cx = (4253 + 4625) // 2
ImageDraw.Draw(im).text((cx - (bb[2] - bb[0]) // 2 - bb[0], 77 - bb[1]),
                        "Risk score", font=font, fill=(0, 0, 0, 255))

# ---- B. "filer" -> "filter", copied from line (b) ---------------------------
# line (a) ink band y 879..940, "filer"  at x 5137..5239
# line (b) ink band y 956..1017, "filter" at x 4928..5047   (line pitch 77)
word = im.crop((4922, 950, 5053, 1023))
ImageDraw.Draw(im).rectangle([5128, 870, 5262, 948],
                             fill=(243, 242, 241, 255))
im.paste(word, (4922 + 209, 950 - 77))

im.save(OUT + "fig_process_views_FIXED.png")
im.convert("RGB").save(OUT + "fig_process_views_FIXED.pdf",
                       "PDF", resolution=600)
im.crop((3600, 0, 5690, 230)).save(OUT + "prev_strip.png")
im.crop((4450, 840, 5450, 1060)).save(OUT + "prev_filter.png")
print("Arial size for the strip label: %d  (ink %d px, target 45)"
      % (size, font.getbbox("Risk score")[3] - font.getbbox("Risk score")[1]))
print("saved ->", OUT + "fig_process_views_FIXED.png / .pdf")
