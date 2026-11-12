bl_info = {
    "name": "O.R.G.A.N.",
    "author": "Ratanuki",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar (N) > O.R.G.A.N.",
    "description": "Personal addon to automatize tedious task when working with ArcSys models.",
    "category": "Object",
}

# I MADE THIS ACCORDING TO HOW I WORK !! 
# I can't guarantee it will work 100% as properly intended with you because I'm not familiar with your game.

import os
import re

import bpy


class ORGAN_OT_show_all_armatures(bpy.types.Operator):
    """Set every armature in the project to 'Textured' and enable 'In Front'"""
    bl_idname = "organ.show_all_armatures"
    bl_label = "Show all armatures"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        count = 0
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                obj.display_type = 'TEXTURED'
                obj.show_in_front = True  # "In Front" (bones always drawn on top)
                count += 1

        if count == 0:
            self.report({'WARNING'}, "No armatures found in the project")
            return {'CANCELLED'}

        # Redraw all areas
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

        self.report({'INFO'}, f"{count} armature(s) set to Textured")
        return {'FINISHED'}


TEXTURE_KEYWORDS = ("base", "sss")


def _node_text(node, tree_name):
    """Lowercase text used to identify which group an image node belongs to:
    image name, node name/label, parent frame name/label and node group name."""
    candidates = [node.name, node.label, node.image.name if node.image else ""]
    if node.parent:
        candidates += [node.parent.name, node.parent.label]
    if tree_name:
        candidates.append(tree_name)
    return " ".join(candidates).lower()


def _matches_group(node, tree_name):
    """True if the image node belongs to a 'base' or 'sss' group."""
    text = _node_text(node, tree_name)
    return any(key in text for key in TEXTURE_KEYWORDS)


_ILM_RE = re.compile(r"(?<![a-z])ilm(?![a-z])")


def _matches_ilm(node, tree_name):
    """True if the image node is an ILM texture."""
    return bool(_ILM_RE.search(_node_text(node, tree_name)))


def _linear_colorspace_name(image):
    """Return the linear color space name available in this Blender version."""
    items = image.colorspace_settings.bl_rna.properties['name'].enum_items
    available = {item.identifier for item in items}
    for name in ("Linear Rec.709", "Linear"):
        if name in available:
            return name
    return None


def _apply_linear_straight(image):
    """Set a linear Color Space and Straight Alpha. Return True if anything changed."""
    modified = False
    linear = _linear_colorspace_name(image)
    if linear and image.colorspace_settings.name != linear:
        image.colorspace_settings.name = linear
        modified = True
    if image.alpha_mode != 'STRAIGHT':
        image.alpha_mode = 'STRAIGHT'
        modified = True
    return modified


_DECAL_RE = re.compile(r"(?<![a-z])decals?(?![a-z])")


def _matches_decal(node, tree_name):
    """True if the image node is a decal texture."""
    return bool(_DECAL_RE.search(_node_text(node, tree_name)))


def _material_has_match(tree, matcher, group_name=None, visited=None):
    """True if the tree (or any nested group) contains an image node accepted by matcher."""
    if visited is None:
        visited = set()
    if tree is None or tree.name in visited:
        return False
    visited.add(tree.name)
    for node in tree.nodes:
        if node.type == 'TEX_IMAGE' and node.image is not None and matcher(node, group_name):
            return True
        if node.type == 'GROUP' and node.node_tree is not None:
            if _material_has_match(node.node_tree, matcher, node.node_tree.name, visited):
                return True
    return False


def _set_blended(material):
    """Set Render Method to Blended (plus Transparent Shadows and Transparency Overlap)."""
    changed = False
    if hasattr(material, "surface_render_method"):  # Blender 4.2+
        if material.surface_render_method != 'BLENDED':
            material.surface_render_method = 'BLENDED'
            changed = True
        if hasattr(material, "use_transparent_shadow") and not material.use_transparent_shadow:
            material.use_transparent_shadow = True
            changed = True
        if hasattr(material, "use_transparency_overlap") and not material.use_transparency_overlap:
            material.use_transparency_overlap = True
            changed = True
    elif hasattr(material, "blend_method"):  # Blender < 4.2
        if material.blend_method != 'BLEND':
            material.blend_method = 'BLEND'
            changed = True
    return changed


def _iter_node_trees():
    """Yield all node trees: materials and node groups (with their group name)."""
    for mat in bpy.data.materials:
        if mat.use_nodes and mat.node_tree:
            yield mat.node_tree, None
    for group in bpy.data.node_groups:
        if group.bl_idname == 'ShaderNodeTree':
            yield group, group.name


class ORGAN_OT_set_alpha_channel_packed(bpy.types.Operator):
    """Set Alpha to 'Channel Packed' on the textures of the 'base' and 'sss' groups"""
    bl_idname = "organ.set_alpha_channel_packed"
    bl_label = "Set Alpha to Channel Packed"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        changed = set()
        found = set()

        for tree, group_name in _iter_node_trees():
            for node in tree.nodes:
                if node.type != 'TEX_IMAGE' or node.image is None:
                    continue
                if not _matches_group(node, group_name):
                    continue
                found.add(node.image.name)
                if node.image.alpha_mode != 'CHANNEL_PACKED':
                    node.image.alpha_mode = 'CHANNEL_PACKED'
                    changed.add(node.image.name)

        if not found:
            self.report({'WARNING'}, "No 'base' or 'sss' textures found")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"{len(changed)} image(s) set to Channel Packed ({len(found)} found)"
        )
        return {'FINISHED'}


class ORGAN_OT_fix_ilm(bpy.types.Operator):
    """Set ILM textures to Color Space 'Linear Rec.709' and Alpha 'Straight'"""
    bl_idname = "organ.fix_ilm"
    bl_label = "Fix ILM"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        found = set()
        changed = set()

        for tree, group_name in _iter_node_trees():
            for node in tree.nodes:
                if node.type != 'TEX_IMAGE' or node.image is None:
                    continue
                if not _matches_ilm(node, group_name):
                    continue

                found.add(node.image.name)
                if _apply_linear_straight(node.image):
                    changed.add(node.image.name)

        if not found:
            self.report({'WARNING'}, "No ILM textures found")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"ILM: {len(changed)} image(s) fixed ({len(found)} found)"
        )
        return {'FINISHED'}


class ORGAN_OT_fix_decal(bpy.types.Operator):
    """Set decal textures to Color Space 'Linear Rec.709' and Alpha 'Straight', and their materials to Blended"""
    bl_idname = "organ.fix_decal"
    bl_label = "Fix Decal"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        found = set()
        changed = set()

        for tree, group_name in _iter_node_trees():
            for node in tree.nodes:
                if node.type != 'TEX_IMAGE' or node.image is None:
                    continue
                if not _matches_decal(node, group_name):
                    continue
                found.add(node.image.name)
                if _apply_linear_straight(node.image):
                    changed.add(node.image.name)

        mats_changed = 0
        for mat in bpy.data.materials:
            if mat.use_nodes and _material_has_match(mat.node_tree, _matches_decal):
                if _set_blended(mat):
                    mats_changed += 1

        if not found:
            self.report({'WARNING'}, "No decal textures found")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Decal: {len(changed)} image(s) and {mats_changed} material(s) fixed "
            f"({len(found)} image(s) found)"
        )
        return {'FINISHED'}


class ORGAN_OT_refresh_textures(bpy.types.Operator):
    """Reload every image in the project from disk (e.g. after editing it in an external program)"""
    bl_idname = "organ.refresh_textures"
    bl_label = "Refresh Textures"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        reloaded = 0
        unsaved = 0
        missing = 0
        candidates = 0

        for img in bpy.data.images:
            # Only images backed by a file on disk (skip generated, viewer, packed and linked ones)
            if img.source not in {'FILE', 'SEQUENCE', 'MOVIE', 'TILED'}:
                continue
            if img.packed_file is not None or img.library is not None or not img.filepath:
                continue
            candidates += 1

            # Reloading would discard changes made inside Blender that were never saved
            if img.is_dirty:
                unsaved += 1
                continue

            # UDIM tiles use a <UDIM> token in the path, so the file check doesn't apply
            if img.source != 'TILED':
                path = bpy.path.abspath(img.filepath, library=img.library)
                if not os.path.isfile(path):
                    missing += 1
                    continue

            img.reload()
            reloaded += 1

        if candidates == 0:
            self.report({'WARNING'}, "No file-based textures found in the project")
            return {'CANCELLED'}

        # Redraw all areas so the updated textures show up
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

        msg = f"{reloaded} texture(s) refreshed"
        if unsaved:
            msg += f", {unsaved} skipped (unsaved changes in Blender)"
        if missing:
            msg += f", {missing} skipped (file not found)"
        self.report({'WARNING'} if (unsaved or missing) else {'INFO'}, msg)
        return {'FINISHED'}


# Color Palettes 

# Blender duplicate suffix: ".001", ".002", ...
_DUP_SUFFIX_RE = re.compile(r"\.(\d{3,})$")
# PREFIX_base / PREFIX_sss (with optional extension, e.g. ".tga")
_PALETTE_RE = re.compile(
    r"^(?P<prefix>.+?)_(?P<kind>base|sss)(?P<ext>\.[A-Za-z0-9]+)?$", re.IGNORECASE
)
# Prefix that already ends in a number (already formatted): SOL1, SOL_DI2...
_NUMBERED_PREFIX_RE = re.compile(r"^(?P<base>.+?)(?P<num>\d+)$")


class ORGAN_OT_format_palette_textures(bpy.types.Operator):
    """Rename palette textures (_base / _sss) to their usable number:
    SOL_base -> SOL1_base, SOL_base.001 -> SOL2_base, SOL_DI_sss.002 -> SOL_DI3_sss..."""
    bl_idname = "organ.format_palette_textures"
    bl_label = "Auto format palette textures"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        entries = []   
        used = {}      

        for img in bpy.data.images:
            if img.library is not None:  
                continue

            name = img.name
            dup = _DUP_SUFFIX_RE.search(name)
            suffix = int(dup.group(1)) if dup else 0
            stem = name[:dup.start()] if dup else name

            match = _PALETTE_RE.match(stem)
            if not match:
                continue

            prefix = match.group("prefix")
            numbered = _NUMBERED_PREFIX_RE.match(prefix)
            if numbered:
                # Already formatted 
                used.setdefault(numbered.group("base"), set()).add(int(numbered.group("num")))
                continue

            entries.append((prefix, suffix, img, match.group("kind"), match.group("ext") or ""))

        # One shared number for all textures 
        numbers = {}
        for prefix, suffix in sorted({(e[0], e[1]) for e in entries}):
            taken = used.setdefault(prefix, set())
            number = suffix + 1
            while number in taken:
                number += 1
            taken.add(number)
            numbers[(prefix, suffix)] = number

        renamed = 0
        skipped = 0
        for prefix, suffix, img, kind, ext in sorted(entries, key=lambda e: (e[0], e[1])):
            new_name = f"{prefix}{numbers[(prefix, suffix)]}_{kind}{ext}"
            existing = bpy.data.images.get(new_name)
            if existing is not None and existing is not img:
                skipped += 1
                continue
            img.name = new_name
            renamed += 1

        if renamed == 0 and skipped == 0:
            self.report({'WARNING'}, "No palette textures found to format")
            return {'CANCELLED'}

        msg = f"{renamed} palette texture(s) renamed"
        if skipped:
            msg += f" ({skipped} skipped due to name conflicts)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


# Import Controls

def _rig_poll(self, obj):
    return obj.type == 'ARMATURE'


def _selectable_armatures():
    """Armature objects of the current view layer that can be selected."""
    return [
        obj for obj in bpy.context.view_layer.objects
        if obj.type == 'ARMATURE' and obj.visible_get() and not obj.hide_select
    ]


def _get_select_all_armatures(self):
    armatures = _selectable_armatures()
    return bool(armatures) and all(obj.select_get() for obj in armatures)


def _set_select_all_armatures(self, value):
    for obj in _selectable_armatures():
        obj.select_set(bool(value))


def _target_rigs(context=None):
    """The armatures the Import Controls act on: every selected armature, or the rig chosen
    in the selector when no armature is selected."""
    context = context or bpy.context
    selected = [obj for obj in (getattr(context, "selected_objects", None) or [])
                if obj.type == 'ARMATURE']
    if selected:
        return selected
    rig = context.scene.organ_rig
    return [rig] if rig is not None else []


def _get_hide_armature(self):
    rigs = _target_rigs()
    return bool(rigs) and all(rig.display_type == 'BOUNDS' for rig in rigs)


def _set_hide_armature(self, value):
    for rig in _target_rigs():
        rig.display_type = 'BOUNDS' if value else 'TEXTURED'


class ORGAN_OT_fix_armature(bpy.types.Operator):
    """Set the selected rigs (or the rig chosen in the selector, if none is selected) to Display As 'Stick' and enable 'In Front'"""
    bl_idname = "organ.fix_armature"
    bl_label = "Fix Armature"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_target_rigs(context))

    # Stop checking my code. I get embarrased.......

    def execute(self, context):
        rigs = _target_rigs(context)
        if not rigs:
            self.report({'WARNING'}, "Select an armature or choose a rig first")
            return {'CANCELLED'}

        for rig in rigs:
            rig.data.display_type = 'STICK'
            rig.show_in_front = True

        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

        if len(rigs) == 1:
            self.report({'INFO'}, f"'{rigs[0].name}' set to Stick + In Front")
        else:
            self.report({'INFO'}, f"{len(rigs)} rigs set to Stick + In Front")
        return {'FINISHED'}


# Fix Mirroring: rules taken from the "Mirroring Overhaul" script.
# Each rule is [text to find, suffix to append]: the found text is removed from the
# name and the suffix is added at the end (e.g. "Arm_R_" -> "Arm_R").
BONE_RENAME = [
    ["_R_","_R"],
    ["_L_","_L"],
    ["R ","_R"],
    ["L ","_L"],
    ["_Right_","_R"],
    ["_Left_","_L"],
    ["Right ","_R"],
    ["Left ","_L"],
    ["_R1","1_R"],
    ["_L1","1_L"],
    ["_R2","2_R"],
    ["_L2","2_L"],
    ["_R3","3_R"],
    ["_L3","3_L"],
    ["_R4","4_R"],
    ["_L5","5_L"],
    ["_R6","6_R"],
    ["_L6","6_L"],
    ["_R7","7_R"],
    ["_L7","7_L"],
    ["_R4_","4_R"],
    ["_L4_","4_L"],
    ["_R5_","5_R"],
    ["_L5_","5_L"],
    ["_R6_","6_R"],
    ["_L6_","6_L"],
    ["_R01","01_R"],
    ["_L01","01_L"],
    ["_R02","02_R"],
    ["_L02","02_L"],
    ["_R03","03_R"],
    ["_L03","03_L"],
    ["_R04","04_R"],
    ["_L05","05_L"],
    ["_R06","06_R"],
    ["_L06","06_L"],
    ["_R07","07_R"],
    ["_L07","07_L"],
    ["_R04_","04_R"],
    ["_L04_","04_L"],
    ["_R05_","05_R"],
    ["_L05_","05_L"],
    ["_R06_","06_R"],
    ["_L06_","06_L"],
    ["_FR01","F01_R"],
    ["_FL01","F01_L"],
    ["_FR02","F02_R"],
    ["_FL02","F02_L"],
    ["_FR03","F03_R"],
    ["_FL03","F03_L"],
    ["_FR04","F04_R"],
    ["_FL05","F05_L"],
    ["_FR06","F06_R"],
    ["_FL06","F06_L"],
    ["_FR07","F07_R"],
    ["_FL07","F07_L"],
    ["_FR04_","F04_R"],
    ["_FL04_","F04_L"],
    ["_FR05_","F05_R"],
    ["_FL05_","F05_L"],
    ["_FR06_","F06_R"],
    ["_FL06_","F06_L"],
    ["_Llow","_low_L"],
    ["_Rlow","_low_R"],
    ["_Lup","_up_L"],
    ["_Rup","_up_R"],
    ["_Lin_tip ","_in_tip_L"],
    ["_Rin_tip ","_in_tip_R"],
    ["_Lin","_in_L"],
    ["_Rin","_in_R"],
    ["_Lmid","_mid_L"],
    ["_Rmid","_mid_R"],
    ["_Lout","_out_L"],
    ["_Rout","_out_R"],
    ["_Lout_tip","_out_tip_L"],
    ["_Rout_tip","_out_tip_R"],
    ["_Lupout","_upout_L"],
    ["_Rupout","_upout_R"],
    ["_Llowout","_lowout_L"],
    ["_Rlowout","_lowout_R"],
    ["_Lupin","_upin_L"],
    ["_Rupin","_upin_R"],
    ["_Llowin","_lowin_L"],
    ["_Rlowin","_lowin_R"],
    ["_FRin1_","_Fin1_R"],
    ["_FRin2_","_Fin2_R"],
    ["_FRin3_","_Fin3_R"],
    ["_FRin4_","_Fin4_R"],
    ["_FRin5_","_Fin5_R"],
    ["_FRin6_","_Fin6_R"],
    ["_FLin1_","_Fin1_L"],
    ["_FLin2_","_Fin2_L"],
    ["_FLin3_","_Fin3_L"],
    ["_FLin4_","_Fin4_L"],
    ["_FLin5_","_Fin5_L"],
    ["_FLin6_","_Fin6_L"],
    ["_SRout1_","_Fout1_R"],
    ["_SRout2_","_Fout2_R"],
    ["_SRout3_","_Fout3_R"],
    ["_SRout4_","_Fout4_R"],
    ["_SRout5_","_Fout5_R"],
    ["_SRout6_","_Fout6_R"],
    ["_SLout1_","_Fout1_L"],
    ["_SLout2_","_Fout2_L"],
    ["_SLout3_","_Fout3_L"],
    ["_SLout4_","_Fout4_L"],
    ["_SLout5_","_Fout5_L"],
    ["_SLout6_","_Fout6_L"],
    ["_FRout1_","_Fout1_R"],
    ["_FRout2_","_Fout2_R"],
    ["_FRout3_","_Fout3_R"],
    ["_FRout4_","_Fout4_R"],
    ["_FRout5_","_Fout5_R"],
    ["_FRout6_","_Fout6_R"],
    ["_FLout1_","_Fout1_L"],
    ["_FLout2_","_Fout2_L"],
    ["_FLout3_","_Fout3_L"],
    ["_FLout4_","_Fout4_L"],
    ["_FLout5_","_Fout5_L"],
    ["_FLout6_","_Fout6_L"],
    ["_SFR1_","_SF1_R"],
    ["_SFR2_","_SF2_R"],
    ["_SFR3_","_SF3_R"],
    ["_SFR4_","_SF4_R"],
    ["_SFR5_","_SF5_R"],
    ["_SFR6_","_SF6_R"],
    ["_SFL1_","_SF1_L"],
    ["_SFL2_","_SF2_L"],
    ["_SFL3_","_SF3_L"],
    ["_SFL4_","_SF4_L"],
    ["_SFL5_","_SF5_L"],
    ["_SFL6_","_SF6_L"],
    ["_SRF1_","_SSF1_R"],
    ["_SRF2_","_SSF2_R"],
    ["_SRF3_","_SSF3_R"],
    ["_SRF4_","_SSF4_R"],
    ["_SRF5_","_SSF5_R"],
    ["_SRF6_","_SSF6_R"],
    ["_SLF1_","_SSF1_L"],
    ["_SLF2_","_SSF2_L"],
    ["_SLF3_","_SSF3_L"],
    ["_SLF4_","_SSF4_L"],
    ["_SLF5_","_SSF5_L"],
    ["_SLF6_","_SSF6_L"],
    ["_SR1_","_S1_R"],
    ["_SR2_","_S2_R"],
    ["_SR3_","_S3_R"],
    ["_SR4_","_S4_R"],
    ["_SR5_","_S5_R"],
    ["_SR6_","_S6_R"],
    ["_SR7_","_S7_R"],
    ["_SR8_","_S8_R"],
    ["_SR9_","_S9_R"],
    ["_SL1_","_S1_L"],
    ["_SL2_","_S2_L"],
    ["_SL3_","_S3_L"],
    ["_SL4_","_S4_L"],
    ["_SL5_","_S5_L"],
    ["_SL6_","_S6_L"],
    ["_SL7_","_S7_L"],
    ["_SL8_","_S8_L"],
    ["_SL9_","_S9_L"],
    ["_SRB1_","_SB1_R"],
    ["_SRB2_","_SB2_R"],
    ["_SRB3_","_SB3_R"],
    ["_SRB4_","_SB4_R"],
    ["_SRB5_","_SB5_R"],
    ["_SRB6_","_SB6_R"],
    ["_SLB1_","_SB1_L"],
    ["_SLB2_","_SB2_L"],
    ["_SLB3_","_SB3_L"],
    ["_SLB4_","_SB4_L"],
    ["_SLB5_","_SB5_L"],
    ["_SLB6_","_SB6_L"],
    ["_SBR1_","_SBS1_R"],
    ["_SBR2_","_SBS2_R"],
    ["_SBR3_","_SBS3_R"],
    ["_SBR4_","_SBS4_R"],
    ["_SBR5_","_SBS5_R"],
    ["_SBR6_","_SBS6_R"],
    ["_SBL1_","_SBS1_L"],
    ["_SBL2_","_SBS2_L"],
    ["_SBL3_","_SBS3_L"],
    ["_SBL4_","_SBS4_L"],
    ["_SBL5_","_SBS5_L"],
    ["_SBL6_","_SBS6_L"],
    ["_BRout1_","_Bout1_R"],
    ["_BRout2_","_Bout2_R"],
    ["_BRout3_","_Bout3_R"],
    ["_BRout4_","_Bout4_R"],
    ["_BRout5_","_Bout5_R"],
    ["_BRout6_","_Bout6_R"],
    ["_BLout1_","_Bout1_L"],
    ["_BLout2_","_Bout2_L"],
    ["_BLout3_","_Bout3_L"],
    ["_BLout4_","_Bout4_L"],
    ["_BLout5_","_Bout5_L"],
    ["_BLout6_","_Bout6_L"],
    ["_BRin1_","_Bin1_R"],
    ["_BRin2_","_Bin2_R"],
    ["_BRin3_","_Bin3_R"],
    ["_BRin4_","_Bin4_R"],
    ["_BRin5_","_Bin5_R"],
    ["_BRin6_","_Bin6_R"],
    ["_BLin1_","_Bin1_L"],
    ["_BLin2_","_Bin2_L"],
    ["_BLin3_","_Bin3_L"],
    ["_BLin4_","_Bin4_L"],
    ["_BLin5_","_Bin5_L"],
    ["_BLin6_","_Bin6_L"],
    ["_RA1_","_A1_R"],
    ["_RA2_","_A2_R"],
    ["_RA3_","_A3_R"],
    ["_RA4_","_A4_R"],
    ["_RA5_","_A5_R"],
    ["_RA6_","_A6_R"],
    ["_LA1_","_A1_L"],
    ["_LA2_","_A2_L"],
    ["_LA3_","_A3_L"],
    ["_LA4_","_A4_L"],
    ["_LA5_","_A5_L"],
    ["_LA6_","_A6_L"],
    ["_BBR1_","_BB1_R"],
    ["_BBR2_","_BB2_R"],
    ["_BBR3_","_BB3_R"],
    ["_BBR4_","_BB4_R"],
    ["_BBR5_","_BB5_R"],
    ["_BBR6_","_BB6_R"],
    ["_BBL1_","_BB1_L"],
    ["_BBL2_","_BB2_L"],
    ["_BBL3_","_BB3_L"],
    ["_BBL4_","_BB4_L"],
    ["_BBL5_","_BB5_L"],
    ["_BBL6_","_BB6_L"],
]


def _apply_rename_rules(item):
    """Apply every rule, in order, to a bone or vertex group (same logic as the original script)."""
    for old, new in BONE_RENAME:
        if old in item.name:
            item.name = item.name.replace(old, "") + new


class ORGAN_OT_fix_mirroring(bpy.types.Operator):
    """Rename the bones and vertex groups of the selected armatures and meshes so they follow the _L / _R mirroring convention"""
    bl_idname = "organ.fix_mirroring"
    bl_label = "Fix Mirroring"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']

        if not armatures and not meshes:
            self.report({'WARNING'}, "Select the armatures and meshes you want to fix")
            return {'CANCELLED'}

        groups_renamed = 0
        for mesh in meshes:
            for vgroup in mesh.vertex_groups:
                original = vgroup.name
                _apply_rename_rules(vgroup)
                if vgroup.name != original:
                    groups_renamed += 1
                    print(f'Renaming vertex group "{original}" of mesh "{mesh.name}" to "{vgroup.name}"')

        bones_renamed = 0
        for arma in armatures:
            for bone in arma.data.bones:
                original = bone.name
                _apply_rename_rules(bone)
                if bone.name != original:
                    bones_renamed += 1
                    print(f'Renaming bone "{original}" of armature "{arma.name}" to "{bone.name}"')

        self.report(
            {'INFO'},
            f"Mirroring fixed: {bones_renamed} bone(s) and {groups_renamed} vertex group(s) renamed"
        )
        return {'FINISHED'}


# The "Shader Import" feature (operators, panel and embedded shader data) lives in the
# separate, optional add-on ORGAN_Shader_Import.py.

class ORGAN_PT_panel(bpy.types.Panel):
    bl_label = "O.R.G.A.N."
    bl_idname = "ORGAN_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "O.R.G.A.N."

    def draw(self, context):
        layout = self.layout
        layout.operator(ORGAN_OT_show_all_armatures.bl_idname, icon='ARMATURE_DATA')


class ORGAN_PT_texture_controls(bpy.types.Panel):
    bl_label = "Texture Controls"
    bl_idname = "ORGAN_PT_texture_controls"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "O.R.G.A.N."
    bl_parent_id = "ORGAN_PT_panel"

    def draw(self, context):
        layout = self.layout
        layout.operator(ORGAN_OT_set_alpha_channel_packed.bl_idname, icon='TEXTURE')
        layout.operator(ORGAN_OT_fix_ilm.bl_idname, icon='NODE_COMPOSITING')
        layout.operator(ORGAN_OT_fix_decal.bl_idname, icon='MATERIAL')
        layout.operator(ORGAN_OT_refresh_textures.bl_idname, icon='FILE_REFRESH')


class ORGAN_PT_color_palettes(bpy.types.Panel):
    bl_label = "Color Palettes"
    bl_idname = "ORGAN_PT_color_palettes"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "O.R.G.A.N."
    bl_parent_id = "ORGAN_PT_texture_controls"

    def draw(self, context):
        layout = self.layout
        layout.operator(ORGAN_OT_format_palette_textures.bl_idname, icon='COLOR')


class ORGAN_PT_import_controls(bpy.types.Panel):
    bl_label = "Import Controls"
    bl_idname = "ORGAN_PT_import_controls"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "O.R.G.A.N."
    bl_parent_id = "ORGAN_PT_panel"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "organ_rig", text="Rig")
        layout.operator(ORGAN_OT_fix_armature.bl_idname, icon='BONE_DATA')

        layout.prop(scene, "organ_select_all_armatures")

        row = layout.row()
        row.enabled = bool(_target_rigs(context))
        row.prop(scene, "organ_hide_armature")

        layout.operator(ORGAN_OT_fix_mirroring.bl_idname, icon='MOD_MIRROR')

classes = (
    ORGAN_OT_show_all_armatures,
    ORGAN_OT_set_alpha_channel_packed,
    ORGAN_OT_fix_ilm,
    ORGAN_OT_fix_decal,
    ORGAN_OT_refresh_textures,
    ORGAN_OT_format_palette_textures,
    ORGAN_OT_fix_armature,
    ORGAN_OT_fix_mirroring,
    ORGAN_PT_panel,
    ORGAN_PT_texture_controls,
    ORGAN_PT_color_palettes,
    ORGAN_PT_import_controls,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.organ_rig = bpy.props.PointerProperty(
        name="Rig",
        description="Armature the Import Controls act on when no armature is selected",
        type=bpy.types.Object,
        poll=_rig_poll,
    )
    # Checked while every selectable armature in the file is selected; checking it selects
    # them all, unchecking it deselects them (other objects are not touched).
    bpy.types.Scene.organ_select_all_armatures = bpy.props.BoolProperty(
        name="Select All Armatures",
        description="Select (or deselect) every armature in the file",
        get=_get_select_all_armatures,
        set=_set_select_all_armatures,
    )
    # The checkbox mirrors the rig's real state, so it
    # unchecks itself when 'Show all armatures' sets everything to Textured.
    bpy.types.Scene.organ_hide_armature = bpy.props.BoolProperty(
        name="Hide Armature",
        description="Checked: the selected rigs (or the chosen rig) are displayed as Bounds. Unchecked: Textured",
        get=_get_hide_armature,
        set=_set_hide_armature,
    )


def unregister():
    del bpy.types.Scene.organ_select_all_armatures
    del bpy.types.Scene.organ_hide_armature
    del bpy.types.Scene.organ_rig

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
