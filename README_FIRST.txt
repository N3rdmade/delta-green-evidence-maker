EVIDENCE PHOTO COMPOSER v1.3
============================

A local browser-based photo / evidence / prop composer.

START
-----
1. Run START.bat on Windows.
2. The launcher checks for Python and required Python packages automatically.
3. The app opens locally in your browser.
4. Choose a frame, set the optional Background Box, add an image, add text/stickers/layer images, and save.

FOLDERS
-------
frames          Frame image files. New supported image files placed here are discovered when the app starts.
stickers        Sticker image files. New PNG/WebP/JPG sticker files are discovered when the app starts.
custom_fonts    Composer-installed fonts.
SAVED IMAGES    Included convenience folder. By default, final PNG exports now go to the parent "Delta Green" folder containing Evidence_Maker_V2; you can choose another output folder in Save Options.
RAW PROJECTS    Editable projects saved when "Also save editable project" is checked.
RAW PROJECTS/SOURCES
                Shared source-image library used by editable projects so identical sources do not need to be copied into every project folder.

EDITABLE PROJECTS
-----------------
Each editable project gets its own folder inside RAW PROJECTS. A project folder contains:
- project.json: editable project state
- preview.png: small Recent Projects thumbnail
- README.txt: short project-folder explanation

The final full-resolution PNG is saved to the portable default output (the parent folder containing Evidence_Maker_V2) or to the folder you choose in Save Options.
Source images are stored once in RAW PROJECTS/SOURCES and referenced by project.json.
Use the Projects button in the top bar to reopen recent projects.

PROJECT STATE
-------------
Editable project JSON stores the frame, matte/background box, the main image placement area captured when the image was imported, image pan/zoom/rotation, text positions and formatting, layer order/names/visibility/locks, sticker and imported-image transformations, and save settings.

BACKGROUND BOX / IMAGE PLACEMENT
--------------------------------
Set the Background Box before adding an image when you want the image to initially fit that area. The matte can remain the classic black box, use a separate image as its background, or use Triangle / Circle / Hexagon shapes. The Position & Size sliders are collapsible, and the purple edit overlay has move, rotate/tilt, uniform-scale, and squish/stretch controls.
When a main image is imported, its image-placement area, rotation, and shape are captured once. Later changing the matte does not move or reshape that already-imported image.
Images imported from the Layers + menu also auto-fit to the current matte when they are first created, then remain independently editable.

OVERWRITE PROTECTION
--------------------
If an image or editable project with the same name already exists, the app asks before replacing it.
Choose Overwrite to replace the existing files, or Save as New Version to create v2, v3, and so on.

NOTES
-----
- The app runs locally on your computer.
- Online font browsing requires an internet connection.
- The editable-project checkbox starts unchecked each launch.
- PNG transparency is preserved when transparency saving is enabled.

STICKER CATEGORIES (v1.3)
-------------------------
The stickers folder is now the category system. No config file is required.

  stickers\Loose_Sticker.png
  stickers\Stamps\Classified.png
  stickers\Evidence\Fingerprints\Print_01.png

Top-level folders become Categories. Folders inside them become Subcategories.
ALL STICKERS shows every supported image recursively, including loose files in
the main stickers folder. Click Refresh in the sticker browser after adding,
moving, or renaming sticker files/folders. Editable RAW PROJECTS save each
sticker's relative folder path so the correct nested asset reopens later.



FRAME CATEGORIES
----------------
The frames folder now mirrors the sticker category system. Top-level folders become frame Categories and nested folders become Subcategories. ALL FRAMES still shows every frame recursively, and hover-to-preview remains available after filtering.
