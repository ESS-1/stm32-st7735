#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys

def generate_qr_code(url: str, output_prefix: str, symbol_name: str, max_size: int = None, section: str = None):
    # Ensure target directory exists (e.g., 'build/')
    output_dir = os.path.dirname(output_prefix)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Generate ASCII QR matrix (Medium ECC, 0 margin)
    try:
        res = subprocess.run(
            ['qrencode', '-s', '1', '-l', 'M', '-m', '0', '-t', 'ASCII', '-o', '-'],
            input=url,
            text=True,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Command 'qrencode' not found! Please install it via pacman:\n"
            "  MSYS2 UCRT64: pacman -S mingw-w64-ucrt-x86_64-qrencode\n"
            "  Linux/Arch:   pacman -S qrencode"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"qrencode failed: {e.stderr.strip()}")

    raw_lines = [line.rstrip('\r\n') for line in res.stdout.splitlines()]
    raw_lines = [line for line in raw_lines if len(line) > 0]

    modules_count = len(raw_lines)
    if modules_count == 0:
        raise ValueError("Empty output from qrencode!")

    expected_len = modules_count * 2
    for idx, line in enumerate(raw_lines):
        if len(line) != expected_len:
            raise ValueError(
                f"Row {idx} has invalid length {len(line)}, expected {expected_len}!"
            )

    # Check if raw QR matrix exceeds requested limit
    scale = None
    if max_size is not None:
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
    png_scale = str(scale if scale is not None else 1)
    subprocess.run(
        ['qrencode', '-s', png_scale, '-l', 'M', '-m', '0', '-t', 'PNG', '-o', png_filename],
        input=url,
        text=True,
        check=True,
    )
    scaled_width = modules_count * (scale if scale is not None else 1)
    scaled_height = scaled_width

    # ==========================================
    # GENERATE C SOURCE / HEADER
    # ==========================================
    bytes_per_row = (modules_count + 7) // 8
    total_bytes = bytes_per_row * modules_count

    # Pack bits into byte array (MSB first)
    byte_array = bytearray(total_bytes)
    for y in range(modules_count):
        row_str = raw_lines[y]
        for x in range(modules_count):
            if row_str[2 * x : 2 * x + 2] == '##': # '##' is black module
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
        if scale is not None:
            f.write(f"#define {symbol_name_upper}_SCALE_X {scale}\n")
            f.write(f"#define {symbol_name_upper}_SCALE_Y {scale}\n")
        f.write("\n")
        f.write(f"extern const uint8_t {symbol_name}_data[{total_bytes}];\n")

    # Source file (.c)
    section_attr = f'__attribute__((section("{section}"))) ' if section else ""
    with open(source_filename, "w", encoding="utf-8") as f:
        f.write("/* Auto-generated QR code data */\n")
        f.write(f'#include "{os.path.basename(header_filename)}"\n')
        f.write('\n')
        f.write("/* Packed QR matrix: 1 bit per module (1 = black, 0 = white), MSB first */\n")
        f.write(f"{section_attr}const uint8_t {symbol_name}_data[{total_bytes}] = {{\n")

        for y in range(modules_count):
            f.write("    ")
            row_bytes = byte_array[y * bytes_per_row : (y + 1) * bytes_per_row]
            f.write(", ".join([f"0x{b:02X}" for b in row_bytes]))
            f.write(",\n")

        f.write("};\n")

    print("QR code artifacts generated successfully:")
    print(f"  - Header:    {header_filename}")
    print(f"  - Source:    {source_filename}")
    print(f"  - PNG Image: {png_filename} ({scaled_width}x{scaled_height} px)")
    print(f"  - Matrix:    {modules_count}x{modules_count} quads")
    print(f"  - Array size:{total_bytes} bytes")
    if scale is not None:
        print(f"  - Scale:     {scale}x")
    if section:
        print(f"  - Section:   {section}")

def main():
    parser = argparse.ArgumentParser(
        description="Generate C source, C header, and PNG image for packed QR code."
    )
    parser.add_argument("--url", required=True, help="URL payload")
    parser.add_argument("--max-size", type=int, default=None, help="Max boundary in pixels (optional; if not provided, no scaling)")
    parser.add_argument("--out-prefix", default="qr_data", help="Output filename prefix for .h, .c, and .png files")
    parser.add_argument("--symbol", default="g_qr_code", help="C array variable name prefix")
    parser.add_argument("--section", default=None, help="Optional ELF section name")

    args = parser.parse_args()

    try:
        generate_qr_code(args.url, args.out_prefix, args.symbol, args.max_size, args.section)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
