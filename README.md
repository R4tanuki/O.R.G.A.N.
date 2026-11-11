# O.R.G.A.N.
### O.R.G.A.N. stands for Orchestrate Resources, Game files And Nodes... hehe.

## Master controller for for Guilty Gear rigs in Blender, built on Aerthas Veras and the ArcSys Blender Discord server's combined work.

# Features

## Main Panel
Show all armatures: sets every armature in the project to Textured display and enables In Front.

## Texture Controls
Set Alpha to Channel Packed: applies Channel Packed alpha to the textures in the base and sss image texture nodes inside both Strive and Xrd shaders.
Fix ILM: sets ILM textures to the Linear Rec.709 color space, with alpha Straight.
Fix Decal: same as Fix ILM for decal textures, and also sets their materials to Blended, with transparent shadows and transparency overlap. This is a personal preference. I just think dirthered looks nasty.
Refresh Textures: reloads every file-based image in the project from disk. Skips images with unsaved changes or whose file is missing, and reports them. Useful when you edit textures in other programs.

## Color Palettes
Auto format palette textures: renames _base / _sss palette textures to their usable number (SOL_base → SOL1_base, SOL_base.001 → SOL2_base, etc.). It's meant to complement the MasterGhost series' Palette Switcher. 

## Import Controls
Rig selector: chooses the armature to act on when none is selected.
Fix Armature: sets the selected rigs (or the one chosen in the selector) to Stick display with In Front.
Select all armatures: checkbox to select every selectable armature.
Hide armature: checkbox to hide/show the target armatures.
Fix Mirroring: renames bones and vertex groups of the selected armatures and meshes to follow the _L / _R convention, using a long table of renaming rules. I quite literally embedded an already existing script posted in the server.

## Shader Import
Strive Shader: imports the node groups and the Sun object from a .blend embedded in the script, and overwrites the active object’s active material with the Strive setup (empty image nodes in labeled frames, colored main group node, etc.).
Xrd Shader: Same but with Xrd.
Both reuse existing node groups if they are already in the project, and remove the junk material_preview_dummy object that Blender creates.

## Notes
The embedded shaders were saved with Blender 5.2, so they may not load in older versions (they WON'T work in older versions).
All of these things work according to the way I (ME !!) work, so they might actually feel clunky or straight up unnecessary to you.
