import re
import os

def process_nc_code_from_layer_2(nc_code_str: str) -> str:
    """
    处理NC代码，根据特定规则修改G代码行，但仅从 "Layer 2" 开始。

    规则：
    1. 找到注释行 "; (--- Layer ¥ @ Z=¥ ---)"，其中 ¥ (Layer编号) >= 2。
    2. 其下一行 (L1) "G* X* Y* Z* F*" 中的 "Z*" 部分提取出来。
    3. 再下一行 (L2) "G# X# Y# F#" 修改为 "G# X# Y# Z* F#"。
    4. 删除 L1，保留注释行和修改后的 L2。
    """
    lines = nc_code_str.splitlines()
    processed_lines = []
    i = 0
    while i < len(lines):
        current_line = lines[i]
        
        comment_pattern = r";\s*\(--- Layer\s*(?P<layer_num>\S+?)\s*@ Z=.*? ---\)"
        comment_match = re.match(comment_pattern, current_line)

        perform_modification = False
        if comment_match:
            layer_num_str = comment_match.group("layer_num")
            try:
                if '.' in layer_num_str:
                    layer_num = float(layer_num_str)
                else:
                    layer_num = int(layer_num_str)
                
                if layer_num >= 2:
                    perform_modification = True
            except ValueError:
                perform_modification = False
        
        if perform_modification and i + 2 < len(lines):
            line1_gcode = lines[i+1]
            line2_gcode = lines[i+2]

            z_value_match_from_line1 = re.search(r"\b(Z[\d\.\-]+)\b", line1_gcode)

            if z_value_match_from_line1:
                z_star_to_insert = z_value_match_from_line1.group(1)

                last_y_match = None
                for match in re.finditer(r"\b(Y[\d\.\-]+)\b", line2_gcode):
                    last_y_match = match
                
                first_f_after_y_match = None
                if last_y_match:
                    for match in re.finditer(r"\b(F[\d\.\-]+)\b", line2_gcode):
                        if match.start() > last_y_match.end():
                            first_f_after_y_match = match
                            break

                if last_y_match and first_f_after_y_match:
                    y_word_ends_at = last_y_match.end()
                    f_word_starts_at = first_f_after_y_match.start()
                    
                    part_before_y_inclusive = line2_gcode[:y_word_ends_at]
                    original_spacing_between_y_f = line2_gcode[y_word_ends_at:f_word_starts_at]
                    part_f_onwards_inclusive = line2_gcode[f_word_starts_at:]
                    
                    modified_line2 = f"{part_before_y_inclusive} {z_star_to_insert}{original_spacing_between_y_f}{part_f_onwards_inclusive}"
                    
                    processed_lines.append(current_line)
                    processed_lines.append(modified_line2)
                    i += 3
                    continue
                else:
                    processed_lines.append(current_line)
                    processed_lines.append(line1_gcode)
                    processed_lines.append(line2_gcode)
                    i += 3
                    continue
            else:
                processed_lines.append(current_line)
                processed_lines.append(line1_gcode)
                processed_lines.append(line2_gcode)
                i += 3
                continue
        
        processed_lines.append(current_line)
        i += 1
        
    return "\n".join(processed_lines)

def main():
    input_file_path = input("请输入NC文件的完整路径: ")

    if not os.path.isfile(input_file_path):
        print(f"错误: 文件 '{input_file_path}' 不存在或不是一个文件。")
        return

    try:
        with open(input_file_path, 'r', encoding='utf-8') as f:
            original_nc_code = f.read()
    except Exception as e:
        print(f"错误: 读取文件 '{input_file_path}' 失败: {e}")
        return

    processed_code = process_nc_code_from_layer_2(original_nc_code)

    # 构建输出文件路径
    directory, filename = os.path.split(input_file_path)
    name_part, ext_part = os.path.splitext(filename)
    output_filename = f"{name_part}_modified{ext_part}"
    output_file_path = os.path.join(directory, output_filename)

    try:
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(processed_code)
        print(f"处理完成！修改后的文件已保存到: {output_file_path}")
    except Exception as e:
        print(f"错误: 写入文件 '{output_file_path}' 失败: {e}")

if __name__ == "__main__":
    main()
