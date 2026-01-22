from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

def create_icon(filename="icon.ico", size=(256, 256)):
    # Create a new image with a transparent background
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw a rounded rectangle (as the app icon background)
    bg_color = (41, 128, 185)  # A nice flat blue
    rect_coords = [20, 20, size[0]-20, size[1]-20]
    
    # Draw rounded rectangle manually (since simple rectangle is sharp)
    # We can just draw a rectangle for simplicity or use a large circle for corner
    # For simplicity in PIL without external deps, let's draw a circle then a rect?
    # Actually, let's just draw a large circle for a modern "app" look
    draw.ellipse([10, 10, size[0]-10, size[1]-10], fill=bg_color)

    # Add text "ENC" (Encoding)
    # Try to load a default font, otherwise use default
    try:
        # Try arial.ttf on Windows
        font = ImageFont.truetype("arial.ttf", 100)
    except IOError:
        font = ImageFont.load_default()

    text = "ENC"
    
    # Calculate text position to center it
    # getbbox returns (left, top, right, bottom)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (size[0] - text_width) / 2
    y = (size[1] - text_height) / 2 - 10 # slightly adjust up
    
    draw.text((x, y), text, font=font, fill="white")
    
    # Add a small "refresh" or "swap" hint (two arrows)
    # Draw simple lines/polygons for arrows
    # Bottom arc
    
    # Save as ICO
    img.save(filename, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print(f"Icon saved to {filename}")

if __name__ == "__main__":
    create_icon()
