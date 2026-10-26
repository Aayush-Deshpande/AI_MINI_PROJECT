"""Prepare only browser assets for Vercel's public output directory."""
from pathlib import Path
import shutil

root=Path(__file__).resolve().parents[1]
output=root/'public'
output.mkdir(exist_ok=True)
for name in ('index.html','app.js','style.css'):
    shutil.copy2(root/'static'/name,output/name)
print('Prepared index.html, app.js and style.css for Vercel.')
