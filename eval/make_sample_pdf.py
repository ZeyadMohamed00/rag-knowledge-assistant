"""Builds data/sample-handbook.pdf: 11 short synthetic topic notes, one per page (page order = sorted file name)."""

import glob
import os
import textwrap

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

root = os.path.dirname(os.path.dirname(__file__))
c = canvas.Canvas(os.path.join(root, "data", "sample-handbook.pdf"), pagesize=A4)
for f in sorted(glob.glob(os.path.join(root, "data", "docs", "*.txt"))):
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 780, os.path.basename(f)[:-4].replace("-", " ").title())
    c.setFont("Helvetica", 11)
    y = 750
    for line in textwrap.wrap(open(f).read().strip(), 90):
        c.drawString(60, y, line)
        y -= 16
    c.showPage()
c.save()
