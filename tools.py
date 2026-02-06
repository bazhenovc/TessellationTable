import bpy
import bmesh
from mathutils import Vector

def relax_vertices(bm, iterations=1, factor=1.0):
    for _ in range(iterations):
        new_positions = {}
        
        for vert in bm.verts:
            if vert.is_boundary:
                continue
            
            if len(vert.link_edges) > 0:
                neighbor_avg = Vector((0, 0, 0))
                neighbor_count = 0
                
                for edge in vert.link_edges:
                    other_vert = edge.other_vert(vert)
                    neighbor_avg += other_vert.co
                    neighbor_count += 1
                
                neighbor_avg /= neighbor_count
                new_positions[vert.index] = vert.co.lerp(neighbor_avg, factor)

        for vert in bm.verts:
            if vert.index in new_positions:
                vert.co = new_positions[vert.index]


class MESH_OT_relax_vertices(bpy.types.Operator):
    """Relax non-boundary mesh vertices"""
    bl_idname = "mesh.relax_vertices"
    bl_label = "Relax Vertices"
    bl_options = {'REGISTER', 'UNDO'}
    
    iterations: bpy.props.IntProperty(
        name="Iterations",
        description="Number of relaxation iterations",
        default=100,
        min=1,
        max=100
    )
    
    factor: bpy.props.FloatProperty(
        name="Factor",
        description="Relaxation strength",
        default=1.0,
        min=0.0,
        max=1.0
    )
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'
    
    def execute(self, context):
        obj = context.active_object
        me = obj.data
        
        bm = bmesh.from_edit_mesh(me)

        relax_vertices(bm, iterations=self.iterations, factor=self.factor)

        bmesh.update_edit_mesh(me)
        
        return {'FINISHED'}


class MESH_OT_subdivide_long_edges(bpy.types.Operator):
    """Subdivide edges longer than the shortest boundary edge"""
    bl_idname = "mesh.subdivide_long_edges"
    bl_label = "Subdivide Long Edges"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'
    
    def execute(self, context):
        obj = context.active_object
        me = obj.data

        bm = bmesh.from_edit_mesh(me)
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        
        if not boundary_edges:
            self.report({'WARNING'}, "No boundary edges found")
            return {'CANCELLED'}
        
        min_boundary_length = min(e.calc_length() for e in boundary_edges)
        threshold = min_boundary_length * 1.2

        edges_to_subdivide = [e for e in bm.edges if not e.is_boundary and e.calc_length() > threshold]
        
        if edges_to_subdivide:
            bmesh.ops.subdivide_edges(bm, edges=edges_to_subdivide, cuts=1)
            self.report({'INFO'}, f"Subdivided {len(edges_to_subdivide)} edges (threshold: {threshold:.4f})")
        else:
            self.report({'INFO'}, "No edges to subdivide")
        
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        bmesh.update_edit_mesh(me)
        
        return {'FINISHED'}


class MESH_OT_collapse_short_edges(bpy.types.Operator):
    """Collapse edges shorter than the shortest boundary edge"""
    bl_idname = "mesh.collapse_short_edges"
    bl_label = "Collapse Short Edges"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'
    
    def execute(self, context):
        obj = context.active_object
        me = obj.data

        bm = bmesh.from_edit_mesh(me)
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        
        if not boundary_edges:
            self.report({'WARNING'}, "No boundary edges found")
            return {'CANCELLED'}
        
        min_boundary_length = 0.6 * min(e.calc_length() for e in boundary_edges)
        edges_to_collapse = [e for e in bm.edges if not e.is_boundary and not e.verts[0].is_boundary and not e.verts[1].is_boundary and e.calc_length() < min_boundary_length]
        
        if edges_to_collapse:
            bmesh.ops.collapse(bm, edges=edges_to_collapse)
            self.report({'INFO'}, f"Collapsed {len(edges_to_collapse)} edges (threshold: {min_boundary_length:.4f})")
        else:
            self.report({'INFO'}, "No edges to collapse")
        
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        
        bmesh.update_edit_mesh(me)
        
        return {'FINISHED'}


class MESH_OT_merge_close_vertices(bpy.types.Operator):
    """Merges vertices closer than the shortest boundary edge"""
    bl_idname = "mesh.merge_close_vertices"
    bl_label = "Merge close vertices"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'
    
    def execute(self, context):
        obj = context.active_object
        me = obj.data
        
        bm = bmesh.from_edit_mesh(me)
        boundary_edges = [e for e in bm.edges if e.is_boundary]
        
        if not boundary_edges:
            self.report({'WARNING'}, "No boundary edges found")
            return {'CANCELLED'}
        
        min_boundary_length = 0.6 * min(e.calc_length() for e in boundary_edges)
        
        bmesh.ops.remove_doubles(bm, verts=[vert for vert in bm.verts if not vert.is_boundary], dist=min_boundary_length)
        
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        
        bmesh.update_edit_mesh(me)
        
        return {'FINISHED'}


class MESH_OT_reset_remeshing(bpy.types.Operator):
    """Delete all non-boundary edges and vertices"""
    bl_idname = "mesh.reset_remeshing"
    bl_label = "Reset Remeshing"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'
    
    def execute(self, context):
        obj = context.active_object
        me = obj.data
        
        bm = bmesh.from_edit_mesh(me)
        verts_to_delete = [v for v in bm.verts if not v.is_boundary]
        
        bmesh.ops.delete(bm, geom=verts_to_delete, context='VERTS')
        
        self.report({'INFO'}, f"Deleted {len(edges_to_delete)} edges {len(verts_to_delete)} vertices")
        
        bmesh.update_edit_mesh(me)
        
        return {'FINISHED'}


class VIEW3D_PT_mesh_remesh_panel(bpy.types.Panel):
    """Panel for mesh remeshing operators"""
    bl_label = "Manual tessellation tools"
    bl_idname = "VIEW3D_PT_mesh_remesh"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Edit'
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'
    
    def draw(self, context):
        layout = self.layout
        
        layout.operator("mesh.subdivide_long_edges")
        layout.operator("mesh.collapse_short_edges")
        layout.operator("mesh.relax_vertices")
        layout.operator("mesh.merge_close_vertices")
        layout.operator("mesh.reset_remeshing")


def register():
    bpy.utils.register_class(MESH_OT_relax_vertices)
    bpy.utils.register_class(MESH_OT_subdivide_long_edges)
    bpy.utils.register_class(MESH_OT_collapse_short_edges)
    bpy.utils.register_class(MESH_OT_merge_close_vertices)
    bpy.utils.register_class(MESH_OT_reset_remeshing)
    bpy.utils.register_class(VIEW3D_PT_mesh_remesh_panel)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_mesh_remesh_panel)
    bpy.utils.unregister_class(MESH_OT_reset_remeshing)
    bpy.utils.unregister_class(MESH_OT_merge_close_vertices)
    bpy.utils.unregister_class(MESH_OT_collapse_short_edges)
    bpy.utils.unregister_class(MESH_OT_subdivide_long_edges)
    bpy.utils.unregister_class(MESH_OT_relax_vertices)


if __name__ == "__main__":
    register()