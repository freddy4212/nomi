import os
import shutil

from PIL import Image

# Paths
source_dir = "/Users/freddy/Documents/251006_WiseEye2/sscma-example-we2/nomi_host/documents/nomi_logo/Color"
dest_dir = "/Users/freddy/Documents/251006_WiseEye2/sscma-example-we2/nomi_host/control_panel/frontend/public"

icon_source = os.path.join(source_dir, "I_Solid_Color.png")
logo_source = os.path.join(source_dir, "H_Standard_Color.svg")

# Ensure destination exists
os.makedirs(dest_dir, exist_ok=True)

# Copy Logo
shutil.copy(logo_source, os.path.join(dest_dir, "logo.svg"))
print(f"Copied logo.svg to {dest_dir}")

# Process Icon
try:
    img = Image.open(icon_source)
    
    # Generate PWA Icons
    img.resize((192, 192), Image.Resampling.LANCZOS).save(os.path.join(dest_dir, "pwa-192x192.png"))
    print("Generated pwa-192x192.png")
    
    img.resize((512, 512), Image.Resampling.LANCZOS).save(os.path.join(dest_dir, "pwa-512x512.png"))
    print("Generated pwa-512x512.png")
    
    # Generate Favicon
    img.save(os.path.join(dest_dir, "favicon.ico"), format='ICO', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    print("Generated favicon.ico")

    # Extract Dominant Color (Simple average of center pixel or similar)
    # Since it's a logo, let's just get the most common non-transparent color
    img = img.convert("RGBA")
    colors = img.getcolors(maxcolors=1000000)
    
    # Filter out transparent or near-transparent pixels
    valid_colors = [c for c in colors if c[1][3] > 200]
    if valid_colors:
        most_common = max(valid_colors, key=lambda x: x[0])
        r, g, b, a = most_common[1]
        hex_color = '#{:02x}{:02x}{:02x}'.format(r, g, b)
        print(f"Dominant Color: {hex_color}")
    else:
        print("Could not determine dominant color")

except Exception as e:
    print(f"Error processing images: {e}")
