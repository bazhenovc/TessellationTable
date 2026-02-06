import bpy
import bmesh
import math
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

def connect_edges(bm, verts):
    for vert0 in verts:
        for vert1 in verts[1:]:
            bm.edges.new([vert0, vert1])

def create_triangle(max_cuts, cuts_a, cuts_b, cuts_c):
    bm = bmesh.new()
    bm_v0 = bm.verts.new(Vector((-1, -1, 0)))
    bm_v1 = bm.verts.new(Vector((1, -1, 0)))
    bm_v2 = bm.verts.new(Vector((0, 1, 0)))
    bm.faces.new([bm_v0, bm_v1, bm_v2])
    
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
 
    # Fit edges to cuts
    longest_edge = max([cuts_a+1, cuts_b+1, cuts_c+1]) / (max_cuts+1)
    
    target_edge_0 = (cuts_a+1)/(max_cuts+1)
    target_edge_1 = (cuts_b+1)/(max_cuts+1)
    target_edge_2 = (cuts_c+1)/(max_cuts+1)
    
    max_iterations = 100
    iteration = 0
    while iteration < max_iterations:
        iteration=iteration+1
        
        scale_edge_0 = target_edge_0/bm.edges[0].calc_length()
        scale_edge_1 = target_edge_1/bm.edges[1].calc_length()
        scale_edge_2 = target_edge_2/bm.edges[2].calc_length()
        
        bmesh.ops.scale(bm, verts=bm.edges[0].verts, vec=(scale_edge_0, scale_edge_0, scale_edge_0))
        bmesh.ops.scale(bm, verts=bm.edges[1].verts, vec=(scale_edge_1, scale_edge_1, scale_edge_1))
        bmesh.ops.scale(bm, verts=bm.edges[2].verts, vec=(scale_edge_2, scale_edge_2, scale_edge_2))
 
    # Subdivide initial edges
    temp_edges = [bm.edges[0], bm.edges[1], bm.edges[2]]
    
    bmesh.ops.subdivide_edges(bm, edges=[temp_edges[0]], cuts=int(cuts_a))
    bmesh.ops.subdivide_edges(bm, edges=[temp_edges[1]], cuts=int(cuts_b))
    bmesh.ops.subdivide_edges(bm, edges=[temp_edges[2]], cuts=int(cuts_c))
    
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    
    # Triangulate initial state    
    target_edge_length = min([edge.calc_length() for edge in bm.edges])
    
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    
    # Generate tessellation pattern for this triangle.
    # Bail out for weird configurations that fail    
    failed = False
    num_boundary_edges = len([e for e in bm.edges if e.is_boundary])

    for _ in range(100):
        modified = False

        edges_to_subdivide = [e for e in bm.edges if not e.is_boundary and e.calc_length() > target_edge_length*1.2]
        
        if edges_to_subdivide:
            bmesh.ops.subdivide_edges(bm, edges=edges_to_subdivide, cuts=1)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            
            if num_boundary_edges != len([e for e in bm.edges if e.is_boundary]):
                failed=True
                break
            
            modified = True

        for _ in range(100):
            num_verts = len(bm.verts)
   
            bmesh.ops.remove_doubles(bm, verts=[vert for vert in bm.verts if not vert.is_boundary], dist=target_edge_length*0.6)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()

            if num_boundary_edges != len([e for e in bm.edges if e.is_boundary]):
                failed=True
                break            
            
            relax_vertices(bm)
            
            if (num_verts != len(bm.verts)):
                modified = True
            else:
                break

        if not modified or failed:
            break
    
    if not failed:
        for _ in range(100):
            num_verts = len(bm.verts)
       
            bmesh.ops.remove_doubles(bm, verts=[vert for vert in bm.verts if not vert.is_boundary], dist=target_edge_length*0.6)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            
            relax_vertices(bm)
            
            if (num_verts == len(bm.verts)):
                break
        
    if failed:
        print(f"Failed topology: {cuts_a}x{cuts_b}x{cuts_c}, do it manually")    
#        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.is_boundary], context='VERTS')
    
    # Additional failing criteria, but don't delete anything for manual inspection
    if not failed:
        too_short_edges = [edge for edge in bm.edges if edge.verts[0].is_boundary != edge.verts[1].is_boundary and edge.calc_length() < target_edge_length*0.3]
        if (len(too_short_edges) > 0):
            print(f"Failed short edge length constraint: {cuts_a}x{cuts_b}x{cuts_c}, review manually")    
            failed = True
        
        too_long_edges = [edge for edge in bm.edges if not edge.is_boundary and edge.calc_length() > target_edge_length*1.3]
        if (len(too_long_edges) > 0):
            print(f"Failed long edge length constraint: {cuts_a}x{cuts_b}x{cuts_c}, review manually")    
            failed = True
        
        vertex_3_poles = [v for v in bm.verts if not v.is_boundary and len(v.link_edges) <= 3]
        if len(vertex_3_poles) > 0:
            print(f"Failed 3-pole constraint: {cuts_a}x{cuts_b}x{cuts_c}, review manually")    
            failed = True
        
        min_triangle_area = min([f.calc_area() for f in bm.faces])
        max_triangle_area = max([f.calc_area() for f in bm.faces])
        if (min_triangle_area/max_triangle_area) < 0.1:
            print(f"Failed triangle area constraint: {cuts_a}x{cuts_b}x{cuts_c}, review manually")
            failed = True
    
    # Create mesh and object
    mesh = bpy.data.meshes.new(name=f"Mesh_Triangle_{cuts_a}_{cuts_b}_{cuts_c}")
    obj = bpy.data.objects.new(f"Triangle_{cuts_a}_{cuts_b}_{cuts_c}", mesh)
    bpy.context.collection.objects.link(obj)
    
    # Update mesh
    bm.to_mesh(mesh)
    bm.free()
    
    # Update the scene
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    return obj, failed


def create_all_triangle_combinations(min_length=1, max_length=16, step=1, spacing=20):
    import itertools
    
    lengths = list(range(min_length, max_length + 1, step))
    combinations = list(itertools.combinations_with_replacement(lengths, 3))
    grid_size = math.ceil(math.sqrt(len(combinations)))
    
    for idx, (a, b, c) in enumerate(combinations):
        row = idx // grid_size
        col = idx % grid_size
        
        tri, failed = create_triangle(max_length, a, b, c)
        
        x = col * spacing
        y = row * spacing
        tri.location = (x, y, 0)
        
        # Put failed configurations separately
        if failed:
            tri.name += ".failed"
            tri.location[1] -= 100
        
        # Print progress
        if (idx + 1) % 100 == 0:
            print(f"Created {idx + 1}/{len(combinations)} triangles...")
    
    print(f"Created {len(combinations)} triangles!")

if __name__ == "__main__":
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    
    # Cleanup in case we interrupted previous generation
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)

    create_all_triangle_combinations(
        min_length=0, 
        max_length=15,
        step=1,
        spacing=4
    )
    
    bpy.ops.object.select_all(action='DESELECT')
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
