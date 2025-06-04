import re
import os

def find_and_parse_original_layer_height(lines):
    """
    Tries to find the original layer height from comments or infer from G-code.
    """
    # 1. Try to find the specific comment
    for line in lines:
        match = re.search(r"; \(User-defined layer height for Z calculation: (\d+\.\d+)mm\)", line)
        if match:
            height = float(match.group(1))
            print(f"调试信息: 从注释中找到原始层高: {height:.3f} mm")
            return height

    # 2. If not found, try to infer from Layer 1's G1 Z command (if layer comments exist)
    layer_1_g1_z_found = False
    in_layer_1_section = False
    for line_content in lines:
        if line_content.startswith("; (--- Layer 1"):
            in_layer_1_section = True
            continue
        if in_layer_1_section and line_content.strip().startswith("G1 Z"):
            try:
                parts = line_content.strip().split()
                for part in parts:
                    if part.startswith("Z"):
                        height = float(part[1:])
                        print(f"调试信息: 从 Layer 1 的第一个 G1 Z 指令推断原始层高为: {height:.3f} mm")
                        return height
            except (IndexError, ValueError) as e:
                print(f"调试信息: 解析 Layer 1 的 G1 Z 指令时出错: {e}")
                pass 
        if in_layer_1_section and (line_content.startswith("; (--- Layer 2") or not line_content.strip()):
            break 
            
    print("警告: 未能在文件中找到明确的原始层高注释或 Layer 1 的 G1 Z 指令。")
    print("将尝试从遇到的第一个 Z 值不为零的 G-code 推断（这可能不准确）。")
    
    for line_idx, line_content in enumerate(lines):
        stripped_line = line_content.strip()
        if stripped_line.startswith("G0 ") or stripped_line.startswith("G1 "):
            parts = stripped_line.split()
            current_layer_num_from_comment = 0
            start_search_idx = max(0, line_idx - 5) 
            for i_context in range(line_idx, start_search_idx -1, -1): 
                if i_context < len(lines): 
                    context_line = lines[i_context]
                    layer_match_with_z = re.search(r"; \(--- Layer (\d+) @ Z=(\d+\.\d+) ---\)", context_line)
                    if layer_match_with_z:
                        layer_num = int(layer_match_with_z.group(1))
                        current_layer_num_from_comment = layer_num
                        break 
                    layer_match_simple = re.search(r"; \(--- Layer (\d+)", context_line)
                    if layer_match_simple and current_layer_num_from_comment == 0:
                         current_layer_num_from_comment = int(layer_match_simple.group(1))

            for part in parts:
                if part.startswith("Z"):
                    try:
                        z_val = float(part[1:])
                        if z_val > 0: 
                            if current_layer_num_from_comment > 0: 
                                inferred_height = z_val / current_layer_num_from_comment
                                print(f"调试信息: 基于 Layer {current_layer_num_from_comment} (G-code Z={z_val:.3f}) 推断的原始层高: {inferred_height:.3f} mm")
                                return inferred_height
                            elif 0.01 < z_val < 1.0: 
                                print(f"调试信息: 基于第一个 G-code Z 值 ({z_val:.3f}) 推断层高（假设为第一层）: {z_val:.3f} mm")
                                return z_val
                    except ValueError:
                        continue 
    return None


def modify_z_values_in_file(input_filepath, new_layer_height_mm):
    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"错误：文件 '{input_filepath}' 未找到。")
        return
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return

    original_layer_height_mm = find_and_parse_original_layer_height(lines)
    if original_layer_height_mm is None or original_layer_height_mm <= 0:
        print("错误：无法确定有效的原始层高或原始层高为零/负数，无法继续处理。")
        print("请确保文件中有类似 '; (User-defined layer height for Z calculation: 0.500mm)' 的注释，")
        print("或 Layer 1 有明确的 G1 Z 指令，或者文件中的 G-code Z 值允许合理推断。")
        use_default = input("是否使用默认原始层高 0.5mm? (y/n): ").lower()
        if use_default == 'y':
            original_layer_height_mm = 0.5
            print("已使用默认原始层高 0.5mm")
        else:
            return
    
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

    if last_z_line_global_idx != -1:
        print(f"调试信息: 最后一个Z指令位于原始文件行 {last_z_line_global_idx + 1}, 内容: '{lines[last_z_line_global_idx].strip()}', Z部分: '{lines[last_z_line_global_idx].strip().split()[last_z_part_idx_in_line]}'")
    else:
        print("调试信息: 文件中未找到有效的Z指令可作为'最后一个Z'。")

    final_output_lines = []
    for current_line_idx, line_content in enumerate(lines):
        stripped_line = line_content.strip()
        if not stripped_line or stripped_line.startswith(";") or stripped_line.startswith("("):
            final_output_lines.append(line_content)
            continue

        parts = stripped_line.split()
        modified_parts = []
        line_changed_this_iteration = False 
        for current_part_idx, part_val in enumerate(parts):
            if part_val.startswith("Z"):
                if current_line_idx == last_z_line_global_idx and current_part_idx == last_z_part_idx_in_line:
                    print(f"调试信息: 跳过修改识别出的最后一个Z指令: {part_val} 在行 {current_line_idx + 1}")
                    modified_parts.append(part_val)
                else:
                    try:
                        original_z_numeric = float(part_val[1:])
                        if original_layer_height_mm <= 0: 
                            print(f"警告: 原始层高无效 ({original_layer_height_mm}), 无法计算Z的乘数 'a' 对于: {part_val}。保留原值。")
                            modified_parts.append(part_val)
                            continue
                        
                        a = 0
                        if original_z_numeric != 0 : 
                            a = original_z_numeric / original_layer_height_mm
                        
                        new_z_numeric = new_layer_height_mm * a
                        modified_parts.append(f"Z{new_z_numeric:.3f}")
                        line_changed_this_iteration = True
                    except ValueError: 
                        modified_parts.append(part_val) 
            else:
                modified_parts.append(part_val)
        
        if line_changed_this_iteration:
             final_output_lines.append(" ".join(modified_parts) + "\n")
        else:
            final_output_lines.append(line_content)

    # Output to new file
    dir_name = os.path.dirname(input_filepath)
    base_name = os.path.basename(input_filepath)
    
    # Format the new layer height for use in the filename
    # e.g., 0.2 -> "0p2", 1.0 -> "1p0", 0.125 -> "0p125"
    layer_height_filename_prefix = str(new_layer_height_mm).replace('.', 'p')
    
    output_filename = f"{layer_height_filename_prefix}_{base_name}" # MODIFIED LINE
    output_filepath = os.path.join(dir_name, output_filename)

    try:
        with open(output_filepath, 'w', encoding='utf-8') as f_out:
            f_out.writelines(final_output_lines)
        print(f"\n处理完成！修改后的文件已保存为: {output_filepath}")
    except Exception as e:
        print(f"写入输出文件时发生错误: {e}")

if __name__ == "__main__":
    print("G-code Z值修改脚本")
    print("---------------------------------")
    
    input_file = ""
    while not input_file:
        input_file_prompt = input("请输入源 .nc 文件的完整路径: ")
        if input_file_prompt.strip():
            input_file = input_file_prompt
            if not os.path.isfile(input_file):
                 print(f"错误: 文件 '{input_file}' 不存在或不是一个文件。请重新输入。")
                 input_file = "" 
            elif not input_file.lower().endswith((".nc", ".gcode", ".gco", ".txt")):
                 print(f"警告: 文件 '{os.path.basename(input_file)}' 的扩展名可能不是常见的G-code格式。请确保文件是G-code。")
        else:
            print("错误：文件路径不能为空。")

    new_lh_float = 0.0
    while True:
        new_lh_str = input("请输入新的层高 (mm，例如 0.2): ")
        try:
            new_lh_float = float(new_lh_str)
            if new_lh_float <= 0:
                print("错误：层高必须是正数。")
            else:
                break
        except ValueError:
            print("错误：请输入有效的数字作为层高。")
            
    modify_z_values_in_file(input_file, new_lh_float)
