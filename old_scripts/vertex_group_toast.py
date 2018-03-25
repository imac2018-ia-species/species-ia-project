bl_info = {
    "name": "Species Experiment",
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

import bpy
from bpy.props import (StringProperty,
                       BoolProperty,
                       IntProperty,
                       FloatProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import (Panel,
                       Operator,
                       PropertyGroup,
                       )
from mathutils import Vector



scene = bpy.data.scenes['Scene']
obj = scene.objects['Sphere']
vgroup = obj.vertex_groups['TipOfTheHat']
vertices = [ v for v in obj.data.vertices if vgroup.index in [ vg.group for vg in v.groups ] ]
vpositions_model = [ v.co for v in vertices ]
vpositions_world = [ (obj.matrix_world * pos) for pos in vpositions_model ]
# obj['MyProp']
# Vector.lerp()

class MySettings(PropertyGroup):

    my_bool = BoolProperty(
        name="Enable or Disable",
        description="A bool property",
        default = False
        )

    my_int = IntProperty(
        name = "Int Value",
        description="A integer property",
        default = 23,
        min = 10,
        max = 100
        )

    my_float = FloatProperty(
        name = "Float Value",
        description = "A float property",
        default = 23.7,
        min = 0.01,
        max = 30.0
        )

    my_string = StringProperty(
        name="User Input",
        description=":",
        default="",
        maxlen=1024,
        )

    my_enum = EnumProperty(
        name="Dropdown:",
        description="Apply Data to attribute",
        items=[ ('OP1', "Option 1", ""),
                ('OP2', "Option 2", ""),
                ('OP3', "Option 3", ""),
               ]
        )


class HelloWorldOperator(bpy.types.Operator):
    bl_idname = "wm.hello_world"
    bl_label = "Print Values Operator"

    def execute(self, context):
        scene = context.scene
        mytool = scene.my_tool

        # print the values to the console
        print("Hello World")
        print("bool state:", mytool.my_bool)
        print("int value:", mytool.my_int)
        print("float value:", mytool.my_float)
        print("string value:", mytool.my_string)
        print("enum state:", mytool.my_enum)

        return {'FINISHED'}



class BasicMenu(bpy.types.Menu):
    bl_idname = "OBJECT_MT_select_test"
    bl_label = "Select"

    def draw(self, context):
        layout = self.layout

        # built-in example operators
        layout.operator("object.select_all", text="Select/Deselect All").action = 'TOGGLE'
        layout.operator("object.select_all", text="Inverse").action = 'INVERT'
        layout.operator("object.select_random", text="Random")


class OBJECT_PT_my_panel(Panel):
    bl_idname = "OBJECT_PT_my_panel"
    bl_label = "My Panel"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "TOOLS"    
    bl_category = "Tools"
    bl_context = "objectmode"   

    @classmethod
    def poll(self,context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        mytool = scene.my_tool

        layout.prop(mytool, "my_bool")
        layout.prop(mytool, "my_enum", text="") 
        layout.prop(mytool, "my_int")
        layout.prop(mytool, "my_float")
        layout.prop(mytool, "my_string")
        layout.operator("wm.hello_world")
        layout.menu("OBJECT_MT_select_test", text="Presets", icon="SCENE")



def register():
    bpy.utils.register_module(__name__)
    bpy.types.Scene.my_tool = PointerProperty(type=MySettings)

def unregister():
    bpy.utils.unregister_module(__name__)
    del bpy.types.Scene.my_tool

if __name__ == "__main__":
    register()