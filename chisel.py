import sys
import bpy, bmesh
import pprint
from bpy.props import FloatProperty
from mathutils import Vector
bl_info = {
    "name": "Chisel",
    "category": "Object",
}
class ChiselOperator(bpy.types.Operator):
    bl_idname = "object.chisel"
    bl_label = "Chisel"
    bl_options = {'REGISTER', 'UNDO'}
    
    offset_x=FloatProperty(
        name='width',
        description='Width',
        default=0.1,
        min=-100.0,
        max=100.0,
    )
    offset_y=FloatProperty(
        name='length',
        description='Length',
        default=0.1,
        min=-100.0,
        max=100.0,
    )
    offset_z=FloatProperty(
        name='height',
        description='Height',
        default=0.1,
        min=-100.0,
        max=100.0,
    )
    def __init__(self):
        self.v_inner = []
        self.v_sides = []
        self.v_ends = []
        self.lock_x = False
        self.lock_y = False
        super().__init__()
 
    def do_chisel(self, context):
 
        bm = self.bm
        # vectors pointing outward for scaling the outer verts
        fatkey = bm.verts.layers.shape.get('v_outward')
        if not fatkey:
            fatkey = bm.verts.layers.shape.new('v_outward')
        

        # `is_end` flags the end vertices
        # so we can find them again after bevel():
        endkey = bm.verts.layers.int.get('is_end')
        if not endkey:
            endkey = bm.verts.layers.int.new('is_end')


        endkeyset = set()        
        
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        esel = set([e for e in bm.edges if e.select])
        vsel = set([v for v in bm.verts if v.select])

        old_end_locs = {}
        
        for v in bm.verts:
            v[endkey] = -1

        for f in bm.faces:
            f.tag = False

        for v in vsel:
            neighbors=0
            for e in v.link_edges:
                if e in esel:
                    neighbors+=1
            if neighbors==1:
                v[endkey] = v.index
                endkeyset.add(v.index)
                old_end_locs[v.index] = v.co


        # bevel needs both the edges and verts:        
        geom = list(vsel) + list(esel)

        # use some default values, we scale the verts later:
        bresult = bmesh.ops.bevel(
            bm,
            geom=geom,
            offset=.05,
            offset_type=1,
            segments=2,
            profile=.5,
            vertex_only=False,
            loop_slide=False
        )

        bmesh.update_edit_mesh(context.object.data)
    
        new_fset = set(bresult['faces'])
        new_eset = set(bresult['edges'])
        new_vset = set(bresult['verts'])

        for f in new_fset:
            f.tag = True

        # find endcap verts by searching for the `endkey` attribute:
        mergegroups = {}
        for k in endkeyset:
            mergegroups[k] = []
            for v in new_vset:
                if v[endkey] == k:
                    mergegroups[k].append(v)

        # collapse each endcap to a single vertex:
        for k in mergegroups:
            mres = bmesh.ops.pointmerge(bm, verts=mergegroups[k], merge_co=old_end_locs[k])

        bm.normal_update()   
        bmesh.update_edit_mesh(context.object.data)
        bm.edges.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # get all of the geometry this op added:
        f_all = set()
        e_all = set()
        v_all = set()
        for f in bm.faces:
            if f.tag:
                f_all.add(f)
                for v in f.verts:
                    v_all.add(v)
                for e in f.edges:
                    e_all.add(e)
        
        # make lists for inner, outer, and end verts:
        v_outer = set()
        self.v_ends = set()
        
        for v in v_all:
            if v[endkey] != -1:
                self.v_ends.add(v)

            # if any neighbor is not in the new geometry
            # then this vert is on the outer loop:
            for f in v.link_faces:
                if f not in f_all:
                    v_outer.add(v)
        
        self.v_inner = v_all ^ v_outer
        self.v_sides = v_outer ^ self.v_ends


        # select the inside edges:
        bpy.ops.mesh.select_mode(type='EDGE')
        bpy.ops.mesh.select_all(action='DESELECT')        
        for e in e_all:
            if e.verts[0] not in self.v_sides and e.verts[1] not in self.v_sides:
               e.select = True


        print("Figuring out bitangents...")
        try:
            bm.normal_update()
            for v in self.v_ends:
                v[fatkey] = Vector((0.0, 0.0, 0.0))
                for e in v.link_edges:
                    if e not in e_all:
                        continue

                    v_other = e.other_vert(v)
                    if v_other in self.v_inner:
                        v[fatkey] = (v.co - v_other.co).normalized()
                        break
                
            for v in self.v_sides:
                v[fatkey] = Vector((0.0, 0.0, 0.0))
                # vectors pointing away from the connected inner verts:
                v_outward = []
                # bitangent = outer edge x this vert's normal
                # (direction gets fixed to point outward using avg of v_outward)
                v_bitangent = []
                for e in v.link_edges:
                    if e not in e_all:
                        continue

                    v_other = e.other_vert(v)
                    # vector pointing from this vert to neighbor:
                    v_edge = v.co - v_other.co
                    if v_other in self.v_inner:
                        v_outward.append(v_edge)
                    elif v_other in v_all:
                        # The outer edge looks like:
                        #  A --- v --- B
                        # v_edge would be (v-A), then (v-B)
                        # So one bitangent points up, the other down.
                        # To fix this, invert the second bitangent:
                        if len(v_bitangent) > 0:
                            v_edge = -v_edge

                        v_bitangent.append(v.normal.cross(v_edge).normalized())
                        
                net_outward = sum(v_outward, Vector((0,0,0)))
                    
                net_bitangent = sum(v_bitangent, Vector((0,0,0)))

                # fix bitangent to point outward                        
                if net_bitangent.dot(net_outward) < 0:
                    net_bitangent = -net_bitangent
                    
                v[fatkey] = net_bitangent
                v[fatkey].normalize()
        except:
            e_type, e_obj, tb = sys.exc_info()
            e_line = tb.tb_lineno
            print("ERROR: [Line ", e_line, "] Error: ", e_obj)
            return

        
            
    def execute(self, context):
        print("execute")
        object = context.object    
        
        if object:

            try:

                mesh = context.object.data
                self.bm = bmesh.from_edit_mesh(context.object.data)
                self.bm.normal_update()
                self.do_chisel(context)
            except:
                e_type, e_obj, tb = sys.exc_info()
                e_line = tb.tb_lineno
                print("ERROR: [Line ", e_line, "] Error: ", e_obj)
                tb.print_tb(10)
                return {'CANCELLED'}
        
            self.bm_original = self.bm.copy()
            self.bm_original.verts.ensure_lookup_table()

        self.bm = bmesh.from_edit_mesh(mesh)
        self.bm.verts.ensure_lookup_table()

        self.resize()
        self.bm.normal_update()

        bmesh.update_edit_mesh(mesh)

        object.update_tag(refresh={'DATA'})
        context.area.tag_redraw()

        return {'FINISHED'}

    def invoke(self, context, event):

        print("Invoke")
        bpy.ops.ed.undo_push(message="Start chisel operator")
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_z = 0.0
        if context.object:

            try:

                self.bm = bmesh.from_edit_mesh(context.object.data)
                self.bm.normal_update()
                self.do_chisel(context)
            except:
                e_type, e_obj, tb = sys.exc_info()
                e_line = tb.tb_lineno
                print("ERROR: [Line ", e_line, "] Error: ", e_obj)
                tb.print_tb(10)
                return {'CANCELLED'}
        
            self.bm.verts.ensure_lookup_table()
            self.bm_original = self.bm.copy()
            self.bm_original.verts.ensure_lookup_table()
          
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "No active object, could not finish")
            return {'CANCELLED'}

    def resize(self):
        fatkey = self.bm.verts.layers.shape.get('v_outward')
        for v in self.v_inner:
            v_old = self.bm_original.verts[v.index]
            v.co = v_old.co + (v_old.normal * self.offset_z)
        
        for v in self.v_ends:
            v_old = self.bm_original.verts[v.index]
            v.co = v_old.co + (v[fatkey] * self.offset_y)

        for v in self.v_sides:
            v_old = self.bm_original.verts[v.index]
            v.co = v_old.co + (v[fatkey] * self.offset_x)

    def modal(self, context, event):
        object = context.object
        mesh = object.data
        delta_depth = .01
        resize_event = False
        
        if event.type == 'X' and event.value == 'PRESS':
            self.lock_x = not self.lock_x
            if self.lock_x:
                self.lock_y = False
        elif event.type == 'Y' and event.value == 'PRESS':
            self.lock_y = not self.lock_y
            if self.lock_y:
                self.lock_x = False
        elif event.type == 'WHEELUPMOUSE':
            print("mouse wheel up")
            self.offset_z += delta_depth
            resize_event = True
        elif event.type == 'WHEELDOWNMOUSE':
            print("mouse wheel down")            
            self.offset_z -= delta_depth    
            resize_event = True
        elif event.type == 'MOUSEMOVE':
            if not self.lock_y:
                self.offset_x += (event.mouse_x - event.mouse_prev_x) / 1000.0

            if not self.lock_x:
                self.offset_y += (event.mouse_y - event.mouse_prev_y) / 1000.0

            resize_event = True
        
        if resize_event:

            self.resize()
            self.bm.normal_update()


            header_msg = "Width: {} Height: {} Depth: {}".format(
                self.offset_x, self.offset_y, self.offset_z)
            if self.lock_x:
                header_msg += " only Width"
            if self.lock_y:
                header_msg += " only Height"

            context.area.header_text_set(header_msg)
            
            object.update_tag(refresh={'DATA'})
            context.area.tag_redraw()
            
        elif event.type == 'LEFTMOUSE':
            self.bm.normal_update()
            object.update_tag(refresh={'DATA'})            
            context.area.header_text_set()
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            # just returning 'CANCELLED' seems to leave the new geometry
            bpy.ops.ed.undo()
            context.area.header_text_set()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}
    

def register():
    bpy.utils.register_class(ChiselOperator)
def unregister():
    bpy.utils.unregister_class(ChiselOperator)
if __name__ == "__main__":
    register()
