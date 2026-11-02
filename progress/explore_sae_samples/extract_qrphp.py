"""Exploration helper (not production code): summarise QR.php sample bodies.

Usage (from repo root): python3 -I progress/explore_sae_samples/extract_qrphp.py progress/explore_sae_samples
Prints, per *.body file of QR.php, the header text and each (line, text) entry.
Only stdlib; regexes tailored to the HTML observed on 2026-11-02.
"""

import glob
import html
import os
import re
import sys

HEADER = re.compile(r'<div style=" background: grey;[^>]*>([^<]*)</div>')
ENTRY = re.compile(
    r'<span class="imagenParada"><img src="([^"]*)" title="([^"]*)"[^>]*></span>'
    r"<span[^>]*>([^<]*)</span>"
)

for path in sorted(glob.glob(os.path.join(sys.argv[1], "*qrphp*.body"))):
    text = open(path, encoding="utf-8").read()
    header = HEADER.findall(text)
    entries = [(t, html.unescape(s).strip()) for _src, t, s in ENTRY.findall(text)]
    print(os.path.basename(path), "| header:", header, "| n_entries:", len(entries))
    for line, s in entries:
        print("   ", repr(line), "->", repr(s))
