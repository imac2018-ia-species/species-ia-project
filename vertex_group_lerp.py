bl_info = {
    "name": "Species Lerp Vertex Groups",
    "description": "",
    "author": "The Species Team",
    "version": (0, 0, 1),
    "blender": (2, 70, 0),
    "location": "3D View > Tools",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "",
    "tracker_url": "",
    "category": "Development"
}

# https://docs.blender.org/api/blender_python_api_current/mathutils.html
# https://docs.blender.org/api/blender_python_api_current/info_quickstart.html#custom-properties
# https://blender.stackexchange.com/a/75240
# https://blender.stackexchange.com/a/57332

# Features:
# - JawWidth
#   - Set Vertex Group
#   - Set 0 (store position of all vertices in group)
#   - Set 1 (store position of all vertices in group)
#   - Drag slider handle
#   - Delete
# Actions:
# - Add
# - Refresh (vertexgroup lists)


# NOTE: vertex group code
# scene = bpy.data.scenes['Scene']
# obj = scene.objects['Sphere']
# vgroup = obj.vertex_groups['TipOfTheHat']
# vertices = [ v for v in obj.data.vertices if vgroup.index in [ vg.group for vg in v.groups ] ]
# vpositions_model = [ v.co for v in vertices ]
# vpositions_world = [ (obj.matrix_world * pos) for pos in vpositions_model ]
#
# obj['MyProp']
# Vector.lerp()


# NOTES:
# - Only for Edit Mode


import bpy
import bmesh
from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       EnumProperty,
                       PointerProperty,
                       CollectionProperty,
                       )
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       )
from mathutils import Vector


def get_vertices_of_vertex_group(obj, vgroup_name):
    vgroup = obj.vertex_groups[vgroup_name]
    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj.data)
        out = [ v for dv, v in zip(obj.data.vertices, bm.verts) if vgroup.index in [ vg.group for vg in dv.groups ] ]
        # bm.free() # FIXME
        return out
    
    return [ v for v in obj.data.vertices if vgroup.index in [ vg.group for vg in v.groups ] ]

def get_vertex_positions_modelspace(vertices):
    return [ v.co for v in vertices ]

def get_vertex_positions_worldspace(obj, vertices):
    return [ (obj.matrix_world * pos) for pos in [ v.co for v in vertices ]]


def on_slider_change(feat, context):
    print("A change occured!", feat.name, ": ", feat.current_lerp_value)
    # FIXME: Perform actual LERP here
    obj = context.object
    vgroup = obj.vertex_groups[feat.vertex_group_name]
    i = 0
    bm = bmesh.from_edit_mesh(obj.data)
    
    for dv, v in zip(obj.data.vertices, bm.verts):
        if vgroup.index in [ vg.group for vg in dv.groups ]:
            p = feat.vpositions[0][i], feat.vpositions[1][i]
            print("Lerp from ", p[0], " to ", p[1])
            v.co = Vector.lerp(p[0], p[1], feat.current_lerp_value)
            i += 1
            
    # bm.to_mesh(obj.data) # NOTE: Throws an exception if in edit mode
    # bm.free() # FIXME

class SpecieFeature(PropertyGroup):
    vertex_group_name = EnumProperty(
        name = "Vertex Group Name",
        description = "Name of the vertex group to use for LERPing",
        items = lambda scene, context: [(name, name, "") for name, vg in context.object.vertex_groups.items()]
        )
    current_lerp_value = FloatProperty(
        name = "Current LERP value",
        description = "A float property",
        default = 0,
        min = 0,
        max = 1,
        update = on_slider_change
        )
    vpositions = [[], []]


class OBJECT_OT_specie_record_feature(bpy.types.Operator):
    bl_idname = "object.specie_record_feature"
    bl_label = "Specie Record Operator"
    feature_name = StringProperty()
    bound = FloatProperty()

    def execute(self, context):
        print("Extremum state:", self.feature_name, self.bound)
        obj = context.object
        feature = obj.specie_features[self.feature_name]
        vgroup = obj.vertex_groups[feature.vertex_group_name]
        bm = bmesh.from_edit_mesh(obj.data)
        feature.vpositions[int(self.bound)] = [ v.co.copy() for dv, v in zip(obj.data.vertices, bm.verts) if vgroup.index in [ vg.group for vg in dv.groups ] ]
        # bm.free() # FIXME
        for p in feature.vpositions[int(self.bound)]:
            print("New vposition: ", p)
        return {'FINISHED'}

class OBJECT_OT_specie_add_feature(bpy.types.Operator):
    bl_idname = "object.specie_add_feature"
    bl_label = "Specie Add Feature Operator"
    feature_name = StringProperty()
    
    def execute(self, context):
        ob = bpy.context.object
        item = ob.specie_features.add()
        item.id = len(ob.specie_features)
        item.name = self.feature_name
        return {'FINISHED'}

class OBJECT_OT_specie_remove_feature(bpy.types.Operator):
    bl_idname = "object.specie_remove_feature"
    bl_label = "Specie Remove Feature Operator"
    feature_index = IntProperty()
    
    def execute(self, context):
        item = context.object.specie_features.remove(self.feature_index)
        return {'FINISHED'}

class OBJECT_PT_my_panel(Panel):
    bl_idname = "OBJECT_PT_species_lerp"
    bl_label = "Specie Lerp Vertex Groups"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Tools"
    bl_context = "mesh_edit"   

    @classmethod
    def poll(self, context):
        return context.object is not None

    def draw(self, context):
        bar = self.layout.operator("object.specie_add_feature", text="Add Feature")
        bar.feature_name = "Feature " + str(len(context.object.specie_features))
        for name, props in context.object.specie_features.items():
            self.layout.label(name)
            self.layout.prop(props, "vertex_group_name")
            self.layout.prop(props, "current_lerp_value")
            bar = self.layout.operator("object.specie_record_feature", text="Record 0")
            bar.feature_name = name
            bar.bound = 0
            bar = self.layout.operator("object.specie_record_feature", text="Record 1")
            bar.feature_name = name
            bar.bound = 1
            bar = self.layout.operator("object.specie_remove_feature", text="Remove")
            bar.feature_index = 0


def register():
    bpy.utils.register_module(__name__)
    # if !hasattr(bpy.types.Object, 'specie_features'):
    bpy.types.Object.specie_features = CollectionProperty(type=SpecieFeature)

def unregister():
    bpy.utils.unregister_module(__name__)
    del bpy.types.Object.specie_features

if __name__ == "__main__":
    register()