# Delta Green Evidence Maker

A handout and evidence image composer for Delta Green games.

## Current version: v42

This repository starts from Evidence_Maker_V2_updated_v42.zip. The application source, frames, stickers, and bundled fonts are preserved. Personal saved projects, exported images, temporary uploads, and machine-specific settings are excluded.

### Run on Windows

Run **START.bat**. The launcher finds or installs Python and the required dependencies, then starts the local application.

### Run with Python

Install the dependencies and launch the app:

```sh
python -m pip install -r requirements.txt
python photo_composer.py
```

The app runs a local Flask server and opens its browser interface. Keep the server running while editing.

## Browser-only version

Planned, not implemented in this baseline. Uploading this app to GitHub Pages alone will not run it: the interface currently calls Flask endpoints for image processing, libraries, and saving.

The browser adaptation will investigate Pyodide/Pillow for image processing and browser-compatible project import, storage, and export. The v42 local application remains the reference version.

## Updates

Changes are tracked in Git commits rather than replacement ZIP files. Commit messages identify changes; CHANGELOG.md records user-visible updates.

## Bundled assets

The repository's code license does not establish ownership of third-party fonts, logos, or artwork. Their respective rights and licenses still apply.
