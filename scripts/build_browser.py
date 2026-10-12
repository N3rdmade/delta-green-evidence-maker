"""Build a static browser edition from the recovered v127 editor and existing asset library."""
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
# Existing root-level frames receive virtual browse categories without changing
# paths or IDs in previously saved projects. Real frame subfolders are already
# discovered recursively by build_frame_library().
ROOT_FRAME_CATEGORIES = {
    "Polaroids": {"Original", "Film", "Modern Rainbow"},
    "Photo Frames": {"Brass Tack", "Nail", "Tape", "Gum", "Red Dart"},
    "Notes & Journals": {"Paperclip", "Folded", "Pinned Note", "Stapled Torn", "File Card"},
    "Evidence Files": {"Stamped", "Fingerprint", "Case File", "Evidence Tag"},
    "Damaged & Weathered": {"Burned", "Termite Damage", "Frozen Clip", "Ooze Tooth", "Dirt Caked", "Paint Spatter", "Water Damaged", "Moldy", "Cracked", "Wax Drip", "Blood Splatter", "Lipstick Kiss", "Alien Glyphs"},
}
FRAME_CATEGORY_ORDER = ["Polaroids", "Photo Frames", "Newspaper", "Notes & Journals", "Leather", "Evidence Files", "Damaged & Weathered"]
frame_library = namespace["build_frame_library"]()
for frame in frame_library["frames"]:
    if frame.get("category"):
        continue
    frame["category"] = next((category for category, names in ROOT_FRAME_CATEGORIES.items() if frame["name"] in names), "Photo Frames")
found = {entry["name"]: entry for entry in frame_library["categories"]}
for category in FRAME_CATEGORY_ORDER:
    if any(f["category"] == category for f in frame_library["frames"]):
        found.setdefault(category, {"name": category, "subcategories": []})
frame_library["categories"] = sorted(found.values(), key=lambda item: (FRAME_CATEGORY_ORDER.index(item["name"]) if item["name"] in FRAME_CATEGORY_ORDER else len(FRAME_CATEGORY_ORDER), item["name"].lower()))

manifest = {"version": "v130.2-browser", "frames": frame_library,
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

html = (ROOT / "migration/v127/index.html").read_text()
html = html.replace("<script>", '<script src="adapter.js?v=130.2"></script>\n<script>', 1)
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
# Restoring a project must not asynchronously overwrite its completion status.
# The saved preview mode belongs to the project, not global browser settings.
# v127's desktop project-sharing UI uses an EMX server endpoint. Reuse portable
# browser backups rather than directing a static-site visitor to a dead endpoint.
html = html.replace('onclick="chooseSharedProjectImport()"', 'onclick="BrowserApp.importProjectFiles()"')
html = html.replace('onclick="exportSharedProject()"', 'onclick="BrowserApp.exportProjectFile()"')
html = html.replace('accept=".emx,.zip,.json"', 'accept=".json"')
# Browser merge results use safe local data URLs rather than server cache paths.
html = html.replace("src:j.url+'?v='+Date.now()", "src:j.url")
# v127 must restore the project's preview background without changing global
# preferences asynchronously after the project has loaded.
html = html.replace("if(data.previewBackground)chooseBgMode(data.previewBackground);",
                    "if(data.previewBackground)setBg(data.previewBackground);")
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
html = html.replace('Perfect for DELTA GREEN and other investigative games', 'v130 • Browser edition • Projects stay on this device')
# v127's cut rebuild can complete synchronously when a sticker has no cuts.
# Two sticker-load callbacks incorrectly assumed the return was always a Promise.
html = html.replace("rebuildCutAssetsForTarget({kind:'sticker',index:i,node:st.node,st}).then(",
                    "Promise.resolve(rebuildCutAssetsForTarget({kind:'sticker',index:i,node:st.node,st})).then(")
html = html.replace("rebuildCutAssetsForTarget({kind:'sticker',index:stickerInstances.indexOf(st),node:st.node,st}).then(",
                    "Promise.resolve(rebuildCutAssetsForTarget({kind:'sticker',index:stickerInstances.indexOf(st),node:st.node,st})).then(")
# Main Label should appear immediately when enabled and an image finishes loading.
# The desktop v83 first-spawn delay left the toggle ON while hiding the label.
html = html.replace(
    "pendingMainLabelSpawnV83=!!mainLabelEnabledV78 && !hadMainLabel;mainLabelExistsV77=hadMainLabel;",
    "pendingMainLabelSpawnV83=false;mainLabelExistsV77=!!mainLabelEnabledV78;")
# Imported projects retain explicit layer visibility; defaults shouldn't hide ON labels.
html = html.replace(
    "namePreview.style.display=mainLabelExistsV77?'block':'none';if(mainLabelExistsV77)syncLabel();",
    "namePreview.style.display=(mainLabelEnabledV78 && mainLabelExistsV77)?'block':'none';if(mainLabelEnabledV78 && mainLabelExistsV77)syncLabel();")
# v130: The source photo takes its initial fit when imported. Reopening or
# editing the frame may refresh the frame preview, but must not move the photo.
html = html.replace(
    "if(imageLoaded && imageBoxScope==='photo')captureMainImagePlacement();",
    "/* Preserve captured photo placement while previewing another frame. */")
html = html.replace(
    "if(frame===currentFrame && imageLoaded && imageBoxScope==='photo')captureMainImagePlacement();",
    "/* Frame refresh must not overwrite an already placed main image. */")
# Rebuilding a punched/edited frame may auto-fit the BACKGROUND, but the
# already positioned foreground photo must retain its independent geometry.
html = html.replace(
    "if(fitted && imageLoaded && imageBoxScope==='photo'){\\n      captureMainImagePlacement();\\n      syncImage();\\n    }",
    "if(fitted && imageLoaded && imageBoxScope==='photo'){\\n      syncImage();\\n    }")
# Capture the photo aperture used at initial placement. Subsequent changes to
# the frame's editable photo bounds must not resize the original photo window.
html = html.replace("function captureMainImagePlacement(){",
    "function captureMainImagePlacement(){ imagePlacementFrameBounds=([...((getDisplayedFrame()||currentFrame)?.photo||[0,0,1,1])]);")
html = html.replace("function getStoredMainImagePlacementRect(scale=1){",
    "function getStoredMainImagePlacementRect(scale=1){")
html = html.replace("let [l,t,r,b]=frame.photo,ow=r-l,oh=b-t;\n  return {left:(l+(imageBoxX-imageBoxW/2)*ow)*scale",
    "let [l,t,r,b]=imagePlacementFrameBounds||frame.photo,ow=r-l,oh=b-t;\n  return {left:(l+(imageBoxX-imageBoxW/2)*ow)*scale")
# Persist captured geometry so saved projects reopen without jumping.
html = html.replace("data.pendingMainLabelSpawnV83=!!pendingMainLabelSpawnV83;",
    "data.imagePlacementFrameBounds=imagePlacementFrameBounds;data.pendingMainLabelSpawnV83=!!pendingMainLabelSpawnV83;")
html = html.replace("pendingMainLabelSpawnV83=!!data?.pendingMainLabelSpawnV83;",
    "imagePlacementFrameBounds=Array.isArray(data?.imagePlacementFrameBounds)?data.imagePlacementFrameBounds.slice(0,4):null;pendingMainLabelSpawnV83=!!data?.pendingMainLabelSpawnV83;")
html = html.replace("let pendingMainLabelSpawnV83=false;",
    "let imagePlacementFrameBounds=null;let pendingMainLabelSpawnV83=false;")
# v130: explicit through-punch destination, separate from All Below logic.
for tool in ('cut','eraser'):
    existing=f'id="{tool}ScopeFrameV90"'
    html=html.replace(f'<button {existing}',
        f'<button id="{tool}ScopeMainImageV90" class="editToolAction" type="button" onclick="setPunchScopeV90(&#39;mainImage&#39;)">Main Image</button><button {existing}')
html = html.replace("['current','below','belowFrame','belowFrameBackground'].includes(v)",
                    "['current','below','mainImage','belowFrame','belowFrameBackground'].includes(v)")
html = html.replace("below:'Below',belowFrame:'Frame'",
                    "below:'Below',mainImage:'MainImage',belowFrame:'Frame'")
html = html.replace("let sourceLevel=getTargetVisualLevelV90(t),targets=[];",
    "let sourceLevel=getTargetVisualLevelV90(t),targets=[];")
html = html.replace("  // Main Image acts as the base image layer below normal overlays.",
    "  if(scope==='mainImage')targets=[];\n  // Main Image acts as the base image layer below normal overlays.")
html = html.replace("if(t.kind!=='subject' && sourceLevel>=110 && imageLoaded && !mainImageLocked)targets.push('mainImage');",
    "if(t.kind!=='subject' && (scope==='mainImage'||sourceLevel>=110) && imageLoaded && !mainImageLocked)targets.push('mainImage');")
# v130.1: A deliberate switch to a different frame should fit the photo again.
# Edits/cuts to the current frame (and picker previews) never change its fit.
html = html.replace("let imagePlacementFrameBounds=null;let pendingMainLabelSpawnV83=false;",
    "let imagePlacementFrameBounds=null, pendingPhotoRefitFrameId=null;let pendingMainLabelSpawnV83=false;")
html = html.replace("  currentFrame=frameList.find(f=>f.id===id)||frameList[0];\n  if(!initial || fromClick)frameSelectionConfirmed=true;",
    "  let nextFrame=frameList.find(f=>f.id===id)||frameList[0];\n  if(!initial && imageLoaded && currentFrame && currentFrame.id!==nextFrame.id)pendingPhotoRefitFrameId=nextFrame.id;\n  currentFrame=nextFrame;\n  if(!initial || fromClick)frameSelectionConfirmed=true;")
html = html.replace("    layout(initial);\n    if(typeof syncImageEditToolButtons==='function')",
    "    if(pendingPhotoRefitFrameId===frame.id && frame===currentFrame){\n      pendingPhotoRefitFrameId=null;\n      if(imageLoaded && imageBoxScope==='photo')captureMainImagePlacement();\n    }\n    layout(initial);\n    if(typeof syncImageEditToolButtons==='function')")
html = html.replace('</body>', '<script>BrowserApp.installUI();</script></body>')
(OUT / "index.html").write_text(html, encoding="utf-8")
print(f"Built {OUT}: {len(manifest['frames']['frames'])} frames, {len(manifest['stickers']['stickers'])} stickers")
