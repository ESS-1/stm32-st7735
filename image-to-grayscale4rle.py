#!/usr/bin/env python3

import sys
from PIL import Image


def rgb_to_gray16(r, g, b):
    # ITU-R BT.601 luminance
    gray = (299 * r + 587 * g + 114 * b) // 1000
    # 0..255 -> 0..15
    return (gray * 15 + 127) // 255


def rgb_to_gray2(r, g, b):
    # ITU-R BT.601 luminance -> 0 or 1
    gray = (299 * r + 587 * g + 114 * b) // 1000
    return 1 if gray >= 128 else 0


def rgb_to_rgb565_be(r, g, b):
    # RGB888 -> RGB565 in Big-Endian byte order for SPI
    val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | ((b & 0xF8) >> 3)
    return (val >> 8) & 0xFF, val & 0xFF


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
            hi, lo = rgb_to_rgb565_be(r, g, b)
            encoded.append(hi)
            encoded.append(lo)

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

    elif fmt == "rle7":
        fmt_enum = "ImageFormat_Grayscale1Rle7"
        pixels = [rgb_to_gray2(r, g, b) for r, g, b in image.get_flattened_data()]
        i = 0
        while i < len(pixels):
            value = pixels[i]
            count = 1
            while (
                i + count < len(pixels)
                and pixels[i + count] == value
                and count < 128
            ):
                count += 1

            encoded.append(((count - 1) << 1) | (value & 0x01))
            i += count

    else:
        print(f"Unknown format: {fmt}. Valid options: raw16, rle4, rle7", file=sys.stderr)
        sys.exit(1)

    total_pixels = image.width * image.height

    print(f"// {image.width}x{image.height}")
    print(f"// Format: {fmt_enum}")
    print(f"// Original pixels: {total_pixels}")
    print(f"// Compressed bytes: {len(encoded)}")
    print(f"// Compression ratio: {(total_pixels * 2) / len(encoded):.2f}x")
    print()

    print(f"#define IMAGE_WIDTH  {image.width}")
    print(f"#define IMAGE_HEIGHT {image.height}")
    print(f"#define IMAGE_FORMAT {fmt_enum}")
    print()

    print("const uint8_t image_data[] = {")

    for i in range(0, len(encoded), 16):
        chunk = encoded[i:i + 16]
        print("    " + ", ".join(f"0x{x:02X}" for x in chunk) + ",")

    print("};")
    print("const size_t image_data_size = sizeof(image_data);")


if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"Usage: {sys.argv[0]} image.png [raw16|rle4|rle7]", file=sys.stderr)
        sys.exit(1)

    img_file = sys.argv[1]
    format_mode = sys.argv[2] if len(sys.argv) == 3 else "raw16"

    convert(img_file, format_mode)
