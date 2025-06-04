import os
import re

def parse_gcode_value(line, code):
    """Extracts the value associated with a G-code letter."""
    match = re.search(rf'{code}([-+]?\d*\.?\d+)', line, re.IGNORECASE)
    return float(match.group(1)) if match else None

def get_gcode_commands(lines, command_type):
    """Extracts specific G-code commands (G0 or G1) with X, Y, F values."""
    cmds = []
    for line in lines:
        if line.strip().startswith(command_type):
            x = parse_gcode_value(line, 'X')
            y = parse_gcode_value(line, 'Y')
            f = parse_gcode_value(line, 'F')
            if x is not None and y is not None: # F can sometimes be omitted if modal
                cmds.append({'x': x, 'y': y, 'f': f})
    return cmds

def modify_gcode(filepath, num_total_layers, layer_height, logical_left_top, logical_right_bottom):
    """
    Modifies the G-code file according to the specified rules.
    """
    if not os.path.exists(filepath):
        print(f"错误：文件 {filepath} 不存在。")
        return

    base_dir = os.path.dirname(filepath)
    original_filename = os.path.basename(filepath)
    new_filename = f"better_{original_filename}"
    output_filepath = os.path.join(base_dir, new_filename)

    header_lines = []
    footer_lines = []
    # Stores {'initial_g0_xyf': (x,y,f), 'g1_commands': [{'x':x,'y':y,'f':f}, ...], 'original_layer_number': int}
    original_layers_data = [] 

    z_feed_rate = 1750.0
    travel_feed_rate = 1750.0
    
    try:
        with open(filepath, 'r') as f:
            lines = [line.rstrip('\r\n') for line in f.readlines()] # Strip newlines early

        # Parse feed rates from comments
        for line in lines:
            if "(G1 Z-only Feedrate set to:" in line:
                match = re.search(r'(\d+)\s*mm/min', line) # CORRECTED REGEX
                if match: z_feed_rate = float(match.group(1))
            if "(ALL G0 Feedrates will also use this Z-axis speed:" in line or "(G0 XY Feedrate set to:" in line:
                match = re.search(r'(\d+)\s*mm/min', line) # CORRECTED REGEX
                if match: travel_feed_rate = float(match.group(1))

        layer_section_started_idx = -1
        original_layer_counter = 0

        # --- Phase 1: Identify layer blocks and their G1 commands ---
        # We'll store G1s and the line index where the layer comment starts.
        # initial_g0_xyf will be determined in a second pass for clarity.
        
        temp_layer_blocks = [] # Stores {'comment_line_idx': idx, 'g1_commands': []}
        current_g1s_for_block = []
        current_block_comment_idx = -1

        for line_idx, line in enumerate(lines):
            stripped_line = line.strip()
            if stripped_line.startswith(";") and "--- Layer" in stripped_line:
                original_layer_counter += 1
                if current_block_comment_idx != -1 and current_g1s_for_block: # Save G1s of previous block
                    temp_layer_blocks[-1]['g1_commands'] = current_g1s_for_block
                
                temp_layer_blocks.append({'comment_line_idx': line_idx, 'g1_commands': [], 'original_layer_number': original_layer_counter})
                current_g1s_for_block = []
                current_block_comment_idx = line_idx
                if layer_section_started_idx == -1:
                    layer_section_started_idx = line_idx
            elif current_block_comment_idx != -1: # We are inside a layer block
                if stripped_line.startswith("G1") and parse_gcode_value(stripped_line, 'X') is not None:
                    x = parse_gcode_value(stripped_line, 'X')
                    y = parse_gcode_value(stripped_line, 'Y')
                    f = parse_gcode_value(stripped_line, 'F') 
                    if x is not None and y is not None and f is not None:
                         current_g1s_for_block.append({'x': x, 'y': y, 'f': f})
        
        if current_block_comment_idx != -1 and current_g1s_for_block: # Save G1s for the last block
             temp_layer_blocks[-1]['g1_commands'] = current_g1s_for_block
        
        if layer_section_started_idx != -1:
            header_lines = lines[:layer_section_started_idx]
        else: # No layer comments found, treat all as header (should not happen for valid file)
            header_lines = lines
            print("警告: 未在文件中找到层注释。")

        # --- Phase 2: Determine initial_g0_xyf for each layer block and finalize original_layers_data ---
        for i, block_info in enumerate(temp_layer_blocks):
            layer_comment_idx = block_info['comment_line_idx']
            g1s = block_info['g1_commands']
            orig_layer_num = block_info['original_layer_number']
            
            # Search for the G0 X Y [Z F] command that *immediately* precedes the first G1 of this block,
            # but *after* the previous layer's G1s (or after header for the first layer).
            search_start_idx = temp_layer_blocks[i-1]['comment_line_idx'] if i > 0 else 0
            # More accurately, search between current layer comment and first G1 of current layer
            
            potential_start_g0_line_content = ""
            # Find the first G1 line index *within the current block of lines*
            # The lines for current block start from block_info['comment_line_idx']
            # and end before temp_layer_blocks[i+1]['comment_line_idx'] or end of file
            
            current_block_lines_start = block_info['comment_line_idx']
            current_block_lines_end = temp_layer_blocks[i+1]['comment_line_idx'] if i + 1 < len(temp_layer_blocks) else len(lines)

            first_g1_abs_idx = -1
            for idx_in_file in range(current_block_lines_start, current_block_lines_end):
                line_content = lines[idx_in_file].strip()
                if line_content.startswith("G1") and parse_gcode_value(line_content, "X") is not None:
                    first_g1_abs_idx = idx_in_file
                    break
            
            if first_g1_abs_idx != -1:
                # Search backwards from the first G1 of this layer up to its layer comment
                for l_idx_abs in range(first_g1_abs_idx - 1, block_info['comment_line_idx'] -1, -1): # Stop before layer comment
                    l_content = lines[l_idx_abs].strip()
                    if l_content.startswith("G0") and parse_gcode_value(l_content, 'X') is not None and parse_gcode_value(l_content, 'Y') is not None:
                        potential_start_g0_line_content = l_content
                        break # Found the G0 right before the G1s of this layer

            g0_x, g0_y, g0_f = None, None, None
            if potential_start_g0_line_content:
                g0_x = parse_gcode_value(potential_start_g0_line_content, 'X')
                g0_y = parse_gcode_value(potential_start_g0_line_content, 'Y')
                g0_f = parse_gcode_value(potential_start_g0_line_content, 'F') or travel_feed_rate
            
            if g0_x is not None and g0_y is not None:
                initial_g0_tuple = (g0_x, g0_y, g0_f)
            else:
                # Fallback: If this original layer corresponds to one where we expect a specific start (e.g. L-T or R-B)
                # For your specific G-code:
                # Original Layer 1 & 3 start at Left-Top
                # Original Layer 2 & 4 start at Left-Top (after some travel moves)
                # So, for all original layers in your example, the printing path starts near what you defined as 'logical_left_top'
                print(f"Warning: Could not determine initial G0 for original layer {orig_layer_num} using G0 search. Defaulting to logical_left_top for its path start.")
                initial_g0_tuple = (logical_left_top[0], logical_left_top[1], travel_feed_rate)

            original_layers_data.append({
                'initial_g0_xyf': initial_g0_tuple,
                'g1_commands': g1s,
                'original_layer_number': orig_layer_num
            })
            if not g1s:
                print(f"Warning: Original layer {orig_layer_num} has no G1 printing commands.")

        # Determine footer lines
        last_content_line_idx = len(lines) -1 
        if temp_layer_blocks: # If layers were found
            last_layer_block = temp_layer_blocks[-1]
            # Footer starts after all G1s of the last layer.
            # Find the index of the last G1 command of the last layer.
            last_g1_line_idx_in_file = -1
            if last_layer_block['g1_commands']:
                # Search from end of file backwards to find the last G1 command of the last layer
                # This is a bit simplified, assumes G1s are contiguous after comment
                start_search_for_last_g1 = last_layer_block['comment_line_idx']
                for line_idx_from_end in range(len(lines) - 1, start_search_for_last_g1 -1, -1):
                    if lines[line_idx_from_end].strip().startswith("G1") and parse_gcode_value(lines[line_idx_from_end], "X") is not None:
                        last_g1_line_idx_in_file = line_idx_from_end
                        break
            
            if last_g1_line_idx_in_file != -1:
                last_content_line_idx = last_g1_line_idx_in_file

        footer_lines = lines[last_content_line_idx + 1:]
        if not footer_lines: # Generic footer if parsing failed to find one
             footer_lines = ["G0 Z12.000 F1750 ; Final safe Z lift", "G0 X0 Y0 F1750 ; Optional: Return to origin", "M30 ; Program End"]


        if not original_layers_data:
            print("错误：未能从原始文件中解析出任何层数据。")
            return

    except Exception as e:
        print(f"解析原始 G-code 文件时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return

    # Generate new G-code
    new_gcode_lines = [line for line in header_lines] # Already stripped

    for i in range(num_total_layers):
        current_layer_num = i + 1
        current_z = current_layer_num * layer_height
        
        new_gcode_lines.append(f"; (--- Layer {current_layer_num} @ Z={current_z:.3f} ---)")
        new_gcode_lines.append(f"G1 Z{current_z:.3f} F{z_feed_rate:.1f}")

        data_source_idx = i % len(original_layers_data) # Cycle through original layers if needed
        source_layer_data = original_layers_data[data_source_idx]
        
        initial_g0_xyf_orig = source_layer_data['initial_g0_xyf'] # Should always exist now
        g1_commands_orig = source_layer_data['g1_commands']

        if current_layer_num == 1:
            # First layer: G0 to logical_left_top, then its G1s (from original layer 1)
            new_gcode_lines.append(f"G0 X{logical_left_top[0]:.3f} Y{logical_left_top[1]:.3f} Z{current_z:.3f} F{travel_feed_rate:.1f}")
            if g1_commands_orig:
                for cmd in g1_commands_orig:
                    new_gcode_lines.append(f"G1 X{cmd['x']:.3f} Y{cmd['y']:.3f} F{cmd['f']:.1f}")
            else: # No G1s, explicitly move to logical_right_bottom
                new_gcode_lines.append(f"; Warning: Source for Layer 1 had no G1 commands. Moving to logical_right_bottom.")
                new_gcode_lines.append(f"G0 X{logical_right_bottom[0]:.3f} Y{logical_right_bottom[1]:.3f} F{travel_feed_rate:.1f}")
            # End of Layer 1 is at logical_right_bottom (or where G1s ended)

        else: # Subsequent layers
            if current_layer_num % 2 == 1: # Odd layer (3, 5, ...) -> Path L-T to R-B
                # Starts at logical_left_top (where previous even layer ended)
                # No G0 to L-T needed as previous layer should end there.
                # Uses G1 commands from source_layer_data as is.
                if g1_commands_orig:
                    for cmd in g1_commands_orig: 
                        new_gcode_lines.append(f"G1 X{cmd['x']:.3f} Y{cmd['y']:.3f} F{cmd['f']:.1f}")
                else: # If original G1s are empty, explicitly move from L-T to R-B
                    new_gcode_lines.append(f"; Warning: Source for Layer {current_layer_num} had no G1. Moving from L-T to R-B.")
                    new_gcode_lines.append(f"G0 X{logical_right_bottom[0]:.3f} Y{logical_right_bottom[1]:.3f} F{travel_feed_rate:.1f}")
                # End of odd layer is at logical_right_bottom (or where G1s ended)

            else: # Even layer (2, 4, ...) -> Path R-B to L-T (reversed)
                # Starts at logical_right_bottom (where previous odd layer ended)
                # No G0 to R-B needed as previous layer should end there.
                if g1_commands_orig:
                    # Original path points: P0 (initial_g0_xyf_orig) -> P1 (g1_cmd[0]) -> ... -> PN (g1_cmd[N-1])
                    # We need to generate G1 moves to: P(N-1), P(N-2), ..., P0
                    
                    # Points in the original G1 path including the start point.
                    # The G1 commands define the *target* of the move.
                    # The first point of the path is initial_g0_xyf_orig's XY.
                    points_in_orig_path = [(initial_g0_xyf_orig[0], initial_g0_xyf_orig[1])] + \
                                          [{'x': cmd['x'], 'y': cmd['y']} for cmd in g1_commands_orig]
                    
                    feeds_for_orig_segments = [cmd['f'] for cmd in g1_commands_orig]

                    if len(points_in_orig_path) > 1 and len(feeds_for_orig_segments) == (len(points_in_orig_path) - 1):
                        # To reverse:
                        # New G1 targets are: points_in_orig_path[len-2], ..., points_in_orig_path[0]
                        # New G1 feeds are: feeds_for_orig_segments[len-1], ..., feeds_for_orig_segments[0] (reversed order of feeds)
                        
                        num_segments = len(feeds_for_orig_segments)
                        for k in range(num_segments):
                            # Target point for this reversed G1 move is points_in_orig_path[num_segments - 1 - k]
                            # (This targets points from P(N-1) down to P0)
                            target_pt_idx_in_orig = num_segments - 1 - k # Index into points_in_orig_path
                            
                            target_x = points_in_orig_path[target_pt_idx_in_orig]['x'] if isinstance(points_in_orig_path[target_pt_idx_in_orig], dict) else points_in_orig_path[target_pt_idx_in_orig][0]
                            target_y = points_in_orig_path[target_pt_idx_in_orig]['y'] if isinstance(points_in_orig_path[target_pt_idx_in_orig], dict) else points_in_orig_path[target_pt_idx_in_orig][1]
                            
                            # The feed rate for the segment ending at points_in_orig_path[target_pt_idx_in_orig]
                            # is feeds_for_orig_segments[target_pt_idx_in_orig] IF target_pt_idx_in_orig > 0
                            # More simply, use the reversed list of feeds.
                            feed_val = feeds_for_orig_segments[num_segments - 1 - k]
                            new_gcode_lines.append(f"G1 X{target_x:.3f} Y{target_y:.3f} F{feed_val:.1f}")
                    elif g1_commands_orig:
                         new_gcode_lines.append(f"; Warning: Could not correctly reverse path for layer {current_layer_num} due to point/feed mismatch for source {source_layer_data['original_layer_number']}.")
                         new_gcode_lines.append(f"; Fallback: Moving to logical_left_top for layer {current_layer_num}")
                         new_gcode_lines.append(f"G0 X{logical_left_top[0]:.3f} Y{logical_left_top[1]:.3f} F{travel_feed_rate:.1f}")
                else: # No G1 commands in source
                    new_gcode_lines.append(f"; Warning: Source for Layer {current_layer_num} had no G1. Moving to logical_left_top.")
                    new_gcode_lines.append(f"G0 X{logical_left_top[0]:.3f} Y{logical_left_top[1]:.3f} F{travel_feed_rate:.1f}")
                # End of even layer is at logical_left_top

    new_gcode_lines.extend([line for line in footer_lines]) # Already stripped

    try:
        with open(output_filepath, 'w') as f:
            for line in new_gcode_lines:
                f.write(line + "\n")
        print(f"成功！修改后的文件已保存到: {output_filepath}")
    except Exception as e:
        print(f"写入输出文件时发生错误: {e}")


if __name__ == '__main__':
    print("G-code 修改脚本")
    
    while True:
        filepath_in = input("请输入原始 .nc 文件的完整路径: ").strip()
        if os.path.isfile(filepath_in):
            break
        print("文件路径无效，请重新输入。")

    while True:
        try:
            layers_in = int(input("请输入您希望生成的总层数 (偶数, 4-20): ").strip())
            if layers_in % 2 == 0 and 4 <= layers_in <= 20:
                break
            print("总层数必须是4到20之间的偶数。")
        except ValueError:
            print("请输入一个有效的整数。")

    while True:
        try:
            layer_height_in = float(input("请输入每层层高 (例如 0.5): ").strip())
            if layer_height_in > 0:
                break
            print("层高必须是正数。")
        except ValueError:
            print("请输入一个有效的数字。")
    
    print("\n请输入路径的逻辑边界点坐标:")
    while True:
        try:
            lt_x_in = float(input("  左上角 X 坐标 (例如 2.558): ").strip())
            lt_y_in = float(input("  左上角 Y 坐标 (例如 18.790): ").strip())
            logical_left_top_in = (lt_x_in, lt_y_in)
            break
        except ValueError:
            print("坐标请输入有效的数字。")
            
    while True:
        try:
            rb_x_in = float(input("  右下角 X 坐标 (例如 18.558): ").strip())
            rb_y_in = float(input("  右下角 Y 坐标 (例如 2.790): ").strip())
            logical_right_bottom_in = (rb_x_in, rb_y_in)
            break
        except ValueError:
            print("坐标请输入有效的数字。")

    modify_gcode(filepath_in, layers_in, layer_height_in, logical_left_top_in, logical_right_bottom_in)

