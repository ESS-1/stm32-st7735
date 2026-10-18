#!/usr/bin/env python3

import sys
import os
import argparse
import qrcode
from PIL import Image

def generate_qr_code(url: str, max_size: int, output_prefix: str, symbol_name: str):
    # Ensure target directory exists (e.g., 'build/')
    output_dir = os.path.dirname(output_prefix)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Create QR code
    qr = qrcode.QRCode(
        version=None,  # Auto-fit smallest version
        error_correction=qrcode.constants.ERROR_CORRECT_M, # Medium error correction (~15%)
        box_size=1,    # Pixel size of each module
        border=0,      # No quiet zone padding inside raw matrix
    )

    qr.add_data(url)
    qr.make(fit=True)

    matrix = qr.get_matrix()
    modules_count = len(matrix)  # Matrix width/height in modules (quads)

    # Check if raw QR matrix exceeds requested limit
    if modules_count > max_size:
        raise ValueError(
            f"QR code size ({modules_count}x{modules_count} modules) exceeds maximum limit of {max_size}x{max_size}!"
        )

    # Calculate integer scale factor
    scale = max_size // modules_count
    if scale < 1:
        scale = 1

    # Output file paths derived from the prefix
    header_filename = f"{output_prefix}.h"
    source_filename = f"{output_prefix}.c"
    png_filename = f"{output_prefix}.png"

    # ==========================================
    # GENERATE PNG IMAGE
    # ==========================================
    base_img = qr.make_image(fill_color="black", back_color="white").convert("1")

    scaled_width = modules_count * scale
    scaled_height = modules_count * scale

    # Scale using Nearest Neighbor to keep sharp square modules
    scaled_img = base_img.resize((scaled_width, scaled_height), resample=Image.NEAREST)
    scaled_img.save(png_filename, format="PNG")

    # ==========================================
    # GENERATE C SOURCE / HEADER
    # ==========================================
    bytes_per_row = (modules_count + 7) // 8
    total_bytes = bytes_per_row * modules_count

    # Pack bits into byte array (MSB first)
    byte_array = bytearray(total_bytes)
    for y in range(modules_count):
        for x in range(modules_count):
            if matrix[y][x]:  # Dark module
                byte_idx = y * bytes_per_row + (x // 8)
                bit_idx = 7 - (x % 8)
                byte_array[byte_idx] |= (1 << bit_idx)

    # Header file (.h)
    symbol_name_upper = symbol_name.upper()
    with open(header_filename, "w", encoding="utf-8") as f:
        f.write("/* Auto-generated QR code data */\n")
        f.write("#pragma once\n")
        f.write("\n")
        f.write("#include <stdint.h>\n")
        f.write("\n")
        f.write(f"#define {symbol_name_upper}_WIDTH   {modules_count}\n")
        f.write(f"#define {symbol_name_upper}_HEIGHT  {modules_count}\n")
        f.write(f"#define {symbol_name_upper}_SCALE_X {scale}\n")
        f.write(f"#define {symbol_name_upper}_SCALE_Y {scale}\n")
        f.write("\n")
        f.write(f"extern const uint8_t {symbol_name}_data[{total_bytes}];\n")

    # Source file (.c)
    with open(source_filename, "w", encoding="utf-8") as f:
        f.write("/* Auto-generated QR code data */\n")
        f.write(f'#include "{os.path.basename(header_filename)}"\n')
        f.write('\n')
        f.write("/* Packed QR matrix: 1 bit per module (1 = black, 0 = white), MSB first */\n")
        f.write(f"const uint8_t {symbol_name}_data[{total_bytes}] = {{\n")

        for y in range(modules_count):
            f.write("    ")
            row_bytes = byte_array[y * bytes_per_row : (y + 1) * bytes_per_row]
            f.write(", ".join([f"0x{b:02X}" for b in row_bytes]))
            f.write(",\n")

        f.write("};\n")

    print(f"QR code artifacts generated successfully:")
    print(f"  - Header:    {header_filename}")
    print(f"  - Source:    {source_filename}")
    print(f"  - PNG Image: {png_filename} ({scaled_width}x{scaled_height} px)")
    print(f"  - Matrix:    {modules_count}x{modules_count} quads")
    print(f"  - Array size:{total_bytes} bytes")
    print(f"  - Scale:     {scale}x")

def main():
    parser = argparse.ArgumentParser(
        description="Generate C source, C header, and PNG image for packed QR code."
    )
    parser.add_argument("--url", required=True, help="URL payload")
    parser.add_argument("--max-size", type=int, required=True, help="Max boundary in pixels")
    parser.add_argument("--out-prefix", default="qr_data", help="Output filename prefix for .h, .c, and .png files")
    parser.add_argument("--symbol", default="g_qr_code", help="C struct variable name")

    args = parser.parse_args()

    try:
        generate_qr_code(args.url, args.max_size, args.out_prefix, args.symbol)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
