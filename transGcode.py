import re
import os
import datetime

def convert_marlin_to_simple_grbl(
    input_filepath, 
    output_directory, 
    output_filename_base,
    user_defined_layer_height, 
    desired_g1_xy_feedrate=None, 
    desired_g1_z_feedrate=None, # This is the "设置的z轴速度" user refers to
    fixed_g0_feedrate=1500.0    # This acts as a fallback for G0 if desired_g1_z_feedrate is not set
):
    output_lines = []
    effective_layer_number = 0 
    current_target_z_for_output = 0.0 
    last_original_z_that_started_a_layer = None 
    initial_overall_z_setup_move_processed = False
    first_actual_layer_z_processed = False

    output_lines.append("G21 ; 设置单位为毫米")
    output_lines.append("G90 ; 使用绝对坐标模式")
    output_lines.append(f"; (Converted from Marlin: {os.path.basename(input_filepath)})")
    output_lines.append(f"; (User-defined layer height for Z calculation: {user_defined_layer_height:.3f}mm)")
    if desired_g1_xy_feedrate:
        output_lines.append(f"; (G1 XY Feedrate set to: {desired_g1_xy_feedrate:.0f} mm/min)")
    else:
        output_lines.append("; (G1 XY Feedrate from original file where available)")
    
    if desired_g1_z_feedrate is not None:
        output_lines.append(f"; (G1 Z-only Feedrate set to: {desired_g1_z_feedrate:.0f} mm/min)")
        output_lines.append(f"; (ALL G0 Feedrates will also use this Z-axis speed: {desired_g1_z_feedrate:.0f} mm/min)")
    else:
        output_lines.append("; (G1 Z-only Feedrate from original file or XY feedrate)")
        output_lines.append(f"; (ALL G0 Feedrates will use default G0 speed: {fixed_g0_feedrate:.0f} mm/min as specific Z-axis speed was not set for G0s)")
    output_lines.append("; (G28 Home command removed)")
    output_lines.append("")

    g28_found_and_removed_once = False

    try:
        with open(input_filepath, 'r', encoding='utf-8') as f:
            for original_line_with_nl in f:
                original_line = original_line_with_nl.strip()
                line_to_parse = original_line
                comment_original = ""
                
                if ';' in line_to_parse:
                    parts = line_to_parse.split(';', 1)
                    line_to_parse = parts[0].strip()
                    comment_original = "; " + parts[1].strip()

                if not line_to_parse and not comment_original.startswith(";LAYER:") and not comment_original.startswith(";TYPE:") and not comment_original.startswith(";MESH:"):
                    continue

                if line_to_parse.startswith("M104") or \
                   line_to_parse.startswith("M105") or \
                   line_to_parse.startswith("M109") or \
                   line_to_parse.startswith("M140") or \
                   line_to_parse.startswith("M190") or \
                   line_to_parse.startswith("M106") or \
                   line_to_parse.startswith("M107") or \
                   line_to_parse.startswith("M82") or \
                   line_to_parse.startswith("M83") or \
                   line_to_parse.startswith("M84") or \
                   re.match(r"^G92\s+E", line_to_parse, re.IGNORECASE) or \
                   line_to_parse.upper() == "G92":
                    continue
                
                if line_to_parse.upper().startswith("G28"):
                    if not g28_found_and_removed_once:
                        g28_found_and_removed_once = True
                    continue
                
                if line_to_parse.upper().startswith("G0") or line_to_parse.upper().startswith("G1"):
                    command_match = re.match(r"(G[01])\s*(.*)", line_to_parse, re.IGNORECASE)
                    if not command_match:
                        continue
                    
                    command = command_match.group(1).upper()
                    params_str = command_match.group(2)
                    
                    params = {"X": None, "Y": None, "Z": None, "F": None}
                    original_z_in_current_line = None 
                    
                    param_tokens = re.findall(r"([XYZF])([-\d.]+)", params_str, re.IGNORECASE)
                    e_axis_present = "E" in params_str.upper()

                    for axis_char, value_str in param_tokens:
                        axis = axis_char.upper()
                        try:
                            value = float(value_str)
                            if axis in params:
                                params[axis] = value
                                if axis == "Z":
                                    original_z_in_current_line = value
                        except ValueError:
                            pass 
                    
                    if command == "G1" and params["X"] is None and params["Y"] is None and params["Z"] is None and e_axis_present:
                        continue
                    if params["X"] is None and params["Y"] is None and params["Z"] is None:
                         if not (command == "G0" and e_axis_present):
                             continue

                    output_z_value = None 

                    if original_z_in_current_line is not None:
                        current_original_z_val_rounded = round(original_z_in_current_line, 3)

                        if not initial_overall_z_setup_move_processed and command == "G0": 
                            output_z_value = original_z_in_current_line 
                            initial_overall_z_setup_move_processed = True
                        
                        elif not first_actual_layer_z_processed: 
                            effective_layer_number = 1
                            current_target_z_for_output = user_defined_layer_height * effective_layer_number
                            output_z_value = current_target_z_for_output
                            output_lines.append(f"\n; (--- Layer {effective_layer_number} @ Z={current_target_z_for_output:.3f} ---){comment_original if 'LAYER:' in comment_original.upper() else ''}")
                            last_original_z_that_started_a_layer = current_original_z_val_rounded
                            first_actual_layer_z_processed = True
                        
                        elif abs(current_original_z_val_rounded - last_original_z_that_started_a_layer) > 0.001: 
                            effective_layer_number += 1
                            current_target_z_for_output = user_defined_layer_height * effective_layer_number
                            output_z_value = current_target_z_for_output
                            output_lines.append(f"\n; (--- Layer {effective_layer_number} @ Z={current_target_z_for_output:.3f} ---){comment_original if 'LAYER:' in comment_original.upper() else ''}")
                            last_original_z_that_started_a_layer = current_original_z_val_rounded
                        
                        elif first_actual_layer_z_processed: 
                             output_z_value = current_target_z_for_output
                    
                    new_line_parts = [command]
                    if params["X"] is not None: new_line_parts.append(f"X{params['X']:.3f}")
                    if params["Y"] is not None: new_line_parts.append(f"Y{params['Y']:.3f}")
                    if output_z_value is not None: new_line_parts.append(f"Z{output_z_value:.3f}")
                    
                    current_line_had_x_param = params["X"] is not None
                    current_line_had_y_param = params["Y"] is not None
                    current_line_outputs_z = output_z_value is not None

                    is_z_only_move_based_on_current_gcode_params = current_line_outputs_z and \
                                                                   not current_line_had_x_param and \
                                                                   not current_line_had_y_param
                    
                    if command == "G0":
                        if desired_g1_z_feedrate is not None:
                            new_line_parts.append(f"F{desired_g1_z_feedrate:.0f}")
                        else:
                            new_line_parts.append(f"F{fixed_g0_feedrate:.0f}")
                    elif command == "G1":
                        if is_z_only_move_based_on_current_gcode_params:
                            if desired_g1_z_feedrate is not None:
                                new_line_parts.append(f"F{desired_g1_z_feedrate:.0f}")
                            elif params["F"] is not None: 
                                new_line_parts.append(f"F{params['F']:.0f}")
                            elif desired_g1_xy_feedrate is not None: 
                                new_line_parts.append(f"F{desired_g1_xy_feedrate:.0f}")
                        else: 
                            if desired_g1_xy_feedrate is not None:
                                new_line_parts.append(f"F{desired_g1_xy_feedrate:.0f}")
                            elif params["F"] is not None:
                                new_line_parts.append(f"F{params['F']:.0f}")
                    
                    if len(new_line_parts) > 1 :
                         output_lines.append(" ".join(new_line_parts) + (f" {comment_original}" if "TYPE:" in comment_original or "MESH:" in comment_original else ""))

                elif line_to_parse.upper().startswith("M30") or line_to_parse.upper().startswith("M2"):
                    break 
                
                elif line_to_parse.startswith(";"):
                    if "LAYER:" in line_to_parse.upper() or \
                       "TYPE:" in line_to_parse.upper() or \
                       "MESH:" in line_to_parse.upper() or \
                       "TIME_ELAPSED" in line_to_parse.upper() or \
                       line_to_parse.startswith(";FLAVOR:") or \
                       line_to_parse.startswith(";TIME:") or \
                       line_to_parse.startswith(";Filament used:") or \
                       line_to_parse.startswith(";Layer height:"):
                        output_lines.append(original_line)
                    
        add_m30 = True
        for ln in reversed(output_lines):
            if ln.strip().upper().startswith("M30"):
                add_m30 = False
                break
        
        if add_m30:
            final_z_lift_val = 10.0 
            if first_actual_layer_z_processed:
                final_z_lift_val = current_target_z_for_output + 10.0
            elif initial_overall_z_setup_move_processed :
                temp_z_initial = 10.0 
                for line_val in output_lines:
                    if line_val.strip().startswith("G0 Z") or line_val.strip().startswith("G1 Z"):
                         z_match = re.search(r'Z([-\d.]+)', line_val, re.IGNORECASE)
                         if z_match:
                            try:
                                temp_z_initial = float(z_match.group(1)) + 10.0
                                break 
                            except ValueError:
                                pass
                final_z_lift_val = temp_z_initial

            final_g0_feedrate_to_use = fixed_g0_feedrate 
            if desired_g1_z_feedrate is not None:
                final_g0_feedrate_to_use = desired_g1_z_feedrate
            
            output_lines.append(f"\nG0 Z{final_z_lift_val:.3f} F{final_g0_feedrate_to_use:.0f} ; Final safe Z lift")
            output_lines.append(f"G0 X0 Y0 F{final_g0_feedrate_to_use:.0f} ; Optional: Return to origin")
            output_lines.append("M30 ; Program End")

        output_filename = f"{output_filename_base}.nc"
        full_output_path = os.path.join(output_directory, output_filename)

        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
            print(f"创建目录: {output_directory}")

        with open(full_output_path, 'w', encoding='utf-8') as outfile:
            for out_line in output_lines:
                outfile.write(out_line + "\n")
        
        print(f"转换完成。文件已保存到: {full_output_path}")
        return full_output_path

    except FileNotFoundError:
        print(f"错误: 输入文件未找到 {input_filepath}")
        return None
    except Exception as e:
        print(f"转换过程中发生错误: {e}")
        import traceback
        traceback.print_exc() 
        return None

if __name__ == '__main__':
    raw_marlin_file_path = input("请输入Marlin G-code文件路径: ")
    marlin_file_path = raw_marlin_file_path.replace("\\\\", "/")
    print(f"提示：处理后的文件路径为: {marlin_file_path}")

    output_name_base_input = input("请输入输出文件的期望名称 (无需扩展名, 留空则使用原文件名): ")
    if not output_name_base_input: 
        output_name_base_input = os.path.splitext(os.path.basename(marlin_file_path))[0]
        print(f"提示：输出文件名将使用原文件名基础: '{output_name_base_input}'")

    default_save_dir = "/Users/ericxu/Downloads/"  # Make sure this path is correct for your system
    default_save_dir = default_save_dir.replace("\\\\", "/")

    while True:
        try:
            user_lh_str = input("请输入你希望的层高 (mm): ") 
            user_lh = float(user_lh_str)
            if user_lh <= 0:
                print("错误：层高必须是正数。")
            else:
                break
        except ValueError:
            print("错误：请输入有效的数字作为层高。")

    str_g1_xy_feed = input("请输入G1 XY轴移动速度 (mm/min, 留空则尝试保留原始F值): ")
    g1_xy_feed = float(str_g1_xy_feed) if str_g1_xy_feed else None

    str_g1_z_feed = input("请输入G1 Z轴纯移动速度 (mm/min, 留空则尝试保留原始F值或使用XY速度): ")
    g1_z_feed = float(str_g1_z_feed) if str_g1_z_feed else None 
    
    fixed_g0_speed = 1750.0 
    
    if g1_z_feed is not None:
        print(f"提示: 所有 G0 快速移动速度将设置为您输入的G1 Z轴速度: {g1_z_feed:.0f} mm/min。")
    else:
        print(f"提示: 所有 G0 快速移动速度将使用默认值: {fixed_g0_speed:.0f} mm/min (因为未指定G1 Z轴速度以覆盖G0速度)。")
    
    print("提示: G28 归位指令将被移除。")
    print(f"提示: 输出G-code中的Z值将基于您设定的层高 {user_lh:.3f}mm 进行计算 (第N层Z = {user_lh:.3f} * N)。")

    if os.path.exists(marlin_file_path):
        convert_marlin_to_simple_grbl(
            marlin_file_path, 
            default_save_dir, 
            output_name_base_input, 
            user_defined_layer_height=user_lh,
            desired_g1_xy_feedrate=g1_xy_feed,
            desired_g1_z_feedrate=g1_z_feed, 
            fixed_g0_feedrate=fixed_g0_speed
        )
    else:
        print(f"错误: 文件 '{marlin_file_path}' 不存在。请检查路径。")
