from __future__ import annotations
import io, os, re, uuid, json, urllib.request, webbrowser, subprocess, threading, time, zipfile, shutil, hashlib, sys, base64
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, Response
from PIL import Image, ImageDraw, ImageFont

# Resolve everything from the application itself, never from a hard-coded
# Windows user path or the shell's current working directory.  This makes a
# synced/copyable Evidence_Maker_V2 folder portable between PCs.
ROOT = Path(__file__).resolve().parent
DELTA_GREEN_ROOT = ROOT.parent
FRAMES_DIR = ROOT / 'frames'
UPLOADS = ROOT / 'uploads'
CUSTOM_FONTS = ROOT / 'custom_fonts'
STICKERS_DIR = ROOT / 'stickers'
RAW_PROJECTS_DIR = ROOT / 'RAW PROJECTS'
PROJECT_SOURCES_DIR = RAW_PROJECTS_DIR / 'SOURCES'
SAVED_IMAGES_DIR = ROOT / 'SAVED IMAGES'
for p in (UPLOADS, CUSTOM_FONTS, STICKERS_DIR, FRAMES_DIR, RAW_PROJECTS_DIR, PROJECT_SOURCES_DIR, SAVED_IMAGES_DIR):
    p.mkdir(exist_ok=True)

FRAME_META_LIST = json.loads((ROOT/'frames.json').read_text(encoding='utf-8'))
FRAME_META_BY_FILE = {f['file']: f for f in FRAME_META_LIST}
DEFAULT_FRAME_META = FRAME_META_LIST[0] if FRAME_META_LIST else {
    'photo': [154, 222, 972, 1031],
    'labelDefault': [0.5, 0.8809],
}

def prettify_name(stem: str) -> str:
    stem = re.sub(r'^\d+[_-]*', '', stem)
    parts = [x for x in re.split(r'[_-]+', stem) if x]
    return ' '.join(p.capitalize() for p in parts) or stem or 'Untitled'

def build_frame_library():
    """Build the frame library recursively, using folders as categories.

    Folder convention mirrors stickers:
      frames/<file>                         -> root / ALL FRAMES only
      frames/<Category>/<file>              -> category
      frames/<Category>/<Subcategory>/<file> -> category + subcategory

    Deeper folders are supported; subcategory becomes a slash-separated path.
    Existing frames.json metadata continues to work when an existing frame is
    moved into a folder because metadata can still be matched by basename.
    """
    items = []
    image_paths = [
        x for x in FRAMES_DIR.rglob('*')
        if x.is_file() and x.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}
    ]
    image_paths.sort(key=lambda x: x.relative_to(FRAMES_DIR).as_posix().lower())

    for path in image_paths:
        rel = path.relative_to(FRAMES_DIR)
        rel_posix = rel.as_posix()
        parts = rel.parts
        category = parts[0] if len(parts) > 1 else ''
        subcategory = '/'.join(parts[1:-1]) if len(parts) > 2 else ''

        # Prefer an exact relative-path metadata entry, then fall back to the
        # original basename so existing frames.json does not need rewriting.
        meta = FRAME_META_BY_FILE.get(rel_posix) or FRAME_META_BY_FILE.get(path.name)
        if meta:
            item = dict(meta)
            item['file'] = rel_posix
        else:
            stable_id = re.sub(r'[^a-z0-9]+', '-', path.stem.lower()).strip('-') or path.stem.lower()
            item = {
                'id': stable_id,
                'name': prettify_name(path.stem),
                'file': rel_posix,
                'photo': list(DEFAULT_FRAME_META.get('photo', [154, 222, 972, 1031])),
                'labelDefault': list(DEFAULT_FRAME_META.get('labelDefault', [0.5, 0.8809])),
            }
        # IDs from frames.json were originally unique only in one flat folder.
        # Keep those IDs where possible, but nested duplicate IDs are made
        # stable/unique using the relative path.
        if any(existing.get('id') == item.get('id') for existing in items):
            item['id'] = re.sub(r'[^a-z0-9]+', '-', rel_posix.lower()).strip('-') or path.stem.lower()
        item['category'] = category
        item['subcategory'] = subcategory
        items.append(item)

    categories = []
    top_dirs = sorted([x for x in FRAMES_DIR.iterdir() if x.is_dir()], key=lambda x: x.name.lower())
    for top in top_dirs:
        subcategories = []
        for child in sorted([x for x in top.rglob('*') if x.is_dir()], key=lambda x: x.relative_to(top).as_posix().lower()):
            subcategories.append(child.relative_to(top).as_posix())
        categories.append({'name': top.name, 'subcategories': subcategories})

    return {
        'frames': items,
        'categories': categories,
        'root_count': sum(1 for x in items if not x.get('category')),
    }

def build_frames():
    return build_frame_library()['frames']

def get_frames_and_map():
    frames = build_frames()
    return frames, {f['id']: f for f in frames}


STICKER_EXTENSIONS = {'.png','.webp','.jpg','.jpeg'}

def build_sticker_library():
    """Build the sticker library recursively from the folders on disk.

    Folder convention:
      stickers/<file>                         -> root / ALL STICKERS only
      stickers/<Category>/<file>              -> category
      stickers/<Category>/<Subcategory>/<file> -> category + subcategory

    Deeper folders are also supported; the subcategory value becomes a
    slash-separated path such as "Evidence/Fingerprints".
    """
    items = []
    image_paths = [
        x for x in STICKERS_DIR.rglob('*')
        if x.is_file() and x.suffix.lower() in STICKER_EXTENSIONS
    ]
    image_paths.sort(key=lambda x: x.relative_to(STICKERS_DIR).as_posix().lower())

    for path in image_paths:
        rel = path.relative_to(STICKERS_DIR)
        rel_posix = rel.as_posix()
        parts = rel.parts
        category = parts[0] if len(parts) > 1 else ''
        subcategory = '/'.join(parts[1:-1]) if len(parts) > 2 else ''
        stable_id = re.sub(r'[^a-z0-9]+', '-', rel_posix.lower()).strip('-') or path.stem.lower()
        items.append({
            'id': stable_id,
            'name': prettify_name(path.stem),
            'file': rel_posix,
            'category': category,
            'subcategory': subcategory,
        })

    categories = []
    top_dirs = sorted([x for x in STICKERS_DIR.iterdir() if x.is_dir()], key=lambda x: x.name.lower())
    for top in top_dirs:
        subcategories = []
        for child in sorted([x for x in top.rglob('*') if x.is_dir()], key=lambda x: x.relative_to(top).as_posix().lower()):
            subcategories.append(child.relative_to(top).as_posix())
        categories.append({'name': top.name, 'subcategories': subcategories})

    return {
        'stickers': items,
        'categories': categories,
        'root_count': sum(1 for x in items if not x.get('category')),
    }

def build_stickers():
    # Compatibility helper used by older code paths.
    return build_sticker_library()['stickers']

FRAMES, FRAME_MAP = get_frames_and_map()
PORT = 5000
app = Flask(__name__)
current_source = None

SETTINGS_FILE = ROOT / 'settings.json'
def default_save_folder():
    # The app lives in <Delta Green>/Evidence_Maker_V2, so the portable default
    # output location is the parent Delta Green folder on whichever PC runs it.
    return str(DELTA_GREEN_ROOT)

def ensure_usable_save_folder(value):
    """Return a usable save folder, repairing stale synced Windows paths.

    settings.json can be synced between PCs.  If it contains another user's
    absolute path (for example another PC's user-profile path), attempting to create it can
    raise PermissionError.  Try the configured path, then automatically fall
    back to this copy of the app's parent folder instead of aborting startup.
    """
    candidate = Path(value or default_save_folder()).expanduser()
    fallback = DELTA_GREEN_ROOT
    try:
        # Folder-picker selections already exist.  A missing absolute path in a
        # synced settings file is therefore almost certainly from another PC.
        if not candidate.exists():
            fallback.mkdir(parents=True, exist_ok=True)
            return str(fallback.resolve())
        candidate.mkdir(parents=True, exist_ok=True)
        return str(candidate.resolve())
    except (OSError, PermissionError):
        fallback.mkdir(parents=True, exist_ok=True)
        return str(fallback.resolve())

settings = {'save_folder': default_save_folder(), 'preview_background': 'dark'}
if SETTINGS_FILE.exists():
    try:
        settings.update(json.loads(SETTINGS_FILE.read_text(encoding='utf-8')))
    except Exception:
        pass
settings['save_folder'] = ensure_usable_save_folder(settings.get('save_folder'))

def persist_settings():
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding='utf-8')

THEME_WORDS = [
    'script','hand','handwriting','ink','marker','brush','chalk','crayon','cursive','callig',
    'blackletter','fraktur','goth','horror','creep','spooky','blood','old','typewriter','antique',
    'vintage','western','papyrus','chiller','jokerman','freestyle','bradley','mistral','viner',
    'ravie','snap','tempus','gabriola','kunstler','edwardian','lucida','segoe print','segoe script',
    'blackadder','old english','curlz','french script','vladimir','pristina','rage','informal','corsiva'
]
PREFERRED = [
    'Segoe Print Bold','Segoe Print','Segoe Script Bold','Segoe Script','Ink Free','Lucida Handwriting',
    'Bradley Hand ITC','Freestyle Script','French Script MT','Blackadder ITC','Old English Text MT',
    'Chiller','Viner Hand ITC','Mistral','Edwardian Script ITC','Kunstler Script','Monotype Corsiva',
    'Papyrus','Courier New','Bookman Old Style','Goudy Old Style','Georgia'
]

# A hand-picked starter shelf of Fontsource fonts with horror/occult/retro dossier vibes.
# Users can also search the full Fontsource catalog by family name from the app.
STYLE_SEEDS = {
    'horror': [
        'creepster','nosifer','eater','butcherman','frijole','metal-mania','mystery-quest',
        'new-rocker','pirata-one','lacquer','rubik-burned','rubik-wet-paint','rubik-dirt',
        'rubik-glitch','rubik-distressed','rubik-marker-hatch','rubik-puddles','rubik-vinyl',
        'rubik-microbe','rubik-moonrocks','rubik-beastly','rubik-80s-fade','rubik-iso',
        'rubik-maze','kablammo','road-rage','trade-winds','jacquard-24','jacquarda-bastarda-9',
        'henny-penny','emilys-candy','miltonian','miltonian-tattoo','griffy','jolly-lodger',
        'flavors','fascinate','fascinate-inline','fontdiner-swanky','freckle-face','ribeye',
        'ribeye-marrow','risque','kranky','barrio','caesar-dressing','underdog','bowlby-one-sc',
        'black-ops-one','ranchers','smokum','ewert','sancreek','rye','metamorphous',
        'medievalsharp','unifrakturcook','unifrakturmaguntia'
    ],
    'script': [
        'great-vibes','alex-brush','allura','dancing-script','sacramento','parisienne','tangerine',
        'pinyon-script','monsieur-la-doulaise','italianno','rouge-script','qwigley','yellowtail',
        'satisfy','cookie','kaushan-script','marck-script','mr-dafoe','mr-de-haviland',
        'mrs-saint-delafield','petit-formal-script','windsong','cedarville-cursive','clicker-script',
        'engagement','euphoria-script','grand-hotel','herr-von-muellerhoff','jim-nightshade',
        'la-belle-aurore','league-script','meddon','meie-script','miss-fajardose','montez',
        'norican','quintessential','rochester','rouge-script','seaweed-script','italianno',
        'birthstone','carattere','corinthia','hurricane','inspiration','luxurious-script',
        'mea-culpa','moon-dance','oooh-baby','passions-conflict','water-brush'
    ],
    'gothic': [
        'unifrakturcook','unifrakturmaguntia','pirata-one','new-rocker','metal-mania','germania-one',
        'medievalsharp','metamorphous','almendra','almendra-display','almendra-sc','uncial-antiqua',
        'cinzel','cinzel-decorative','grenze-gotisch','eagle-lake','fondamento','nova-cut',
        'im-fell-english-sc','im-fell-great-primer-sc','im-fell-french-canon-sc',
        'im-fell-double-pica-sc','macondo','macondo-swash-caps','medula-one','rye','smokum',
        'trade-winds','berkshire-swash','caesar-dressing','fontdiner-swanky','mystery-quest',
        'averia-serif-libre','bokor','croissant-one','elsie-swash-caps','federant','gren-ze-gotisch',
        'iceberg','jolly-lodger','kelly-slab','kumar-one-outline','maiden-orange','quintessential',
        'risque','uncial-antiqua','vast-shadow'
    ],
    'vintage': [
        'special-elite','old-standard-tt','im-fell-english','im-fell-dw-pica','im-fell-great-primer',
        'im-fell-french-canon','im-fell-double-pica','sancreek','ewert','smythe','diplomata','ultra',
        'limelight','graduate','vast-shadow','rye','cutive','cutive-mono','courier-prime',
        'libre-caslon-display','libre-caslon-text','cormorant-garamond','eb-garamond',
        'playfair-display','abril-fatface','alfa-slab-one','stardos-stencil','bodoni-moda','cinzel',
        'forum','goudy-bookletter-1911','benne','elsie','rokkitt','lora','cormorant-sc','spectral-sc',
        'bungee-shade','bungee-outline','fascinate-inline','fontdiner-swanky','monoton','poiret-one',
        'prata','rozha-one','rufina','sorts-mill-goudy','yeseva-one','young-serif','zilla-slab',
        'bree-serif','arbutus-slab','bio-rhyme','crete-round','faustina','fraunces'
    ],
    'grunge': [
        'rubik-dirt','rubik-distressed','rubik-burned','rubik-wet-paint','rubik-glitch',
        'rubik-marker-hatch','rubik-puddles','rubik-vinyl','rubik-microbe','rubik-moonrocks',
        'rubik-beastly','rubik-80s-fade','rubik-iso','rubik-maze','rubik-bubbles','rubik-maps',
        'rubik-pixels','rubik-lines','rubik-gemstones','rubik-broken-fax','kablammo','road-rage',
        'black-ops-one','bowlby-one-sc','bungee','bungee-shade','bungee-outline','faster-one',
        'fascinate','fascinate-inline','finger-paint','freckle-face','frijole','griffy',
        'hanalei-fill','kranky','londrina-outline','londrina-shadow','londrina-sketch',
        'londrina-solid','major-mono-display','monoton','plaster','ranchers','ribeye','ribeye-marrow',
        'rock-salt','smokum','trade-winds','underdog','wallpoet'
    ],
    'western': [
        'rye','sancreek','ewert','smokum','ranchers','graduate','ultra','stardos-stencil',
        'black-ops-one','bowlby-one-sc','bungee-shade','faster-one','holtwood-one-sc',
        'maiden-orange','rye','special-elite','vast-shadow','arbutus','arbutus-slab','bio-rhyme',
        'bree-serif','crete-round','diplomata','diplomata-sc','fontdiner-swanky','girassol',
        'graduate','kelly-slab','racing-sans-one','rakkas','ribeye','sancreek','smythe',
        'stardos-stencil','ultra','vast-shadow'
    ],
    'stencil': [
        'stardos-stencil','black-ops-one','bungee-stencil','saira-stencil-one','wallpoet',
        'graduate','bungee-outline','bungee-shade','major-mono-display','share-tech-mono',
        'special-elite','cutive-mono','ibm-plex-mono','oswald','teko','russo-one','staatliches',
        'big-shoulders-stencil-display','big-shoulders-stencil-text','allerta-stencil'
    ]
}

DIRECT_CATEGORIES = {
    'handwritten': 'handwriting',
    'typewriter': 'monospace',
    'display': 'display',
    'serif': 'serif',
    'sans': 'sans-serif',
}

STYLE_FALLBACKS = {
    'horror': ['display'],
    'script': ['handwriting'],
    'gothic': ['display'],
    'vintage': ['serif','display'],
    'grunge': ['display'],
    'western': ['display','serif'],
    'stencil': ['display','monospace'],
}



def font_name(path):
    try:
        fam, style = ImageFont.truetype(str(path), 18).getname()
        name = fam.strip(); style = style.strip()
        if style and style.lower() not in ('regular','normal','book') and style.lower() not in name.lower():
            name += ' ' + style
        return name
    except Exception:
        return path.stem.replace('_',' ').replace('-',' ').strip()

def has_word(name, term):
    low=name.lower(); term=term.lower()
    return term in low if ' ' in term else re.search(r'\b'+re.escape(term)+r'\b', low) is not None

def scan_fonts():
    windir = Path(os.environ.get('WINDIR', r'C:\Windows'))
    localapp = Path(os.environ.get('LOCALAPPDATA',''))
    dirs = [windir/'Fonts', localapp/'Microsoft'/'Windows'/'Fonts', CUSTOM_FONTS]
    found=[]; seen=set()
    for folder in dirs:
        if not folder.exists():
            continue
        for p in folder.iterdir():
            if p.suffix.lower() not in {'.ttf','.otf','.ttc'}:
                continue
            try:
                key=str(p.resolve()).lower()
            except Exception:
                key=str(p).lower()
            if key in seen:
                continue
            seen.add(key)
            name=font_name(p); low=name.lower()
            themed=any(has_word(name,k) for k in THEME_WORDS)
            score=0
            for i,pref in enumerate(PREFERRED):
                pl=pref.lower()
                if low==pl or low.startswith(pl+' '):
                    score=max(score,200-i)
            if themed:
                score += 50
            if folder == CUSTOM_FONTS:
                score += 75
            found.append({
                'name':name, 'path':str(p), 'themed':themed or score>0,
                'custom':folder==CUSTOM_FONTS, 'score':score
            })
    found.sort(key=lambda f:(not f['themed'],-f['score'],not f['custom'],f['name'].lower()))
    unique=[]; used_names=set()
    for f in found:
        k=f['name'].lower()
        if k in used_names:
            continue
        used_names.add(k); unique.append(f)
    for f in unique:
        # Stable ID: adding/removing fonts no longer reshuffles every browser /font URL.
        basis=(f['path'].lower()+'|'+f['name'].lower()).encode('utf-8','ignore')
        f['id']=hashlib.sha1(basis).hexdigest()[:14]
    return unique

FONTS = scan_fonts()
FONT_MAP = {f['id']:f for f in FONTS}

def refresh_fonts():
    global FONTS, FONT_MAP
    FONTS=scan_fonts()
    FONT_MAP={f['id']:f for f in FONTS}

def get_font(fid,size):
    f=FONT_MAP.get(str(fid))
    if f:
        try:
            return ImageFont.truetype(f['path'], int(size))
        except Exception:
            pass
    return ImageFont.load_default()

def safe_filename(text):
    text=(text or 'UNKNOWN').strip()
    text=re.sub(r'[<>:"/\\|?*\x00-\x1f]','',text).rstrip('. ').strip()
    return (text or 'UNKNOWN') + '.png'

def safe_project_folder_name(text):
    text=(text or 'UNTITLED').strip()
    text=re.sub(r'[<>:"/\\|?*\x00-\x1f]','',text).rstrip('. ').strip()
    return text or 'UNTITLED'

def split_version_stem(stem):
    m=re.match(r'^(.*?)(?:\s+v(\d+))?$', str(stem or '').strip(), re.I)
    if not m:
        return str(stem or '').strip() or 'UNTITLED', 1
    base=(m.group(1) or '').strip() or 'UNTITLED'
    version=int(m.group(2)) if m.group(2) else 1
    return base, version

def next_version_name(stem, dest, include_project=False):
    base,current=split_version_stem(stem)
    n=max(2,current+1)
    while True:
        candidate=f'{base} v{n}'
        image_exists=(Path(dest)/(candidate+'.png')).exists()
        project_exists=(RAW_PROJECTS_DIR/safe_project_folder_name(candidate)).exists() if include_project else False
        if not image_exists and not project_exists:
            return candidate
        n+=1

def project_folder_from_id(project_id):
    safe=Path(str(project_id or '')).name.strip()
    if not safe:
        return None
    p=(RAW_PROJECTS_DIR/safe).resolve()
    try:
        p.relative_to(RAW_PROJECTS_DIR.resolve())
    except Exception:
        return None
    return p

def decode_data_url(data_url: str):
    if not isinstance(data_url, str) or not data_url.startswith('data:'):
        return None, None
    m = re.match(r'^data:([^;,]+)?(?:;charset=[^;,]+)?(;base64)?,(.*)$', data_url, re.I | re.S)
    if not m:
        return None, None
    mime = (m.group(1) or 'application/octet-stream').lower()
    is_b64 = bool(m.group(2))
    body = m.group(3) or ''
    try:
        if is_b64:
            raw = base64.b64decode(body)
        else:
            from urllib.parse import unquote_to_bytes
            raw = unquote_to_bytes(body)
        return mime, raw
    except Exception:
        return None, None

def mime_extension(mime: str) -> str:
    return {
        'image/png':'.png',
        'image/jpeg':'.jpg',
        'image/jpg':'.jpg',
        'image/webp':'.webp',
        'image/bmp':'.bmp',
        'image/gif':'.gif',
    }.get((mime or '').lower(), '.png')

def persist_shared_source(data_url: str):
    mime, decoded = decode_data_url(data_url)
    if not decoded:
        return None
    PROJECT_SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(decoded).hexdigest()
    ext = mime_extension(mime)
    filename = digest + ext
    target = PROJECT_SOURCES_DIR / filename
    if not target.exists():
        target.write_bytes(decoded)
    return '../SOURCES/' + filename

def source_ref_to_data_url(source_ref: str):
    if not source_ref:
        return None
    try:
        name = Path(str(source_ref)).name
        source_path = (PROJECT_SOURCES_DIR / name).resolve()
        source_path.relative_to(PROJECT_SOURCES_DIR.resolve())
        if not source_path.exists() or not source_path.is_file():
            return None
        ext = source_path.suffix.lower()
        mime = {
            '.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg',
            '.webp':'image/webp', '.bmp':'image/bmp', '.gif':'image/gif'
        }.get(ext, 'application/octet-stream')
        encoded = base64.b64encode(source_path.read_bytes()).decode('ascii')
        return f'data:{mime};base64,{encoded}'
    except Exception:
        return None

def safe_font_filename(text):
    text=re.sub(r'[^A-Za-z0-9._ -]+','',text or 'font').strip().replace(' ','_')
    return text or 'font'

def transform_source(src, ow, oh, panx, pany, zoom, fitmode, rotation=0):
    sw,sh=src.size
    base=min(ow/sw,oh/sh) if fitmode=='fit' else max(ow/sw,oh/sh)
    scale=base*max(.05,float(zoom))
    nw=max(1,int(sw*scale)); nh=max(1,int(sh*scale))
    work=src.resize((nw,nh), Image.Resampling.LANCZOS)
    rot=float(rotation or 0)
    if abs(rot) > .001:
        work=work.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)
        nw,nh=work.size
    canvas=Image.new('RGBA',(ow,oh),(0,0,0,255))
    x=int((ow-nw)/2 + float(panx)*ow)
    y=int((oh-nh)/2 + float(pany)*oh)
    canvas.alpha_composite(work,(x,y))
    return canvas

def parse_hex_color(value, default=(24,21,16)):
    try:
        s=str(value or '').strip().lstrip('#')
        if len(s)==3:
            s=''.join(ch*2 for ch in s)
        if len(s)!=6:
            return default
        return tuple(int(s[i:i+2],16) for i in (0,2,4))
    except Exception:
        return default

def styled_text_layer(size,text,font,bold=False,italic=False,shadow=False,color=(24,21,16),opacity=255):
    W,H=size
    layer=Image.new('RGBA',(W,H),(0,0,0,0))
    d=ImageDraw.Draw(layer)
    stroke=2 if bold else 0
    bbox=d.textbbox((0,0),text,font=font,stroke_width=stroke)
    tw,th=bbox[2]-bbox[0],bbox[3]-bbox[1]
    x=(W-tw)//2; y=(H-th)//2
    alpha=max(0,min(255,int(opacity)))
    fill=(int(color[0]),int(color[1]),int(color[2]),alpha)
    if shadow:
        shadow_alpha=max(0,min(255,int(105*(alpha/255.0))))
        d.text((x+4,y+5),text,font=font,fill=(0,0,0,shadow_alpha),stroke_width=stroke,stroke_fill=(0,0,0,shadow_alpha))
    d.text((x,y),text,font=font,fill=fill,stroke_width=stroke,stroke_fill=fill)
    if italic:
        layer=layer.transform(layer.size,Image.Transform.AFFINE,(1,-0.22,0,0,1,0),resample=Image.Resampling.BICUBIC)
    return layer

def fetch_json(url, timeout=20):
    req=urllib.request.Request(url,headers={'User-Agent':'Evidence-Photo-Composer/1.0'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def pick_static_variant(details):
    variants=details.get('variants') or {}
    weights=details.get('weights') or []
    target=400 if 400 in weights else (weights[0] if weights else None)
    weight_block=variants.get(str(target)) if target is not None else None
    if weight_block is None and variants:
        weight_block=next(iter(variants.values()))
    if not isinstance(weight_block,dict):
        raise RuntimeError('No downloadable static font variant was found.')
    style_block=weight_block.get('normal') or next(iter(weight_block.values()))
    if not isinstance(style_block,dict):
        raise RuntimeError('No normal font style was found.')
    preferred_subset=details.get('defSubset') or 'latin'
    subset_block=style_block.get(preferred_subset) or style_block.get('latin') or next(iter(style_block.values()))
    urls=(subset_block or {}).get('url') or {}
    # The composer/Pillow needs a desktop font file. Fontsource exposes TTF on its
    # static variant endpoint; do not report success after downloading browser-only WOFF.
    file_url=urls.get('ttf')
    if not file_url:
        raise RuntimeError('This Fontsource font has no TTF desktop variant available.')
    return file_url,'.ttf'

def installed_custom_names():
    result=set()
    for p in CUSTOM_FONTS.iterdir():
        if p.is_file() and p.suffix.lower() in {'.ttf','.otf','.ttc'}:
            result.add(font_name(p).lower())
    return result

def open_folder_native(path):
    path=Path(path).resolve()
    errors=[]
    if os.name == 'nt':
        # Explorer.exe is the most reliable way to open a normal folder window from
        # the local Flask process. Fall back to ShellExecute/startfile if needed.
        try:
            flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
            subprocess.Popen(['explorer.exe', str(path)], creationflags=flags)
            return True, errors
        except Exception as e:
            errors.append('explorer: '+str(e))
        try:
            os.startfile(str(path))
            return True, errors
        except Exception as e:
            errors.append('startfile: '+str(e))
        try:
            subprocess.Popen(['cmd.exe','/c','start','',str(path)], shell=False)
            return True, errors
        except Exception as e:
            errors.append('cmd start: '+str(e))
    else:
        try:
            subprocess.Popen(['xdg-open',str(path)])
            return True, errors
        except Exception as e:
            errors.append('xdg-open: '+str(e))
    return False, errors

@app.get('/')
def home():
    return Response((ROOT/'index.html').read_text(encoding='utf-8'), mimetype='text/html')

@app.get('/frames')
def frames():
    return jsonify(build_frame_library())

@app.get('/frame/<path:name>')
def frame_file(name):
    # Supports category/subcategory folders while send_from_directory keeps
    # traversal outside the frames folder blocked.
    return send_from_directory(FRAMES_DIR,name)

@app.route('/frames/open', methods=['GET','POST'])
def open_frames_folder():
    FRAMES_DIR.mkdir(parents=True,exist_ok=True)
    opened,errors=open_folder_native(FRAMES_DIR)
    return jsonify(ok=True,opened=opened,folder=str(FRAMES_DIR.resolve()),errors=errors)

@app.get('/stickers')
def stickers():
    return jsonify(build_sticker_library())

@app.get('/sticker/<path:name>')
def sticker_file(name):
    # send_from_directory safely resolves nested relative paths while
    # preventing traversal outside the stickers directory.
    return send_from_directory(STICKERS_DIR,name)

@app.get('/asset/<name>')
def asset(name):
    return send_from_directory(ROOT,name)

@app.get('/fonts')
def fonts():
    return jsonify([{k:f[k] for k in ('id','name','themed','custom')} for f in FONTS])

@app.post('/fonts/refresh')
def fonts_refresh():
    refresh_fonts()
    return fonts()

@app.get('/font/<fid>')
def font_file(fid):
    f=FONT_MAP.get(str(fid))
    if not f:
        return ('not found',404)
    return send_from_directory(Path(f['path']).parent, Path(f['path']).name)

@app.route('/custom-fonts/open', methods=['GET','POST'])
def open_custom_fonts():
    CUSTOM_FONTS.mkdir(parents=True,exist_ok=True)
    opened,errors=open_folder_native(CUSTOM_FONTS)
    return jsonify(ok=True,opened=opened,folder=str(CUSTOM_FONTS.resolve()),errors=errors)

@app.route('/stickers/open', methods=['GET','POST'])
def open_stickers_folder():
    STICKERS_DIR.mkdir(parents=True,exist_ok=True)
    opened,errors=open_folder_native(STICKERS_DIR)
    return jsonify(ok=True,opened=opened,folder=str(STICKERS_DIR.resolve()),errors=errors)

FONTSOURCE_CACHE = {'time':0.0,'data':[]}

def fontsource_catalog():
    now=time.time()
    if FONTSOURCE_CACHE['data'] and now-FONTSOURCE_CACHE['time'] < 3600:
        return FONTSOURCE_CACHE['data']
    data=fetch_json('https://api.fontsource.org/v1/fonts', timeout=30)
    # Keep normal text fonts; icon-only packages are not useful here.
    data=[f for f in data if f.get('family') and f.get('id') and f.get('type') != 'icons']
    data.sort(key=lambda f:str(f.get('family','')).lower())
    FONTSOURCE_CACHE['data']=data
    FONTSOURCE_CACHE['time']=now
    return data

def online_item(f, custom):
    weights=f.get('weights') or [400]
    weight=400 if 400 in weights else weights[0]
    styles=f.get('styles') or ['normal']
    style='normal' if 'normal' in styles else styles[0]
    subsets=f.get('subsets') or ['latin']
    subset=f.get('defSubset') or ('latin' if 'latin' in subsets else subsets[0])
    family=str(f.get('family') or '')
    return {
        'id':str(f.get('id') or ''), 'family':family, 'weight':weight,
        'style':style, 'subset':subset, 'installed':family.lower() in custom,
        'category':str(f.get('category') or '')
    }

def ordered_style_fonts(catalog, category):
    seeds=STYLE_SEEDS.get(category,[])
    by_id={str(f.get('id')):f for f in catalog}
    output=[]; used=set()
    for fid in seeds:
        f=by_id.get(fid)
        if f and fid not in used:
            output.append(f); used.add(fid)
    for fallback in STYLE_FALLBACKS.get(category,[]):
        for f in catalog:
            fid=str(f.get('id'))
            if fid in used:
                continue
            if str(f.get('category') or '') == fallback:
                output.append(f); used.add(fid)
    return output

@app.get('/online-fonts')
def online_fonts():
    q=(request.args.get('q') or '').strip().lower()
    category=(request.args.get('category') or 'horror').strip().lower()
    try:
        page=max(1,int(request.args.get('page') or 1))
        page_size=max(24,min(120,int(request.args.get('page_size') or 96)))
    except Exception:
        page,page_size=1,96
    custom=installed_custom_names()
    try:
        catalog=fontsource_catalog()

        if q:
            matches=[
                f for f in catalog
                if q in str(f.get('family') or '').lower() or q in str(f.get('id') or '').lower()
            ]
        elif category == 'all':
            matches=catalog
        elif category in DIRECT_CATEGORIES:
            real_cat=DIRECT_CATEGORIES[category]
            matches=[f for f in catalog if str(f.get('category') or '') == real_cat]
        elif category in STYLE_SEEDS:
            matches=ordered_style_fonts(catalog,category)
        else:
            matches=ordered_style_fonts(catalog,'horror')

        total=len(matches)
        begin=(page-1)*page_size
        end=begin+page_size
        chunk=matches[begin:end]
        return jsonify(
            ok=True,
            items=[online_item(f,custom) for f in chunk],
            source='search' if q else 'category',
            category=category,
            page=page,
            page_size=page_size,
            total=total,
            has_more=end < total
        )
    except Exception as e:
        return jsonify(
            ok=False,error='Fontsource is unavailable right now: '+str(e),
            items=[],page=1,total=0,has_more=False
        ),502

@app.post('/online-font/install')
def install_online_font():
    fid=(request.get_json(force=True).get('id') or '').strip()
    if not re.fullmatch(r'[a-z0-9-]+',fid):
        return jsonify(ok=False,error='Invalid Fontsource font ID.'),400
    try:
        details=fetch_json('https://api.fontsource.org/v1/fonts/'+fid)
        file_url,ext=pick_static_variant(details)
        family=details.get('family') or fid
        req=urllib.request.Request(file_url,headers={'User-Agent':'Evidence-Photo-Composer/1.0'})
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read(15*1024*1024)
        if not raw:
            raise RuntimeError('Downloaded font file was empty.')
        target=CUSTOM_FONTS/(safe_font_filename(family)+ext.lower())
        target.write_bytes(raw)
        refresh_fonts()
        return jsonify(ok=True,family=family,file=target.name)
    except Exception as e:
        return jsonify(ok=False,error='Could not add that font: '+str(e)),502

@app.post('/font-import')
def font_import():
    f=request.files.get('file')
    if not f:
        return jsonify(ok=False,error='Choose a font or ZIP file first.'),400
    original=Path(f.filename or 'font')
    ext=original.suffix.lower()
    added=[]
    try:
        if ext in {'.ttf','.otf','.ttc'}:
            target=CUSTOM_FONTS/safe_font_filename(original.name)
            f.save(target)
            added.append(target.name)
        elif ext=='.zip':
            raw=f.read()
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for member in z.infolist():
                    p=Path(member.filename)
                    if member.is_dir() or p.suffix.lower() not in {'.ttf','.otf','.ttc'}:
                        continue
                    target=CUSTOM_FONTS/safe_font_filename(p.name)
                    with z.open(member) as srcf, open(target,'wb') as dstf:
                        shutil.copyfileobj(srcf,dstf)
                    added.append(target.name)
        else:
            return jsonify(ok=False,error='Import a .ttf, .otf, .ttc, or .zip file.'),400
        if not added:
            return jsonify(ok=False,error='No supported font files were found.'),400
        refresh_fonts()
        return jsonify(ok=True,added=added,count=len(added))
    except Exception as e:
        return jsonify(ok=False,error='Font import failed: '+str(e)),500


@app.post('/upload')
def upload():
    global current_source
    f=request.files.get('file')
    if not f:
        return jsonify(ok=False,error='No file received.'),400
    ext=Path(f.filename or '').suffix.lower()
    if ext not in {'.png','.jpg','.jpeg','.webp','.bmp'}:
        ext='.png'
    p=UPLOADS/('source_'+uuid.uuid4().hex[:8]+ext)
    f.save(p)
    try:
        im=Image.open(p); im.verify(); im=Image.open(p)
    except Exception:
        p.unlink(missing_ok=True)
        return jsonify(ok=False,error='That file is not a readable image.'),400
    current_source=p
    return jsonify(ok=True,preview='/source/'+p.name,name=f.filename or p.name,width=im.width,height=im.height)

@app.post('/from-url')
def from_url():
    global current_source
    url=(request.get_json(force=True).get('url') or '').strip()
    if not url.lower().startswith(('http://','https://')):
        return jsonify(ok=False,error='Paste a full http:// or https:// image URL.'),400
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read(30*1024*1024)
        im=Image.open(io.BytesIO(raw)).convert('RGBA')
        p=UPLOADS/('source_'+uuid.uuid4().hex[:8]+'.png')
        im.save(p)
        current_source=p
        return jsonify(ok=True,preview='/source/'+p.name,name=Path(url.split('?')[0]).name or 'image.png',width=im.width,height=im.height)
    except Exception as e:
        return jsonify(ok=False,error='Could not download image: '+str(e)),400

@app.get('/source/<name>')
def source(name):
    return send_from_directory(UPLOADS,name)

@app.post('/clear-source')
def clear_source():
    global current_source
    current_source=None
    return jsonify(ok=True)

@app.get('/settings')
def get_settings():
    return jsonify(settings)

@app.post('/settings/update')
def update_settings():
    d=request.get_json(force=True) or {}
    if d.get('preview_background') in {'dark','check','white'}:
        settings['preview_background']=d['preview_background']
    persist_settings()
    return jsonify(ok=True,**settings)

@app.post('/choose-save-folder')
def choose_save_folder():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root=tk.Tk()
        root.withdraw()
        root.attributes('-topmost',True)
        chosen=filedialog.askdirectory(initialdir=settings['save_folder'],title='Choose where finished evidence photos are saved')
        root.destroy()
        if chosen:
            settings['save_folder']=chosen
            Path(chosen).mkdir(parents=True,exist_ok=True)
            persist_settings()
        return jsonify(ok=True,folder=settings['save_folder'],cancelled=not bool(chosen))
    except Exception as e:
        return jsonify(ok=False,error=str(e)),500

@app.post('/open-output-folder')
def open_output_folder():
    p=Path(settings['save_folder']); p.mkdir(parents=True,exist_ok=True)
    opened,errors=open_folder_native(p)
    return jsonify(ok=True,opened=opened,folder=str(p.resolve()),errors=errors)


@app.post('/save-composite')
def save_composite():
    f=request.files.get('file')
    if not f:
        return jsonify(ok=False,error='No rendered image was received.'),400

    label=(request.form.get('label') or 'UNKNOWN').strip()
    auto_name=str(request.form.get('autoName','true')).lower() in {'1','true','yes','on'}
    raw_name=(request.form.get('fileName') or label or 'UNKNOWN').strip()
    transparent=str(request.form.get('transparent','true')).lower() in {'1','true','yes','on'}
    save_raw_project=str(request.form.get('saveRawProject','false')).lower() in {'1','true','yes','on'}
    save_mode=(request.form.get('saveMode') or 'ask').strip().lower()
    if save_mode not in {'ask','overwrite','version'}:
        save_mode='ask'

    project_data_text=''
    project_upload=request.files.get('projectData')
    if project_upload:
        try:
            project_data_text=project_upload.read().decode('utf-8')
        except Exception:
            project_data_text=''
    if not project_data_text:
        project_data_text=(request.form.get('projectData') or '').strip()
    if save_raw_project and not project_data_text:
        return jsonify(ok=False,error='Editable project data was not received. The image was not saved.'),400

    try:
        raw=f.read()
        im=Image.open(io.BytesIO(raw)).convert('RGBA')
    except Exception as e:
        return jsonify(ok=False,error='The rendered PNG could not be read: '+str(e)),400

    if not transparent:
        bg=Image.new('RGBA',im.size,(22,25,27,255))
        bg.alpha_composite(im)
        im=bg

    if auto_name:
        fn=safe_filename(label)
    else:
        if raw_name.lower().endswith('.png'):
            raw_name=raw_name[:-4]
        fn=safe_filename(raw_name)

    dest=Path(settings['save_folder'])
    dest.mkdir(parents=True,exist_ok=True)
    original_stem=Path(fn).stem
    project_folder_name=safe_project_folder_name(original_stem)
    target=dest/fn
    project_dir=RAW_PROJECTS_DIR/project_folder_name

    image_exists=target.exists()
    project_exists=save_raw_project and project_dir.exists()
    if save_mode=='ask' and (image_exists or project_exists):
        suggested=next_version_name(original_stem,dest,include_project=save_raw_project)
        return jsonify(
            ok=False,
            conflict=True,
            filename=fn,
            image_exists=image_exists,
            project_exists=project_exists,
            suggested_filename=suggested+'.png',
            message='A file or editable project with this name already exists.'
        ),409

    if save_mode=='version':
        version_stem=next_version_name(original_stem,dest,include_project=save_raw_project)
        fn=version_stem+'.png'
        project_folder_name=safe_project_folder_name(version_stem)
        target=dest/fn
        project_dir=RAW_PROJECTS_DIR/project_folder_name

    if save_mode=='overwrite' and save_raw_project and project_dir.exists():
        shutil.rmtree(project_dir,ignore_errors=True)

    im.save(target,'PNG')

    raw_project_saved_to=None
    if save_raw_project and project_data_text:
        try:
            project_data=json.loads(project_data_text)
        except Exception:
            project_data={'type':'evidence-photo-project','version':1.1,'raw':project_data_text}

        RAW_PROJECTS_DIR.mkdir(parents=True,exist_ok=True)
        project_dir.mkdir(parents=True,exist_ok=True)

        project_data['type']='evidence-photo-project'
        project_data['version']=1.31
        project_data['savedWith']='Evidence Photo Composer v1.3.1'
        project_data['savedPngName']=fn
        project_data['savedCompositePath']=str(target)
        project_data['savedAt']=time.strftime('%Y-%m-%d %H:%M:%S')
        project_data['projectName']=project_folder_name

        # Store source images once in RAW PROJECTS/SOURCES and keep only a
        # lightweight reference in each project JSON. This allows multiple
        # projects to share the same source without duplicating it.
        src_data=project_data.pop('sourceDataUrl', None)
        source_ref=persist_shared_source(src_data) if src_data else project_data.get('sourceRef')
        if source_ref:
            project_data['sourceRef']=source_ref

        (project_dir/'project.json').write_text(json.dumps(project_data,indent=2), encoding='utf-8')

        # Recent Projects only needs a thumbnail, not another full-size copy.
        preview=im.copy()
        preview.thumbnail((640,640), Image.Resampling.LANCZOS)
        preview.save(project_dir/'preview.png','PNG',optimize=True)

        readme=(
            'EDITABLE PROJECT FOLDER\n'
            '-----------------------\n'
            'project.json = editable project data for reopening inside the composer\n'
            'preview.png = small thumbnail used by the Recent Projects browser\n'
            'Source images are shared in RAW PROJECTS/SOURCES and referenced by project.json.\n'
            'The full saved image lives only in SAVED IMAGES (or your selected output folder).\n'
        )
        (project_dir/'README.txt').write_text(readme, encoding='utf-8')
        raw_project_saved_to=str(project_dir)

    return jsonify(ok=True,filename=fn,saved_to=str(target),preview='/saved/'+fn,raw_project_saved_to=raw_project_saved_to)

@app.get('/projects')
def list_projects():
    RAW_PROJECTS_DIR.mkdir(parents=True,exist_ok=True)
    projects=[]
    for folder in RAW_PROJECTS_DIR.iterdir():
        if not folder.is_dir():
            continue
        project_file=folder/'project.json'
        if not project_file.exists():
            continue
        try:
            data=json.loads(project_file.read_text(encoding='utf-8'))
        except Exception:
            data={}
        stat=project_file.stat()
        saved_at=data.get('savedAt') or time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(stat.st_mtime))
        projects.append({
            'id':folder.name,
            'name':data.get('projectName') or data.get('label') or folder.name,
            'label':data.get('label') or '',
            'saved_at':saved_at,
            'mtime':stat.st_mtime,
            'has_thumbnail':(folder/'preview.png').exists(),
            'saved_png':data.get('savedPngName') or '',
        })
    projects.sort(key=lambda x:x['mtime'],reverse=True)
    for p in projects:
        p.pop('mtime',None)
    return jsonify(ok=True,folder=str(RAW_PROJECTS_DIR.resolve()),projects=projects)

@app.get('/project-data/<path:project_id>')
def get_project_data(project_id):
    folder=project_folder_from_id(project_id)
    if not folder:
        return jsonify(ok=False,error='Invalid project name.'),400
    project_file=folder/'project.json'
    if not project_file.exists():
        return jsonify(ok=False,error='Project not found.'),404
    try:
        data=json.loads(project_file.read_text(encoding='utf-8'))
        # Keep project.json compact: sourceRef points into RAW PROJECTS/SOURCES.
        # Only expand it to a data URL while reopening inside the app.
        if data.get('sourceRef') and not data.get('sourceDataUrl'):
            source_data=source_ref_to_data_url(data.get('sourceRef'))
            if source_data:
                data['sourceDataUrl']=source_data
        return jsonify(ok=True,project=data)
    except Exception as e:
        return jsonify(ok=False,error='Could not read project: '+str(e)),500

@app.get('/project-thumbnail/<path:project_id>')
def get_project_thumbnail(project_id):
    folder=project_folder_from_id(project_id)
    if not folder:
        return Response(status=404)
    thumb=folder/'preview.png'
    if not thumb.exists():
        return Response(status=404)
    return send_from_directory(folder,'preview.png')

@app.post('/open-projects-folder')
def open_projects_folder():
    RAW_PROJECTS_DIR.mkdir(parents=True,exist_ok=True)
    opened,errors=open_folder_native(RAW_PROJECTS_DIR)
    return jsonify(ok=True,opened=opened,folder=str(RAW_PROJECTS_DIR.resolve()),errors=errors)

@app.post('/render')
def render():
    if not current_source or not current_source.exists():
        return jsonify(ok=False,error='Add an image first.'),400

    d=request.get_json(force=True) or {}
    frames, frame_map = get_frames_and_map()
    meta = frame_map.get(d.get('frameId'), frames[0] if frames else DEFAULT_FRAME_META)
    overlay=Image.open(FRAMES_DIR/meta['file']).convert('RGBA')
    l,t,r,b=meta['photo']; ow,oh=r-l,b-t
    src=Image.open(current_source).convert('RGBA')
    opening=transform_source(
        src,ow,oh,d.get('panX',0),d.get('panY',0),d.get('zoom',1),
        d.get('fitMode','fill'),d.get('imgRot',0)
    )
    final=Image.new('RGBA',overlay.size,(0,0,0,0))
    final.alpha_composite(opening,(l,t))
    final.alpha_composite(overlay)

    # Main label.
    label=(d.get('label') or 'UNKNOWN').strip()
    text=label.upper() if d.get('uppercase',False) else label
    fs=max(10,min(400,int(float(d.get('fontSize',72)))))
    font=get_font(d.get('fontId','0'),fs)
    text_color=parse_hex_color(d.get('textColor','#181510'))
    text_opacity=max(0,min(255,round(float(d.get('textOpacity',100))*2.55)))
    layer=styled_text_layer(
        (max(1500,overlay.width*2),max(420,fs*5)),text,font,
        bool(d.get('bold')),bool(d.get('italic')),bool(d.get('shadow')),
        text_color,text_opacity
    )
    layer=layer.rotate(float(d.get('labelRot',0)),resample=Image.Resampling.BICUBIC,expand=False)
    lx=float(d.get('labelX',meta['labelDefault'][0]))
    ly=float(d.get('labelY',meta['labelDefault'][1]))
    final.alpha_composite(layer,(int(lx*overlay.width-layer.width/2),int(ly*overlay.height-layer.height/2)))

    # Optional additional text lines, using the same selected font.
    extras = d.get('extras') or []
    if not extras and d.get('extraEnabled') and str(d.get('extraText') or '').strip():
        extras = [{
            'text': d.get('extraText'),
            'fontSize': d.get('extraFontSize', 34),
            'x': d.get('extraX', .5),
            'y': d.get('extraY', .94),
            'rot': d.get('extraRot', 0),
            'shadow': d.get('extraShadow', False),
        }]

    if isinstance(extras, list):
        for item in extras:
            if not isinstance(item, dict):
                continue
            extra = str(item.get('text') or '').strip()
            if not extra:
                continue
            efs=max(8,min(300,int(float(item.get('fontSize',34)))))
            efont=get_font(item.get('fontId',d.get('fontId','0')),efs)
            extra_color=parse_hex_color(item.get('color',d.get('textColor','#181510')))
            extra_opacity=max(0,min(255,round(float(item.get('opacity',d.get('textOpacity',100)))*2.55)))
            elayer=styled_text_layer(
                (max(1500,overlay.width*2),max(360,efs*5)),extra,efont,
                False,False,bool(item.get('shadow')),
                extra_color,extra_opacity
            )
            elayer=elayer.rotate(float(item.get('rot',0)),resample=Image.Resampling.BICUBIC,expand=False)
            ex=float(item.get('x',.5)); ey=float(item.get('y',.94))
            final.alpha_composite(elayer,(int(ex*overlay.width-elayer.width/2),int(ey*overlay.height-elayer.height/2)))

    if not d.get('transparent',True):
        bg=Image.new('RGBA',final.size,(22,25,27,255))
        bg.alpha_composite(final)
        final=bg

    if d.get('autoName',True):
        fn=safe_filename(label)
    else:
        raw=(d.get('fileName') or label or 'UNKNOWN').strip()
        if raw.lower().endswith('.png'):
            raw=raw[:-4]
        fn=safe_filename(raw)

    dest=Path(settings['save_folder'])
    dest.mkdir(parents=True,exist_ok=True)
    target=dest/fn
    final.save(target,'PNG')
    return jsonify(ok=True,filename=fn,saved_to=str(target),preview='/saved/'+fn)

@app.get('/saved/<name>')
def saved(name):
    # Serve the actual saved image directly instead of keeping a duplicate cache.
    return send_from_directory(Path(settings['save_folder']),name)

def launch_window():
    time.sleep(.9)
    url=f'http://127.0.0.1:{PORT}'
    if os.name=='nt':
        candidates=[
            Path(os.environ.get('PROGRAMFILES(X86)',''))/'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('PROGRAMFILES',''))/'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('LOCALAPPDATA',''))/'Microsoft/Edge/Application/msedge.exe',
            Path(os.environ.get('PROGRAMFILES',''))/'Google/Chrome/Application/chrome.exe',
            Path(os.environ.get('PROGRAMFILES(X86)',''))/'Google/Chrome/Application/chrome.exe',
        ]
        for exe in candidates:
            if exe.exists():
                try:
                    subprocess.Popen([str(exe),f'--app={url}','--start-maximized','--new-window'])
                    return
                except Exception:
                    pass
    try:
        webbrowser.open(url)
    except Exception:
        pass

if __name__=='__main__':
    print('Evidence Photo Composer -> http://127.0.0.1:5000')
    print('Keep this window open while using the composer.')
    threading.Thread(target=launch_window,daemon=True).start()
    app.run(host='127.0.0.1',port=PORT,debug=False)
