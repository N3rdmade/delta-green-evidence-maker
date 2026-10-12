## v129 — Crash recovery and workspace backups

- Autosave unfinished work to device-local IndexedDB, debounced after editing stops with periodic checkpoints.
- Prompt to restore the latest recovery snapshot on return.
- Add visible warnings about the risks of clearing browser site data.
- Back up all browser projects, old and new imported frames/stickers, source images, and custom fonts into a selected local workspace.
- Create Backups/Autosave and mirror recovery snapshots there when workspace access is available.
- Remember the user's workspace directory handle where browser permissions allow; do not assume permission after restart.

## v128 — Flattened images and local workspace

- Re-encode normal PNG exports as a single bitmap, retaining transparency if selected.
- Add one optional private workspace folder with nested Projects, Exports and Assets folders.
- Keep uploaded image assets and source images in per-browser storage or the selected device folder, not GitHub.
- Preserve old imported assets through compatible reads and separate new asset stores.

## v44 — Project reopen regression fix

- Save portable project resources with browser project records, not only downloaded backups.
- Route reopening through the browser adapter explicitly.
- Fail browser smoke tests immediately with the reported project error instead of a silent timeout.
- Keep the v42 desktop editor unchanged.

# Changelog

## v43 — Browser edition

- Added a static build that retains the v42 editor and original desktop app.
- Replaced server storage with browser project storage, PNG downloads, and optional directory selection.
- Added portable project backups and import of desktop RAW PROJECTS folders.
- Added browser asset/font import, including font ZIPs, and direct Fontsource access.
- Added automatic GitHub Pages deployment gated by browser tests.

## v42 — GitHub baseline

- Imported application source and asset libraries from the v42 archive.
- Preserved the existing shape-editor and frame-loading save fixes.
- Excluded personal projects, generated output, uploads, caches, and local settings.
- Added repository documentation and ignore rules.
- No application behavior changes. Browser-only hosting is not yet implemented.
