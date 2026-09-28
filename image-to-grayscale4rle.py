#!/usr/bin/env python3

import sys
from PIL import Image


def rgb_to_gray16(r, g, b):
    # ITU-R BT.601 luminance
    gray = (299 * r + 587 * g + 114 * b) // 1000

    # 0..255 -> 0..15
    return (gray * 15 + 127) // 255


def convert(filename):
    image = Image.open(filename)

    # RGBA -> RGB, compositing onto black background
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (0, 0, 0))
        background.paste(image, mask=image.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")

    pixels = []

    for r, g, b in image.getdata():
        pixels.append(rgb_to_gray16(r, g, b))

    # RLE
    encoded = []

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

    print(f"// {image.width}x{image.height}")
    print(f"// Original pixels: {len(pixels)}")
    print(f"// Compressed bytes: {len(encoded)}")
    print(f"// Compression ratio: {len(pixels) / len(encoded):.2f}x")
    print()

    print("const uint8_t image_data[] = {")

    for i in range(0, len(encoded), 16):
        chunk = encoded[i:i + 16]
        print("    " + ", ".join(f"0x{x:02X}" for x in chunk) + ",")

    print("};")
    print(f"const size_t image_data_size = sizeof(image_data);")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} image.png", file=sys.stderr)
        sys.exit(1)

    convert(sys.argv[1])
