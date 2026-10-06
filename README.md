# Delta Green Evidence Maker

A handout and evidence image composer for Delta Green games.

## v43 — Browser edition

The browser edition preserves the v42 editor, including its shape controls and frame-loading save fix. It runs entirely in the browser: no Python installation or separate server is required.

- 44 frames and 58 stickers, plus image, frame, sticker, and font import.
- PNG downloads with transparent or opaque backgrounds.
- Editable projects saved on this device using browser storage.
- **Export Project** downloads a portable JSON backup with source images, used fonts, and imported assets. **Import Project** reopens it.
- **Import Desktop Folder** reads older project folders. Select the full **RAW PROJECTS** folder so referenced images in **SOURCES** are available.
- **Choose Folder** writes PNGs directly to a selected folder in supporting browsers. Otherwise PNGs use browser downloads.
- Online fonts use Fontsource. Image URLs must permit browser access; when a host blocks access, download the image and upload it instead.

Browser projects are not uploaded to GitHub or synchronized between devices. Clearing site data removes browser saves. Export project backups for work you want to keep. Browsers cannot automatically enumerate Windows fonts; use the bundled fonts or import your own font files.

In Downloads mode, Overwrite replaces the browser project but starts a new download; your browser may number the PNG filename. A selected output folder supports direct replacement.

### Publishing

The **Publish browser edition** GitHub Actions workflow builds the site, runs browser smoke tests, and then deploys it. Enable **Settings → Pages → Source → GitHub Actions** once. Pushes to main subsequently update the site automatically.

Expected site address after deployment: https://n3rdmade.github.io/delta-green-evidence-maker/

### Build and preview

```sh
python scripts/build_browser.py
python -m http.server 8765 --directory _site
```

Open http://localhost:8765/. The builder adapts the reference editor into a static site. Add repository assets under frames/, stickers/, or custom_fonts/ and rebuild.

### Browser smoke tests

```sh
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install chromium
node scripts/test_browser.cjs
```

Run the preview server first. Tests cover loading, image upload, shape/sticker state, PNG export, project persistence/reopen, conflicts/versioning, and portable import. Set EVIDENCE_TEST_URL to test a subpath or deployed version.

## Original local Python app (v42)

The original index.html and photo_composer.py remain unchanged. On Windows, run **START.bat**, or:

```sh
python -m pip install -r requirements.txt
python photo_composer.py
```

## Bundled assets

The repository's code license does not establish ownership of third-party fonts, logos, or artwork. Their respective rights and licenses still apply.
