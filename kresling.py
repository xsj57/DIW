import math

def generate_thick_kresling(n=6, radius=0.5, thickness=0.5, height=20, 
                           twist_angle=15, filename="thick_kresling.stl"):
    twist = math.radians(twist_angle)
    outer_r = radius + thickness/2
    inner_r = radius - thickness/2
    
    # 生成四组顶点：底部外层、底部内层、顶部外层、顶部内层
    bottom_outer, bottom_inner = [], []
    top_outer, top_inner = [], []
    
    for i in range(n):
        angle = math.radians(360/n * i)
        
        # 底部顶点
        bottom_outer.append((
            outer_r * math.cos(angle),
            outer_r * math.sin(angle),
            0.0
        ))
        bottom_inner.append((
            inner_r * math.cos(angle),
            inner_r * math.sin(angle),
            0.0
        ))
        
        # 顶部顶点（带扭转）
        top_angle = angle + twist
        top_outer.append((
            outer_r * math.cos(top_angle),
            outer_r * math.sin(top_angle),
            height
        ))
        top_inner.append((
            inner_r * math.cos(top_angle),
            inner_r * math.sin(top_angle),
            height
        ))
    
    # 生成所有三角形面
    triangles = []
    
    # 外侧壁面
    for i in range(n):
        next_i = (i+1)%n
        triangles.append((bottom_outer[i], top_outer[next_i], top_outer[i]))
        triangles.append((bottom_outer[i], bottom_outer[next_i], top_outer[next_i]))
    
    # 内侧壁面（法线方向相反）
    for i in range(n):
        next_i = (i+1)%n
        triangles.append((bottom_inner[i], top_inner[i], top_inner[next_i]))
        triangles.append((bottom_inner[i], top_inner[next_i], bottom_inner[next_i]))
    
    # 连接内外层的垂直壁面
    for i in range(n):
        next_i = (i+1)%n
        # 底部连接
        triangles.append((bottom_outer[i], bottom_inner[i], bottom_inner[next_i]))
        triangles.append((bottom_outer[i], bottom_inner[next_i], bottom_outer[next_i]))
        
        # 顶部连接
        triangles.append((top_outer[i], top_inner[next_i], top_inner[i]))
        triangles.append((top_outer[i], top_outer[next_i], top_inner[next_i]))
        
        # 侧边立柱
        triangles.append((bottom_outer[i], bottom_inner[i], top_inner[i]))
        triangles.append((bottom_outer[i], top_inner[i], top_outer[i]))
        triangles.append((bottom_inner[i], bottom_inner[next_i], top_inner[next_i]))
        triangles.append((bottom_inner[i], top_inner[next_i], top_inner[i]))
    
    # 写入STL文件
    with open(filename, 'w') as f:
        f.write("solid ThickKresling\n")
        for tri in triangles:
            v0, v1, v2 = tri
            # 计算法线
            u = (v1[0]-v0[0], v1[1]-v0[1], v1[2]-v0[2])
            v = (v2[0]-v0[0], v2[1]-v0[1], v2[2]-v0[2])
            nx = u[1]*v[2] - u[2]*v[1]
            ny = u[2]*v[0] - u[0]*v[2]
            nz = u[0]*v[1] - u[1]*v[0]
            length = math.sqrt(nx**2 + ny**2 + nz**2)
            if length > 0:
                nx /= length
                ny /= length
                nz /= length
            
            f.write(f"facet normal {nx:.6f} {ny:.6f} {nz:.6f}\n")
            f.write("  outer loop\n")
            for vertex in tri:
                f.write(f"    vertex {vertex[0]:.6f} {vertex[1]:.6f} {vertex[2]:.6f}\n")
            f.write("  endloop\n")
            f.write("endfacet\n")
        f.write("endsolid ThickKresling\n")

# 生成模型
generate_thick_kresling(n=8,
                       radius=7.5,
                       thickness=0.5,
                       height=20,
                       twist_angle=15,
                       filename="thick_kresling.stl")