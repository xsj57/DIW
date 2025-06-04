import re
import os

def get_total_layers(lines):
    """
    Determines the total number of layers by parsing layer comments.
    Returns 0 if no layer comments are found.
    """
    max_layer = 0
    for line in lines:
        match = re.search(r"; \(--- Layer (\d+)", line)
        if match:
            layer_num = int(match.group(1))
            if layer_num > max_layer:
                max_layer = layer_num
    return max_layer

def calculate_target_z_for_layers(total_layers, layers_per_block_a, initial_lh_h, delta_lh_d):
    """
    Calculates the target Z height at the end of each layer.
    Returns a list where target_z_at_layer_end[i] is the Z for layer i+1.
    """
    if total_layers == 0:
        return []

    target_z_at_layer_end = [0.0] * total_layers
    current_cumulative_z = 0.0

    print("\n调试信息: 计划的每层独立层高和累积Z值：")
    print("----------------------------------------------------")
    print("| Layer # | Block Idx | Individual LH | Cumulative Z |")
    print("|---------|-----------|---------------|--------------|")

    for i in range(total_layers):
        layer_number_1_indexed = i + 1
        block_index_0_indexed = (layer_number_1_indexed - 1) // layers_per_block_a
        
        current_individual_lh = initial_lh_h + (block_index_0_indexed * delta_lh_d)
        
        if current_individual_lh <= 0:
            print(f"警告: 计算得出 Layer {layer_number_1_indexed} 的独立层高为 {current_individual_lh:.3f}mm (<=0)。")
            print("这可能导致G-code问题。建议检查输入参数 a, h, d。")
            current_individual_lh = 0.001 
            print(f"         已将 Layer {layer_number_1_indexed} 的层高强制设为 {current_individual_lh:.3f}mm。")

        current_cumulative_z += current_individual_lh
        target_z_at_layer_end[i] = current_cumulative_z
        print(f"| {layer_number_1_indexed:<7} | {block_index_0_indexed:<9} | {current_individual_lh:<13.3f} | {current_cumulative_z:<12.3f} |")
    
    print("----------------------------------------------------\n")
    return target_z_at_layer_end

def get_last_z_indices(lines):
    """
    Finds the line index and part index of the very last Z command in the file.
    """
    last_z_line_global_idx = -1
    last_z_part_idx_in_line = -1

    for i in range(len(lines) - 1, -1, -1):
        line_content_scan = lines[i]
        stripped_line_scan = line_content_scan.strip()
        if not stripped_line_scan or stripped_line_scan.startswith(";") or stripped_line_scan.startswith("("):
            continue

        parts_scan = stripped_line_scan.split()
        found_z_in_this_line_scan = False
        for j in range(len(parts_scan) - 1, -1, -1):
            if parts_scan[j].startswith("Z"):
                try:
                    float(parts_scan[j][1:]) 
                    last_z_line_global_idx = i
                    last_z_part_idx_in_line = j
                    found_z_in_this_line_scan = True
                    break 
                except ValueError:
                    continue 
        if found_z_in_this_line_scan:
            break 
    return last_z_line_global_idx, last_z_part_idx_in_line

def process_gcode_variable_lh(input_filepath, layers_per_block_a, initial_lh_h, delta_lh_d):
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"错误：文件 '{input_filepath}' 未找到。")
        return
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return

    total_layers = get_total_layers(lines)
    if total_layers == 0:
        print("错误：在文件中未找到任何 '; (--- Layer N ...' 格式的层注释。无法确定总层数。")
        return
    print(f"文件总层数: {total_layers}")

    if layers_per_block_a <= 0:
        print("错误：每块的层数 (a) 必须是正整数。")
        return
    if initial_lh_h <= 0:
        print("错误：初始层高 (h) 必须是正数。")
        return
        
    if delta_lh_d < 0:
        num_blocks_before_zero_lh = -initial_lh_h / delta_lh_d if delta_lh_d != 0 else float('inf')
        if num_blocks_before_zero_lh < (total_layers / layers_per_block_a):
             print(f"警告: 根据输入参数，层高可能在第 {int(num_blocks_before_zero_lh) + 1} 个块变为零或负数。")

    target_z_values = calculate_target_z_for_layers(total_layers, layers_per_block_a, initial_lh_h, delta_lh_d)
    if not target_z_values:
        print("错误: 未能计算目标Z值。")
        return

    last_z_line_idx, last_z_part_idx = get_last_z_indices(lines)
    if last_z_line_idx != -1:
        print(f"调试信息: 最后一个Z指令位于原始文件行 {last_z_line_idx + 1}, Z参数索引 {last_z_part_idx}.")
        print(f"         内容: '{lines[last_z_line_idx].strip()}'")
        print(f"         Z部分: '{lines[last_z_line_idx].strip().split()[last_z_part_idx]}'")

    final_output_lines = []
    current_gcode_layer_num = 0 

    for line_idx, line_content in enumerate(lines):
        stripped_line = line_content.strip()
        
        layer_comment_match = re.search(r"; \(--- Layer (\d+)", stripped_line)
        if layer_comment_match:
            current_gcode_layer_num = int(layer_comment_match.group(1))

        if not stripped_line or stripped_line.startswith(";") or stripped_line.startswith("("):
            final_output_lines.append(line_content)
            continue

        parts = stripped_line.split()
        modified_parts = []
        line_has_changed = False

        for part_idx, part_val in enumerate(parts):
            if part_val.startswith("Z"):
                is_the_globally_last_z = (line_idx == last_z_line_idx and part_idx == last_z_part_idx)
                
                if is_the_globally_last_z:
                    modified_parts.append(part_val)
                elif current_gcode_layer_num > 0 and current_gcode_layer_num <= total_layers:
                    new_z_for_current_layer = target_z_values[current_gcode_layer_num - 1]
                    modified_parts.append(f"Z{new_z_for_current_layer:.3f}")
                    line_has_changed = True
                else:
                    modified_parts.append(part_val) 
            else:
                modified_parts.append(part_val)
        
        if line_has_changed:
            final_output_lines.append(" ".join(modified_parts) + "\n")
        else:
            final_output_lines.append(line_content)

    # --- Filename Generation START ---
    dir_name = os.path.dirname(input_filepath)
    original_full_basename = os.path.basename(input_filepath)
    original_basename_no_ext, _ = os.path.splitext(original_full_basename)
    
    h_formatted = str(initial_lh_h).replace('.', 'p')
    
    d_str = str(delta_lh_d)
    if delta_lh_d < 0:
        d_formatted = d_str.replace('.', 'p').replace('-', 'neg', 1) 
    else: 
        d_formatted = d_str.replace('.', 'p')
        if d_formatted.startswith('-'):
             d_formatted = "neg" + d_formatted[1:]

    if delta_lh_d >= 0 and d_formatted.startswith('neg'):
        d_formatted = d_formatted.replace('neg', '', 1)

    output_filename = f"{h_formatted}_{d_formatted}_{original_basename_no_ext}.nc" # MODIFIED LINE
    output_filepath = os.path.join(dir_name, output_filename)
    # --- Filename Generation END ---

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f_out:
            f_out.writelines(final_output_lines)
        print(f"\n处理完成！可变层高G-code已保存为: {output_filepath}")
    except Exception as e:
        print(f"写入输出文件时发生错误: {e}")


if __name__ == "__main__":
    print("G-code 可变层高修改脚本")
    print("------------------------------------")
    
    input_file = ""
    while not input_file:
        input_file_prompt = input("请输入源 .nc 文件的完整路径: ")
        if input_file_prompt.strip():
            input_file = input_file_prompt
            if not os.path.isfile(input_file):
                 print(f"错误: 文件 '{input_file}' 不存在或不是一个文件。请重新输入。")
                 input_file = "" 
            elif not input_file.lower().endswith((".nc", ".gcode", ".gco", ".txt")):
                 print(f"警告: 文件 '{os.path.basename(input_file)}' 的扩展名可能不是常见的G-code格式。")
        else:
            print("错误：文件路径不能为空。")

    a_layers_per_block = 0
    while a_layers_per_block <= 0:
        try:
            a_str = input("请输入每块的层数 (a, 例如 15): ")
            a_layers_per_block = int(a_str)
            if a_layers_per_block <= 0:
                print("错误：每块的层数 (a) 必须是正整数。")
        except ValueError:
            print("错误：请输入一个有效的整数。")

    h_initial_lh = 0.0
    while h_initial_lh <= 0:
        try:
            h_str = input("请输入第一个块的初始层高 (h, mm, 例如 0.35): ")
            h_initial_lh = float(h_str)
            if h_initial_lh <= 0:
                print("错误：初始层高 (h) 必须是正数。")
        except ValueError:
            print("错误：请输入一个有效的数字。")

    d_lh_increment = 0.0
    valid_d = False
    while not valid_d:
        try:
            d_str = input("请输入每个后续块层高的变化量 (d, mm, 例如 -0.05 或 0.02): ")
            d_lh_increment = float(d_str)
            valid_d = True
        except ValueError:
            print("错误：请输入一个有效的数字。")
            
    process_gcode_variable_lh(input_file, a_layers_per_block, h_initial_lh, d_lh_increment)
