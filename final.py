# Procédé:
# 1. Avoir plusieurs objets dans la scène en object Mode;
#    On présuppose que les objets sont mutuellement adaptés au Shinkwrap;
#    On présuppose qu'ils ont un ensemble commun de Shape Keys;
# 2. Sélectionner un ensemble d'objets, puis appuyer sur un bouton;
#    Incrémente un état interne et le numéro de génération. C'est-à-dire :
#    - Supprime les non-fits, exceptés une petite proportion;
#    - Divise la sélection en couples;
#    - Pour chaque couple, générer N enfants d'après interpolation;
#      Interpolation par Shape Keys. Le Shrinkwrap est un Shape Key, mais est supprimé à la fin
#      afin d'économiser de la mémoire.
#    - Ca serait bien que la couleur soit interpolée aussi.
# 4. Goto 2 jusqu'à satisfaction.
#
# Y'a un bouton "clear" pour reset le numéro de génération et les données internes.

# Exemple de run:
# - J'ai un cube et une sphère dans ma scène.
#   Ils ont tous les deux une "taille de chapeau" et "taille des pieds" en Shape Keys.
# - Je lance l'add-on, et configure ses settings dans le panel.
# - Je sélectionne le cube et la sphère.
# - J'appuie sur "Generate".
# - Je vois mes deux objets, ainsi que leur progéniture, bien répartis sur la grille.
# - Je peux recommencer autant que je veux.
#
# Plan:
# - Interpoler les couleurs de matériaux
# - Jouer avec le Shrinkwrap
# - Tester sur les animaux

# bpy.ops.object.shape_key_add(from_mix=False)
# bpy.ops.object.shape_key_add(all=False)
# bpy.ops.object.modifier_add(type='SHRINKWRAP')
# bpy.ops.object.modifier_apply(apply_as='SHAPE')
# ob.active_shape_key_index
# mod = ob.modifiers['Shrinkwrap']
# mod.name = "new name"
# mod.target = other_object
# mod.wrap_method = 'NEAREST_SURFACEPOINT' | 'NEAREST_VERTEX' | 'PROJECT'


import bpy
from bpy.props import (
    StringProperty, BoolProperty, IntProperty, FloatProperty, EnumProperty, 
    PointerProperty, CollectionProperty,
    FloatVectorProperty, IntVectorProperty
)
from bpy.types import (Panel, Operator, PropertyGroup)
from mathutils import Vector
from numpy import random
import itertools
import math


#
# Utility functions
#

def map01(x, minn, maxn):
    """Map a value in [min, max] range to the [0, 1] range."""
    if minn == maxn: # Prevent division by zero
        return minn
    return (x - minn) / (maxn - minn)

def lerp(start, end, t):
    """Perform linear interpolation"""
    return start * (1 - t) + end * t

# https://blender.stackexchange.com/a/45100
def duplicate_object(context, ob):
    """Duplicate a Blender Object and links it to the scene."""
    c = ob.copy()
    c.data = ob.data.copy()
    c.animation_data_clear()
    context.scene.objects.link(c)
    return c

def make_2d_capacity_from_1d(count):
    """Computes a reasonably square 2D capacity from a 1D capacity."""
    w = math.ceil(math.sqrt(count))
    h = math.ceil(count / w)
    assert w*h >= count
    return w, h
    

#
# Properties
#

def override_generation_index_for_selected_objects(self, context):
    for ob in context.selected_objects:
        ob.specie.generation_index = self.generation_index_override
    

class SpeciesScene(PropertyGroup):
    """Scene-wide data used by this Add-on."""
    grid_spacing = FloatVectorProperty(name="Grid Spacing", size=3)
    num_children_per_couple = IntProperty(name="Children per couple", default=1, min=1)
    mutation_probability = FloatProperty(name="Mutation Probability", default=0.2, min=0, max=1)
    mutation_normal_distribution_scale = FloatProperty(name="Scale of Normal Distribution for Mutations", default=0.4, min=0)
    generation_index_override = IntProperty(name="Generation Index Override", default=0, min=-1, update=override_generation_index_for_selected_objects)

class SpecieObject(PropertyGroup):
    """Object-specific data used by this Add-on."""
    generation_index = IntProperty(name="Generation Index", default=-1, min=-1)



#
# Operators
#


# Stored into constants to avoid surprises when changing the strings
op_randomize = "object.species_randomize"
op_mix = "object.species_mix"
op_tidy_up = "object.species_tidy_up"
op_flatten = "object.species_flatten"
op_retain = "object.species_retain"

class FlattenSpecies(Operator):
    """Sets the generation index to the highest one for all objects."""
    bl_idname = op_flatten
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
    """Nicely spreads objects across the grid."""
    bl_idname = op_tidy_up
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
    """Deletes objects that have interacted with this add-on and are not currently selected."""    
    bl_idname = op_retain
    bl_label = "Species: Retain"
    
    def execute(self, context):
        for ob in context.scene.objects:
            if ob.specie.generation_index >= 0 and not ob.select:
                bpy.data.objects.remove(ob, do_unlink=True)
        bpy.ops.object.species_tidy_up('INVOKE_DEFAULT')
        context.area.tag_redraw()
        return {'FINISHED'}


class RandomizeSpecies(Operator):
    """Randomizes all values of shape keys for each currently selected object."""
    bl_idname = op_randomize
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
    """Treating currently selected objects as "mom, dad" couples, offspring is generated by randomly blending values of Shape Keys that parents have in common."""
    bl_idname = op_mix
    bl_label = "Species: Mix"
    
    def execute(self, context):
        obs = context.selected_objects
        
        if not obs:
            self.report({'ERROR'}, 'No objects to mix!');
            return {'FINISHED'}
        
        if len(obs) < 2:
            self.report({'ERROR'}, 'Mixing needs multiple objects!');
            return {'FINISHED'}

        g = context.scene.species

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
            for i in range(g.num_children_per_couple):
                ob = duplicate_object(context, mom)
                ob.specie.generation_index = next_gen
                for key in keys:
                    mixed = lerp(mk[key].value, dk[key].value, random.random())
                    if random.random() <= g.mutation_probability:
                        mixed += random.normal(scale=g.mutation_normal_distribution_scale)
                        mixed = min(mixed, ob.data.shape_keys.key_blocks[key].slider_max)
                        mixed = max(mixed, ob.data.shape_keys.key_blocks[key].slider_min)
                    ob.data.shape_keys.key_blocks[key].value = mixed
        
        bpy.ops.object.species_tidy_up('INVOKE_DEFAULT')
        return {'FINISHED'}


#
# Panels
#

class MainPanel(Panel):
    bl_idname = "OBJECT_PT_species_main"
    bl_label = "Species: Main Panel"
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
        c.prop(context.scene.species, "num_children_per_couple")
        
        c = self.layout.column(align=True)
        c.label("Mutations:")
        c.prop(context.scene.species, "mutation_probability")
        c.prop(context.scene.species, "mutation_normal_distribution_scale")
        
        c = self.layout.column(align=True)
        c.label("All objects:")
        r = c.row(align=True)
        r.operator(op_tidy_up, text="Tidy Up")
        r.operator(op_flatten, text="Flatten")
        
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
                c.operator(op_retain, text="Retain")
                c.operator(op_randomize, text="Randomize Shape Key Values")    
                
            if len(obs) >= 2:
                c.operator(op_mix, text="Mix")
        


#
# Usual Blender stuff
#

bl_info = {
    "name": "Species Project",
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

def register():
    bpy.utils.register_module(__name__)
    # if !hasattr(bpy.types.Scene, 'species'):
    bpy.types.Scene.species = PointerProperty(type=SpeciesScene)
    bpy.types.Object.specie = PointerProperty(type=SpecieObject)

def unregister():
    bpy.utils.unregister_module(__name__)
    del bpy.types.Scene.species
    del bpy.types.Object.specie

if __name__ == "__main__":
    register()