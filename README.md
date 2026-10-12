# Delta Green Evidence Maker

**[Open the Evidence Maker](https://n3rdmade.github.io/delta-green-evidence-maker/)**

A browser-based editor for creating Delta Green handouts, case files, vintage photo evidence, and other investigation props. **No software installation required.**

## Using the editor

Choose a frame, upload your photo, customize its placement, then export a flattened PNG. The editor supports stickers, masks, punches, text, visual effects, imported fonts, and editable projects.

- **Frames and stickers:** Everyone sees the built-in collection. Your personal uploads remain in **your own browser**, not in GitHub.
- **Categories:** Folder names under `frames/` and `stickers/` become the main categories. Nested folders become subcategories automatically on the next site build.
- **Recent projects and recovery:** Stored locally in your browser with autosave snapshots. Clearing **site data** may erase locally saved work.
- **Workspace backup:** In supported browsers, choose a local workspace folder to save exports, projects, custom assets, fonts, and recovery snapshots to separate organized folders. Without one, exports use Downloads.
- **PNG export:** Flattened image with optional transparency; editable data is saved separately as a project backup.

## Repo layout

```text
.github/workflows/pages.yml    GitHub Pages build and deployment
src/editor.html                Active editor source
browser/adapter.js             Local browser storage and file handling
frames/                        Built-in frames (folders = categories)
stickers/                      Built-in stickers (folders = categories)
custom_fonts/                  Built-in fonts
frames.json                    Original frame placement metadata
evidence_frames.json           New evidence frame photo-opening metadata
evidence_frame_library.zip     Pack of 21 published evidence frames
scripts/build_browser.py       Static website builder and category discovery
scripts/test_browser.cjs       Browser regression tests
photo_composer.py              Frame/sticker library metadata functions
```

**The ZIP in the repository is an asset pack processed automatically at build time**, not a program installer. `evidence_frame_additions.zip` can be added later to publish the remaining nine artwork designs.

There are no Windows launchers or retired-version folders in the current source tree. Old commits remain accessible through Git history.

## Adding shared frames or stickers

Place new image files in the appropriate folder and commit:

```text
frames/
  Newspaper/
    Clippings/
      torn-article.webp
  Polaroids/
    vintage-polaroid.png
  Notes & Journals/
    notebook-page.webp
stickers/
  Stamps/
    confidential.png
```

The next successful GitHub Pages build discovers new category names and subcategories automatically. **No hardcoded category list is required.**

For frames, transparent photo windows are important. To specify exact photo-placement coordinates or a custom frame name, add an entry to `evidence_frames.json` (or `frames.json` for original frames). The editor also discovers unregistered frames, but uses a default photo-placement box for those.

## Building and testing locally

Requires Python 3.12+ and Node.js 22+ for testing; **visitors don't need either**.

```bash
python scripts/build_browser.py
python -m http.server 8765
```

Open `http://localhost:8765/_site/`.

Browser smoke tests (with the server running):

```bash
npm install --no-save --package-lock=false playwright@1.62.1
npx playwright install chromium
node scripts/test_browser.cjs
```

Pushes to `main` trigger GitHub Actions, which builds, tests and publishes the site. Check the [Actions page](https://github.com/N3rdmade/delta-green-evidence-maker/actions).

## Privacy and backups

The GitHub Pages website serves public built-in assets but **does not upload visitor images or projects to your repository**. Imported files and editable projects stay on the user's device. For long-term protection, select a local Workspace Folder or export project backups. Browser storage is not a permanent cloud backup.

## Licensing

See [LICENSE](LICENSE). Bundled assets and third-party fonts may have separate rights and licensing terms.
