"""Build a static browser edition from the unchanged v42 editor and asset library."""
import ast
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
source = (ROOT / "photo_composer.py").read_text()
tree = ast.parse(source)
namespace = {"ROOT": ROOT, "FRAMES_DIR": ROOT / "frames", "STICKERS_DIR": ROOT / "stickers",
             "re": re, "STICKER_EXTENSIONS": {".png", ".jpg", ".jpeg", ".webp"}}
meta = json.loads((ROOT / "frames.json").read_text())
namespace.update(FRAME_META_BY_FILE={f["file"]: f for f in meta}, DEFAULT_FRAME_META=meta[0])
functions = {"prettify_name", "build_frame_library", "build_sticker_library"}
settings = {"STYLE_SEEDS", "STYLE_FALLBACKS", "DIRECT_CATEGORIES"}
for node in tree.body:
    if isinstance(node, ast.FunctionDef) and node.name in functions:
        exec(compile(ast.Module(body=[node], type_ignores=[]), "<asset-library>", "exec"), namespace)
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in settings:
                namespace[target.id] = ast.literal_eval(node.value)
fonts = []
for path in sorted((ROOT / "custom_fonts").glob("*")):
    if path.suffix.lower() not in {".ttf", ".otf", ".woff", ".woff2", ".ttc"}:
        continue
    name = path.stem.replace("_", " ")
    fonts.append(dict(id=hashlib.sha1(path.name.encode()).hexdigest()[:14],
                      name=name, custom=False, themed=True,
                      url="custom_fonts/" + path.name))
manifest = {"version": "v44", "frames": namespace["build_frame_library"](),
            "stickers": namespace["build_sticker_library"](), "fonts": fonts,
            "styles": namespace["STYLE_SEEDS"], "fallbacks": namespace["STYLE_FALLBACKS"],
            "categories": namespace["DIRECT_CATEGORIES"]}
OUT.mkdir(exist_ok=True)
for folder in ("frames", "stickers", "custom_fonts"):
    shutil.copytree(ROOT / folder, OUT / folder, dirs_exist_ok=True)
shutil.copy2(ROOT / "logo_app.png", OUT / "logo_app.png")
shutil.copy2(ROOT / "browser/adapter.js", OUT / "adapter.js")
(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
(OUT / ".nojekyll").touch()

html = (ROOT / "index.html").read_text()
html = html.replace("<script>", '<script src="adapter.js?v=44"></script>\n<script>', 1)
html = html.replace('src="/asset/logo_app.png"', 'src="logo_app.png"')
html = html.replace("fetch('/", "BrowserApp.api('/")
html = html.replace("return '/frame/'+String(file||'').split('/').map(part=>encodeURIComponent(part)).join('/');",
                    "return BrowserApp.asset('frames',file);")
html = html.replace("return '/sticker/'+String(file||'').split('/').map(part=>encodeURIComponent(part)).join('/');",
                    "return BrowserApp.asset('stickers',file);")
html = html.replace("src:url('/font/${f.id}')", "src:url('${BrowserApp.fontUrl(f.id)}')")
html = html.replace('src="/project-thumbnail/${encodeURIComponent(pr.id)}?v=${Date.now()}"',
                    'src="${BrowserApp.thumbnail(pr.id)}"')
# Blob/data URLs cannot accept the desktop server's cache-busting query string.
html = html.replace("+'?v='+Date.now()", "")
html = html.replace("async function init(){try{", "async function init(){try{await BrowserApp.ready;")
html = html.replace("async function importProjectState(data){",
                    "async function importProjectState(data){ await BrowserApp.restoreResources(data); fonts=await (await BrowserApp.api('/fonts')).json(); await loadStickers();")
# Ensure browser-saved editable projects contain the same portable resources as backups.
html = html.replace("let projectState=await exportProjectState();",
                    "let projectState=await BrowserApp.packProject(await exportProjectState());")
# Reopening always uses the browser adapter, including the project identifier route.
html = html.replace("await fetch('/project-data/'+encodeURIComponent(projectId))",
                    "await BrowserApp.api('/project-data/'+encodeURIComponent(projectId))")
html = html.replace("onclick=\"openProjectsFolder()\"", "onclick=\"BrowserApp.importProjectFiles()\"")
html = html.replace("Open RAW PROJECTS Folder", "Import Project")
html = html.replace("onclick=\"openOutput()\"", "onclick=\"BrowserApp.exportProjectFile()\"")
html = html.replace("Open Output Folder", "Export Project")
html = html.replace('onclick="chooseFolder()">Browse', 'onclick="BrowserApp.chooseDirectory()">Choose Folder')
html = html.replace('onclick="openFrameFolder(event)">Open Frame Folder',
                    'onclick="BrowserApp.importAssets(\'frames\')">Import Frames')
html = html.replace('onclick="openStickerFolder()">Open Sticker Folder',
                    'onclick="BrowserApp.importAssets(\'stickers\')">Import Stickers')
html = html.replace('onclick="openCustomFonts()">Open Composer Font Folder',
                    'onclick="chooseFontImport()">Import Fonts')
html = html.replace("Fonts installed in Windows on this PC.", "Fonts bundled with this app.")
html = html.replace("Refresh Windows Fonts", "Refresh Fonts").replace("Windows Fonts", "Bundled Fonts")
html = html.replace("No Windows fonts were detected.", "No bundled fonts were found.")
html = html.replace("System Fonts", "Bundled Fonts").replace(" — Windows Font", " — Bundled Font")
html = html.replace('<div class="fontName">${f.name}</div>', '<div class="fontName">${escapeHtml(f.name)}</div>')
html = html.replace('id="saveRawProject" type="checkbox"', 'id="saveRawProject" type="checkbox" checked')
html = html.replace('id="savePath" class="saveBox" readonly', 'id="savePath" class="saveBox" readonly value="Browser Downloads"')
html = re.sub(r'<div class="projectHint">.*?</div>',
              '<div class="projectHint">Editable projects stay in this browser on this device. Use <b>Export Project</b> for a portable backup. Clearing site data removes browser saves.</div>', html, count=1)
html = html.replace('<b>RAW PROJECTS</b>', '<b>this browser</b>')
html = html.replace('Perfect for DELTA GREEN and other investigative games', 'v44 • Browser edition • Projects stay on this device')
html = html.replace('</body>', '<script>BrowserApp.installUI();</script></body>')
(OUT / "index.html").write_text(html, encoding="utf-8")
print(f"Built {OUT}: {len(manifest['frames']['frames'])} frames, {len(manifest['stickers']['stickers'])} stickers")
