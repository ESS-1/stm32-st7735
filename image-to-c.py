#!/usr/bin/env python3

import sys
from PIL import Image


def rgb_to_gray16(r, g, b):
    # ITU-R BT.601 luminance
    gray = (299 * r + 587 * g + 114 * b) // 1000
    # 0..255 -> 0..15
    return (gray * 15 + 127) // 255


def rgb_to_rgb565_swapped(r, g, b):
    # Standard RGB565
    color565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | ((b & 0xF8) >> 3)
    # Byte-swap for STM32 Little-Endian -> SPI Big-Endian transfer in ST7735_DrawImage
    return ((color565 & 0xFF00) >> 8) | ((color565 & 0xFF) << 8)


def convert(filename, fmt="raw16"):
    image = Image.open(filename)

    # RGBA -> RGB, compositing onto black background
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (0, 0, 0))
        background.paste(image, mask=image.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")

    encoded = []
    fmt_enum = ""

    if fmt == "raw16":
        fmt_enum = "ImageFormat_Raw16"
        for r, g, b in image.get_flattened_data():
            encoded.append(rgb_to_rgb565_swapped(r, g, b))

    elif fmt == "rle4":
        fmt_enum = "ImageFormat_Grayscale4Rle4"
        pixels = [rgb_to_gray16(r, g, b) for r, g, b in image.get_flattened_data()]
        i = 0
        while i < len(pixels):
            value = pixels[i]
            count = 1
            while (
                i + count < len(pixels)
                and pixels[i + count] == value
                and count < 16
            ):
                count += 1

            encoded.append(((count - 1) << 4) | value)
            i += count

    else:
        print(f"Unknown format: {fmt}. Valid options: raw16, rle4", file=sys.stderr)
        sys.exit(1)

    total_pixels = image.width * image.height
    data_size_bytes = len(encoded) * 2 if fmt == "raw16" else len(encoded)

    print(f"// {image.width}x{image.height}")
    print(f"// Format: {fmt_enum}")
    print(f"// Original pixels: {total_pixels}")
    print(f"// Data size: {data_size_bytes} bytes")
    print(f"// Compression ratio: {(total_pixels * 2) / data_size_bytes:.2f}x")
    print()

    print(f"#define IMAGE_WIDTH  {image.width}")
    print(f"#define IMAGE_HEIGHT {image.height}")
    print(f"#define IMAGE_FORMAT {fmt_enum}")
    print()

    if fmt == "raw16":
        print("const uint16_t image_data[] = {")
        for i in range(0, len(encoded), 8):
            chunk = encoded[i:i + 8]
            print("    " + ", ".join(f"0x{x:04X}" for x in chunk) + ",")
        print("};")
    else:
        print("const uint8_t image_data[] = {")
        for i in range(0, len(encoded), 16):
            chunk = encoded[i:i + 16]
            print("    " + ", ".join(f"0x{x:02X}" for x in chunk) + ",")
        print("};")

    print("const size_t image_data_size = sizeof(image_data);")


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"Usage: {sys.argv[0]} image.png [raw16|rle4]", file=sys.stderr)
        sys.exit(1)

    img_file = sys.argv[1]
    format_mode = sys.argv[2] if len(sys.argv) == 3 else "raw16"

    convert(img_file, format_mode)
