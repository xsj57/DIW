import numpy as np
from stl import mesh
import os

# Helper function to create faces for a quadrilateral (four vertices in CCW order)
def make_quad_faces(v0_idx, v1_idx, v2_idx, v3_idx):
    return [np.array([v0_idx, v1_idx, v2_idx]), np.array([v0_idx, v2_idx, v3_idx])]

def create_hollow_layer_vertices(inner_r, outer_r, z_bottom, z_top):
    vertices = []
    half_inner_r = inner_r / 2.0
    half_outer_r = outer_r / 2.0
    vertices.append(np.array([-half_outer_r, -half_outer_r, z_bottom]))  # 0
    vertices.append(np.array([half_outer_r, -half_outer_r, z_bottom]))  # 1
    vertices.append(np.array([half_outer_r, half_outer_r, z_bottom]))  # 2
    vertices.append(np.array([-half_outer_r, half_outer_r, z_bottom]))  # 3
    vertices.append(np.array([-half_inner_r, -half_inner_r, z_bottom]))  # 4
    vertices.append(np.array([half_inner_r, -half_inner_r, z_bottom]))  # 5
    vertices.append(np.array([half_inner_r, half_inner_r, z_bottom]))  # 6
    vertices.append(np.array([-half_inner_r, half_inner_r, z_bottom]))  # 7
    vertices.append(np.array([-half_outer_r, -half_outer_r, z_top]))  # 8
    vertices.append(np.array([half_outer_r, -half_outer_r, z_top]))  # 9
    vertices.append(np.array([half_outer_r, half_outer_r, z_top]))  # 10
    vertices.append(np.array([-half_outer_r, half_outer_r, z_top]))  # 11
    vertices.append(np.array([-half_inner_r, -half_inner_r, z_top]))  # 12
    vertices.append(np.array([half_inner_r, -half_inner_r, z_top]))  # 13
    vertices.append(np.array([half_inner_r, half_inner_r, z_top]))  # 14
    vertices.append(np.array([-half_inner_r, half_inner_r, z_top]))  # 15
    return vertices

def create_hollow_layer_faces():
    faces = []
    faces.extend(make_quad_faces(0, 1, 9, 8))
    faces.extend(make_quad_faces(1, 2, 10, 9))
    faces.extend(make_quad_faces(2, 3, 11, 10))
    faces.extend(make_quad_faces(3, 0, 8, 11))
    faces.extend(make_quad_faces(4, 12, 13, 5))
    faces.extend(make_quad_faces(5, 13, 14, 6))
    faces.extend(make_quad_faces(6, 14, 15, 7))
    faces.extend(make_quad_faces(7, 15, 12, 4))
    faces.extend(make_quad_faces(8, 9, 13, 12))
    faces.extend(make_quad_faces(9, 10, 14, 13))
    faces.extend(make_quad_faces(10, 11, 15, 14))
    faces.extend(make_quad_faces(11, 8, 12, 15))
    faces.extend(make_quad_faces(0, 4, 5, 1))
    faces.extend(make_quad_faces(1, 5, 6, 2))
    faces.extend(make_quad_faces(2, 6, 7, 3))
    faces.extend(make_quad_faces(3, 7, 4, 0))
    return faces

def create_solid_cuboid_vertices(base_side_length, z_bottom, z_top):
    vertices = []
    half_side = base_side_length / 2.0
    vertices.append(np.array([-half_side, -half_side, z_bottom]))  # 0
    vertices.append(np.array([half_side, -half_side, z_bottom]))  # 1
    vertices.append(np.array([half_side, half_side, z_bottom]))  # 2
    vertices.append(np.array([-half_side, half_side, z_bottom]))  # 3
    vertices.append(np.array([-half_side, -half_side, z_top]))  # 4
    vertices.append(np.array([half_side, -half_side, z_top]))  # 5
    vertices.append(np.array([half_side, half_side, z_top]))  # 6
    vertices.append(np.array([-half_side, half_side, z_top]))  # 7
    return vertices

def create_solid_cuboid_faces():
    faces = []
    faces.extend(make_quad_faces(0,3,2,1)) 
    faces.extend(make_quad_faces(4,5,6,7)) 
    faces.extend(make_quad_faces(0,1,5,4)) 
    faces.extend(make_quad_faces(1,2,6,5)) 
    faces.extend(make_quad_faces(2,3,7,6)) 
    faces.extend(make_quad_faces(3,0,4,7)) 
    return faces

def main():
    print("--- 中空四边形金字塔 STL 生成器 (V5) ---")
    print("所有长度单位均为毫米 (mm)。")
    try:
        x_param = float(input("请输入壁厚和层高 x (mm): "))
        r_param = float(input("请输入底层内正方形边长 r (mm): "))
        y_param = float(input("请输入每层缩进值 y (mm): "))
    except ValueError:
        print("输入无效，请输入数字。")
        return

    if x_param <= 0:
        print("错误：壁厚和层高 x 必须大于 0 mm。")
        return
    if r_param <= 0: 
        print("错误：底层内正方形边长 r 必须大于 0 mm。") # Though technically it could be very small
        return
    if y_param < 0: 
        print("错误：每层缩进值 y 不能为负数。")
        return

    output_dir = "/Users/ericxu/Downloads/"
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print(f"已创建输出文件夹: {output_dir}")
        except OSError as e:
            print(f"错误：无法创建输出文件夹 {output_dir}: {e}")
            return

    all_vertices_list = []
    all_faces_list = []
    vertex_offset = 0
    
    current_layer_idx = 1
    current_inner_r = r_param # Inner side for the *current* layer if it were hollow
    
    max_layers_limit = 500 
    n_total_completed_layers = 0
    top_layer_outer_threshold_mm = 1.0 # Outer side <= 1.0mm makes it a solid top

    print(f"\n开始生成金字塔模型 (x={x_param}mm, r={r_param}mm, y={y_param}mm)...\n")

    while current_layer_idx <= max_layers_limit:
        z_bottom = (current_layer_idx - 1) * x_param
        z_top = current_layer_idx * x_param
        
        # This is the inner dimension that would be used if this layer is hollow.
        # It's based on r_param and y subtractions from previous layers.
        # current_inner_r is for the current layer being evaluated.
        
        potential_outer_side_of_layer = current_inner_r + 2 * x_param

        print(f"评估第 {current_layer_idx} 层: 使用的内边长 r_eff = {current_inner_r:.2f}mm. "
              f"计算得到的外边长 potential_outer_side = {potential_outer_side_of_layer:.2f}mm. "
              f"Z范围: [{z_bottom:.2f}mm - {z_top:.2f}mm]")

        is_top_solid_layer = False
        layer_vertices_local = None # Initialize to ensure it's assigned if layer is valid
        layer_faces_local_indices = None

        # --- REVISED LAYER DECISION LOGIC ---
        # Condition 1: Is this layer the TOP SOLID layer?
        # True if its potential_outer_side is > 0 AND <= threshold.
        if 0 < potential_outer_side_of_layer <= top_layer_outer_threshold_mm:
            is_top_solid_layer = True
            top_cuboid_actual_side_length = potential_outer_side_of_layer
            print(f"  决策: 第 {current_layer_idx} 层成为顶层 (实心六面体)。")
            print(f"        其外边长 ({top_cuboid_actual_side_length:.2f}mm) <= {top_layer_outer_threshold_mm}mm (且 > 0mm)。")
            print(f"        生成实心六面体: 底边长 {top_cuboid_actual_side_length:.2f}mm, 高 {x_param:.2f}mm。")
            layer_vertices_local = create_solid_cuboid_vertices(top_cuboid_actual_side_length, z_bottom, z_top)
            layer_faces_local_indices = create_solid_cuboid_faces()

        # Condition 2: If NOT the top solid layer, can it be a HOLLOW layer?
        # True if potential_outer_side > threshold AND current_inner_r for *this* layer is positive.
        elif potential_outer_side_of_layer > top_layer_outer_threshold_mm:
            if current_inner_r > 0: # Inner dimension must be valid for a hollow layer
                actual_outer_side_for_hollow = potential_outer_side_of_layer
                print(f"  决策: 第 {current_layer_idx} 层是空心层。")
                print(f"        外边长 ({actual_outer_side_for_hollow:.2f}mm) > {top_layer_outer_threshold_mm}mm。")
                print(f"        内边长 ({current_inner_r:.2f}mm) > 0mm。")
                layer_vertices_local = create_hollow_layer_vertices(current_inner_r, actual_outer_side_for_hollow, z_bottom, z_top)
                layer_faces_local_indices = create_hollow_layer_faces()
            else: # Cannot be hollow because inner_r is not positive (and it wasn't a top layer)
                print(f"  终止: 第 {current_layer_idx} 层不是顶层 (外边长 "
                      f"{potential_outer_side_of_layer:.2f}mm > {top_layer_outer_threshold_mm}mm)。")
                print(f"        且其内边长 ({current_inner_r:.2f}mm) 非正数，无法形成空心层。")
                if n_total_completed_layers > 0:
                    print(f"        金字塔在前一层 (第 {n_total_completed_layers} 层) 已结束。")
                else:
                    print(f"        无法生成任何初始层。")
                break # Exit while loop
        
        # Condition 3: If potential_outer_side_of_layer itself is not positive.
        else: # This implies potential_outer_side_of_layer <= 0
            print(f"  终止: 第 {current_layer_idx} 层计算得到的外边长 "
                  f"({potential_outer_side_of_layer:.2f}mm) 为非正数。无法形成任何有效层。")
            if n_total_completed_layers > 0:
                print(f"        金字塔在前一层 (第 {n_total_completed_layers} 层) 已结束。")
            else:
                print(f"        无法生成任何初始层。")
            break # Exit while loop
        # --- END OF REVISED LAYER DECISION LOGIC ---
        
        if layer_vertices_local is not None and layer_faces_local_indices is not None:
            all_vertices_list.extend(layer_vertices_local)
            for face_indices in layer_faces_local_indices:
                global_face_indices = [idx + vertex_offset for idx in face_indices]
                all_faces_list.append(np.array(global_face_indices))
            vertex_offset += len(layer_vertices_local)
            n_total_completed_layers = current_layer_idx
        else:
            # This should not be reached if breaks are working correctly, but as a safeguard:
            print(f"  警告: 第 {current_layer_idx} 层未生成几何体，尽管未明确终止循环。检查逻辑。")
            break


        if is_top_solid_layer:
            print(f"\n已到达顶层 (第 {n_total_completed_layers} 层，其外边长为 {top_cuboid_actual_side_length:.2f}mm)，金字塔生成完毕。")
            print(f"总共 {n_total_completed_layers} 层。")
            break 

        # Prepare for the NEXT layer
        current_inner_r -= y_param # This current_inner_r will be for the *next* layer evaluation
        current_layer_idx += 1
        
        if current_layer_idx > max_layers_limit : 
             print(f"\n警告: 已达到最大层数限制 ({max_layers_limit})。")
             print(f"金字塔总层数为 {n_total_completed_layers}。")
             break
    
    if n_total_completed_layers == 0 and not all_vertices_list :
        # Only print this if no layers were made and no specific termination message already printed.
        # Most termination messages are now within the loop.
        print("最终：未能生成任何几何数据。请检查输入参数是否合理。")
        return
    elif not all_vertices_list and n_total_completed_layers > 0 :
        # Should ideally not happen if n_total_completed_layers is only incremented when geometry is added
        print("警告：层数计数与实际几何数据不符。")


    if not all_vertices_list: # Final check if really nothing was generated
        if n_total_completed_layers == 0: # To avoid double message if already printed
             print("最终：确实未能生成任何几何数据。")
        return


    final_vertices_np = np.array(all_vertices_list)
    final_faces_np = np.array(all_faces_list)

    pyramid_stl_mesh = mesh.Mesh(np.zeros(final_faces_np.shape[0], dtype=mesh.Mesh.dtype))
    for i, f_indices in enumerate(final_faces_np):
        for j in range(3): 
            pyramid_stl_mesh.vectors[i][j] = final_vertices_np[f_indices[j],:]

    r_for_filename = str(r_param).replace('.', '_')
    filename = os.path.join(output_dir, f"pyramid_{r_for_filename}_{n_total_completed_layers}.stl")
    
    try:
        pyramid_stl_mesh.save(filename)
        print(f"\nSTL 文件已成功保存到: {filename}")
    except Exception as e:
        print(f"\n错误：保存 STL 文件失败: {e}")

if __name__ == '__main__':
    main()
