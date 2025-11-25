import cairosvg
import os

icons = [
    "porticonr", "porticoncr",
    "porticonm", "porticoncm"
]

print("Converting SVGs to PNGs with transparency...")
for name in icons:
    svg_path = f"icons/{name}.svg"
    png_path = f"icons/{name}.png"
    
    if os.path.exists(svg_path):
        try:
            cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=32, output_height=32)
            print(f"✅ Converted {svg_path} -> {png_path}")
        except Exception as e:
            print(f"❌ Error converting {name}: {e}")
    else:
        print(f"⚠️ Missing {svg_path}")

print("Done.")
