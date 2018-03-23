bl_info = {
    "name": "Species Project",
    "description": "Content creation helper using evolutionary algorithms on shape keys and optionally using Shrinkwrap modifiers",
    "author": "The Species Team",
    "version": (0, 0, 1),
    "blender": (2, 70, 0),
    "location": "3D View > Tools",
    "warning": "", # used for warning icon and text in addons panel
    "wiki_url": "",
    "tracker_url": "",
    "category": "Development"
}

import bpy
from bpy.props import (
    StringProperty, BoolProperty, IntProperty, FloatProperty, EnumProperty, 
    PointerProperty, CollectionProperty,
    FloatVectorProperty, IntVectorProperty
)
from bpy.types import (Panel, Operator, PropertyGroup)
from mathutils import (Vector, Color)
import math
import numpy
from numpy import random


#
# Utility functions
#

def map01(x, minn, maxn):
    """Map a value in [min, max] range to the [0, 1] range."""
    if minn == maxn: # Prevent division by zero
        return 0
    return (x - minn) / (maxn - minn)

def lerp(start, end, t):
    """Perform linear interpolation"""
    return start * (1 - t) + end * t

def make_2d_capacity_from_1d(count):
    """Computes a reasonably square 2D capacity from a 1D capacity."""
    w = math.ceil(math.sqrt(count))
    h = math.ceil(count / w)
    assert w*h >= count
    return w, h

#
# Blender-related functions
#

# https://blender.stackexchange.com/a/45100
# https://blender.stackexchange.com/a/82775
def duplicate_object(context, ob):
    """Duplicate a Blender Object and links it to the scene."""
    c = ob.copy()
    c.data = ob.data.copy()
    for k, mat in ob.material_slots.items():
        c.material_slots[k].material = ob.material_slots[k].material.copy()
    c.animation_data_clear()
    context.scene.objects.link(c)
    return c


# Reminder: Valid values for `wrap_method` are 'NEAREST_SURFACEPOINT' | 'NEAREST_VERTEX' | 'PROJECT'.
def add_shrinkwrap_shape_key(ob, name, target, wrap_method = 'NEAREST_SURFACEPOINT'):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.scene.objects.active = ob
    bpy.ops.object.modifier_add(type='SHRINKWRAP')
    mod = ob.modifiers['Shrinkwrap']
    mod.name = name
    mod.target = target
    mod.wrap_method = wrap_method
    bpy.ops.object.modifier_apply(apply_as='SHAPE', modifier=name)


def redraw_all_areas():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


#
# Properties update hooks
#

def call_tidy_up(self, context):
    bpy.ops.object.species_tidy_up('INVOKE_DEFAULT')

def override_generation_index_for_selected_objects(self, context):
    for ob in context.selected_objects:
        ob.specie.generation_index = self.generation_index_override
    call_tidy_up(self, context)


#
# Properties
#   

class SpeciesScene(PropertyGroup):
    """Scene-wide data used by this Add-on."""
    grid_spacing = FloatVectorProperty(name="Grid Spacing", size=3, update=call_tidy_up)
    num_children_per_couple_without_shrinkwrap = IntProperty(name="Children per couple", default=0, min=0)
    num_children_per_couple_using_shrinkwrap = IntProperty(name="Children per couple", default=0, min=0)
    
    mutation_probability = FloatProperty(name="Mutation Probability", default=0.2, min=0, max=1)
    mutation_normal_distribution_scale = FloatProperty(name="Scale of Normal Distribution for Mutations", default=0.4, min=0)
    generation_index_override = IntProperty(name="Generation Index Override", default=0, min=-1, update=override_generation_index_for_selected_objects)
    
    def mix_scalar_genome(self, a, b, minn, maxn):
        mixed = lerp(a, b, random.random())
        if random.random() <= self.mutation_probability:
            mixed += random.normal(scale = self.mutation_normal_distribution_scale)
            mixed = numpy.clip(mixed, minn, maxn)
        return mixed
    
    def mix_vector_genome(self, a, b, minn, maxn):
        mixed = Vector.lerp(a, b, random.random())
        if random.random() <= self.mutation_probability:
            m = lambda: random.normal(scale = self.mutation_normal_distribution_scale)
            mixed += Vector((m(), m(), m()))
            mixed = Vector(numpy.clip(mixed, minn, maxn))
        return mixed


class SpecieObject(PropertyGroup):
    """Object-specific data used by this Add-on."""
    generation_index = IntProperty(name="Generation Index", default=-1, min=-1)



#
# Operators
#

class FlattenSpecies(Operator):
    """Sets the generation index to the highest one for all objects"""
    bl_idname = "object.species_flatten"
    bl_label = "Species: Flatten"
    
    def execute(self, context):
        obs = [ob for ob in context.scene.objects if ob.specie.generation_index >= 0]
        if not obs:
            self.report({'WARNING'}, "No objects to flatten (Does any have a positive generation index?)")
            return {'FINISHED'}
        
        highest_generation_index = max([ob.specie.generation_index for ob in obs])
        for ob in obs:
            ob.specie.generation_index = highest_generation_index
        
        bpy.ops.object.species_tidy_up('INVOKE_DEFAULT')
        return {'FINISHED'}
    

class TidyUpSpecies(Operator):
    """Nicely spreads objects across the grid"""
    bl_idname = "object.species_tidy_up"
    bl_label = "Species: Tidy Up"
    
    def execute(self, context):
        obs = [ob for ob in context.scene.objects if ob.specie.generation_index >= 0]
        if not obs:
            self.report({'WARNING'}, "No objects to flatten (Does any have a positive generation index?)")
            return {'FINISHED'}
        
        g = context.scene.species
        lowest_generation_index = min([ob.specie.generation_index for ob in obs])
        
        generations = {}
        for ob in obs:
            generations.setdefault(ob.specie.generation_index, []).append(ob)
        
        for gen_i, obs in generations.items():
            w, h = make_2d_capacity_from_1d(len(obs))
            for i, ob in enumerate(obs):
                ob.location.x = g.grid_spacing[0] * ((i  % w) - (w-1)/2)
                ob.location.y = g.grid_spacing[1] * ((i // w) - (h-1)/2)
                ob.location.z = (gen_i - lowest_generation_index) * g.grid_spacing[2]
        return {'FINISHED'}


class RetainSpecies(Operator):
    """Deletes objects that have interacted with this add-on and are not currently selected"""    
    bl_idname = "object.species_retain"
    bl_label = "Species: Retain"
    
    def execute(self, context):
        for ob in context.scene.objects:
            if ob.specie.generation_index >= 0 and not ob.select:
                bpy.data.objects.remove(ob, do_unlink=True)
        bpy.ops.object.species_tidy_up('INVOKE_DEFAULT')
        redraw_all_areas()
        return {'FINISHED'}


class RandomizeSpecies(Operator):
    """Randomizes all values of shape keys for each currently selected object"""
    bl_idname = "object.species_randomize"
    bl_label = "Species: Randomize"
    
    def execute(self, context):
        if not context.selected_objects:
            self.report({'ERROR'}, 'No objects to randomize!');
            return {'FINISHED'}
        
        for ob in context.selected_objects:
            for shape_key in ob.data.shape_keys.key_blocks:
                shape_key.value = random.random()
                
        return {'FINISHED'}


class MixSpecies(Operator):
    """Treating currently selected objects as "mom, dad" couples, offspring is generated by randomly blending values of Shape Keys that parents have in common"""
    bl_idname = "object.species_mix"
    bl_label = "Species: Mix"
    
    def execute(self, context):
        obs = context.selected_objects
        
        if not obs:
            self.report({'WARNING'}, 'No objects to mix!')
            return {'FINISHED'}
        
        if len(obs) < 2:
            self.report({'WARNING'}, 'Mixing needs multiple objects!')
            return {'FINISHED'}

        g = context.scene.species
        
        total_num_children = g.num_children_per_couple_using_shrinkwrap + g.num_children_per_couple_without_shrinkwrap
        
        if total_num_children <= 0:
            self.report({'WARNING'}, 'There is zero children per couple!')
            return {'FINISHED'}

        highest_generation_index = max(0, max([ob.specie.generation_index for ob in context.scene.objects]))
        
        for ob in obs:
            if ob.specie.generation_index < 0:
                ob.specie.generation_index = highest_generation_index

        # Generate offspring
        couples = [(obs[i], obs[i+1]) for i in range(0, len(obs)-1, 1)]
        for mom, dad in couples:
            mk = mom.data.shape_keys.key_blocks
            dk = dad.data.shape_keys.key_blocks
            keys = set(mk.keys()).intersection(dk.keys())
            next_gen = 1 + max(mom.specie.generation_index, dad.specie.generation_index)
    
            for i in range(total_num_children):
                
                ob = duplicate_object(context, mom)
                ob.specie.generation_index = next_gen
                
                # Use Shrinkwrap to blend between two models
                if i < g.num_children_per_couple_using_shrinkwrap:
                    modname = 'Shrinkwrap to ' + dad.name
                    ob.location = dad.location.copy()
                    add_shrinkwrap_shape_key(ob, name=modname, target=dad)
                    ob.data.shape_keys.key_blocks[modname].value = random.random()
                
                # Mix materials (only diffuse color)
                for m in range(1):
                    mmat = mom.material_slots[m].material
                    dmat = dad.material_slots[m].material
                    color = g.mix_vector_genome(
                        Vector(mmat.diffuse_color), 
                        Vector(dmat.diffuse_color),
                        Vector((0,0,0)), Vector((1,1,1))
                    )
                    ob.material_slots[m].material.diffuse_color = Color(color)
                
                # Mix shape keys
                for key in keys:
                    k = ob.data.shape_keys.key_blocks[key]
                    k.value = g.mix_scalar_genome(mk[key].value, dk[key].value, k.slider_min, k.slider_max)
        
        bpy.ops.object.species_tidy_up('INVOKE_DEFAULT')
        return {'FINISHED'}
    

#
# Panels
#

class MainPanel(Panel):
    bl_idname = "OBJECT_PT_species_main"
    bl_label = "Species"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_category = "Tools"
    bl_context = "objectmode"

    @classmethod
    def poll(self, context):
        # We're always active
        return True

    def draw(self, context):
        c = self.layout.column(align=True)
        c.prop(context.scene.species, "grid_spacing", text="Grid Spacing")
        
        c = self.layout.column(align=True)
        c.label("Children per couple:")
        c.prop(context.scene.species, "num_children_per_couple_without_shrinkwrap", text="Without Shrinkwrap")
        c.prop(context.scene.species, "num_children_per_couple_using_shrinkwrap", text="Using Shrinkwrap")
        
        c = self.layout.column(align=True)
        c.label("Mutations:")
        c.prop(context.scene.species, "mutation_probability")
        c.prop(context.scene.species, "mutation_normal_distribution_scale")
        
        c = self.layout.column(align=True)
        c.label("All objects:")
        r = c.row(align=True)
        r.operator(TidyUpSpecies.bl_idname, text="Tidy Up")
        r.operator(FlattenSpecies.bl_idname, text="Flatten")
        
        c = self.layout.column(align=True)
        obs = context.selected_objects
        if not obs:
            c.label("(No object selected)")
        else:
            c.label("Selection:")
            
            if len(obs) == 1:
                c.prop(context.object.specie, "generation_index", text="Generation index")
            else:
                c.prop(context.scene.species, "generation_index_override", text="Generation index")
            
            if len(obs) >= 1:
                c.operator(RetainSpecies.bl_idname, text="Retain")
                c.operator(RandomizeSpecies.bl_idname, text="Randomize Shape Key Values")    
                
            if len(obs) >= 2:
                c.operator(MixSpecies.bl_idname, text="Mix")
        


#
# Usual Blender stuff
#

def register():
    bpy.utils.register_module(__name__)
    bpy.types.Scene.species = PointerProperty(type=SpeciesScene)
    bpy.types.Object.specie = PointerProperty(type=SpecieObject)

def unregister():
    bpy.utils.unregister_module(__name__)
    del bpy.types.Scene.species
    del bpy.types.Object.specie

if __name__ == "__main__":
    register()