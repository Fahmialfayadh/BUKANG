import io
import math
import requests
import datetime
from PIL import Image, ImageOps, ImageDraw, ImageFont
from PIL.ExifTags import TAGS, GPSTAGS

def get_decimal_from_dms(dms, ref):
    """Converts Degrees, Minutes, Seconds to decimal coordinates."""
    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])
    val = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ['S', 'W']:
        val = -val
    return val

def extract_exif_gps(image_input):
    """
    Extracts latitude and longitude from photo EXIF metadata if available.
    Returns (lat, lon) tuple or (None, None).
    """
    try:
        if isinstance(image_input, Image.Image):
            img = image_input
        elif isinstance(image_input, bytes):
            img = Image.open(io.BytesIO(image_input))
        else:
            img = Image.open(image_input)

        if not hasattr(img, '_getexif') or img._getexif() is None:
            return None, None

        exif = img._getexif()
        gps_info = {}
        for tag, value in exif.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    gps_info[sub_tag] = value[t]

        if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            lat = get_decimal_from_dms(gps_info["GPSLatitude"], gps_info.get("GPSLatitudeRef", "N"))
            lon = get_decimal_from_dms(gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E"))
            return round(lat, 6), round(lon, 6)
    except Exception:
        pass
    return None, None

def reverse_geocode(lat: float, lon: float) -> str:
    """Fetches human-readable address from Lat/Lon using OpenStreetMap Nominatim API."""
    if lat is None or lon is None:
        return "Surabaya, Jawa Timur, Indonesia"

    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BUKANG_Geotag_App/1.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            address = data.get("address", {})
            parts = []
            
            road = address.get("road") or address.get("pedestrian") or address.get("path")
            suburb = address.get("suburb") or address.get("village") or address.get("neighbourhood")
            district = address.get("city_district") or address.get("county") or address.get("district")
            city = address.get("city") or address.get("town") or address.get("regency")
            state = address.get("state")
            postcode = address.get("postcode")

            if road: parts.append(road)
            if suburb: parts.append(suburb)
            if district: parts.append(f"Kec. {district}")
            if city: parts.append(city)
            if state: parts.append(state)
            if postcode: parts.append(postcode)

            if parts:
                return ", ".join(parts)
            return data.get("display_name", f"{lat:.6f}, {lon:.6f}")
    except Exception:
        pass
    return f"Koordinat: {lat:.6f}, {lon:.6f}"

def render_fallback_map_tile(width: int = 140, height: int = 140) -> Image.Image:
    """Renders a realistic local street map tile graphic if online network tiles time out."""
    img = Image.new("RGBA", (width, height), (235, 238, 230, 255))
    draw = ImageDraw.Draw(img)

    # City blocks & green areas
    draw.rectangle([10, 10, 60, 50], fill=(220, 225, 210, 255))
    draw.rectangle([70, 20, 130, 70], fill=(225, 230, 215, 255))
    draw.rectangle([15, 60, 80, 125], fill=(215, 222, 205, 255))

    # Main street avenues (white & orange)
    draw.line([(0, height * 0.45), (width, height * 0.45)], fill=(255, 255, 255, 255), width=10)
    draw.line([(0, height * 0.45), (width, height * 0.45)], fill=(253, 186, 116, 255), width=6)

    draw.line([(width * 0.5, 0), (width * 0.5, height)], fill=(255, 255, 255, 255), width=10)
    draw.line([(width * 0.5, 0), (width * 0.5, height)], fill=(253, 186, 116, 255), width=6)

    draw.line([(0, height * 0.8), (width * 0.8, 0)], fill=(255, 255, 255, 255), width=6)

    # Red Location Pushpin Marker at Center
    cx, cy = width // 2, height // 2
    draw.ellipse([cx - 9, cy - 22, cx + 9, cy - 4], fill=(239, 68, 68, 255), outline=(255, 255, 255, 255), width=2)
    draw.polygon([(cx - 5, cy - 6), (cx + 5, cy - 6), (cx, cy + 3)], fill=(239, 68, 68, 255))
    draw.ellipse([cx - 3, cy - 16, cx + 3, cy - 10], fill=(255, 255, 255, 255))

    # Map logo badge
    try:
        badge_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 9)
    except Exception:
        badge_font = ImageFont.load_default()
    draw.rectangle([2, height - 14, 45, height - 2], fill=(0, 0, 0, 180))
    draw.text((4, height - 13), "Google", fill=(255, 255, 255, 255), font=badge_font)

    return img

def fetch_static_map(lat: float, lon: float, width: int = 140, height: int = 140) -> Image.Image:
    """Fetches static map tile around (lat, lon) with a red location pushpin marker on center."""
    if lat is None or lon is None:
        return render_fallback_map_tile(width, height)

    zoom = 15
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi) / 2.0 * n)

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BUKANG_Geotag/1.0"}
    
    tile_urls = [
        f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{zoom}/{ytile}/{xtile}",
        f"https://basemaps.cartocdn.com/rastertiles/voyager/{zoom}/{xtile}/{ytile}.png",
        f"https://tile.openstreetmap.org/{zoom}/{xtile}/{ytile}.png"
    ]

    map_img = None
    for url in tile_urls:
        try:
            r = requests.get(url, headers=headers, timeout=3)
            if r.status_code == 200:
                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                map_img = img.resize((width, height), Image.Resampling.LANCZOS)
                break
        except Exception:
            continue

    if not map_img:
        return render_fallback_map_tile(width, height)

    draw = ImageDraw.Draw(map_img)
    cx, cy = width // 2, height // 2

    # Draw red location pushpin marker on center
    draw.ellipse([cx - 9, cy - 22, cx + 9, cy - 4], fill=(239, 68, 68, 255), outline=(255, 255, 255, 255), width=2)
    draw.polygon([(cx - 5, cy - 6), (cx + 5, cy - 6), (cx, cy + 3)], fill=(239, 68, 68, 255))
    draw.ellipse([cx - 3, cy - 16, cx + 3, cy - 10], fill=(255, 255, 255, 255))

    # Add Map logo badge at bottom-left corner
    try:
        badge_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 9)
    except Exception:
        badge_font = ImageFont.load_default()
    draw.rectangle([2, height - 14, 45, height - 2], fill=(0, 0, 0, 180))
    draw.text((4, height - 13), "Google", fill=(255, 255, 255, 255), font=badge_font)

    return map_img

def wrap_text(text: str, max_chars: int = 38) -> list:
    """Wraps long address text into multiple lines."""
    words = text.split(" ")
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > max_chars:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
        else:
            current_line.append(word)
            current_length += len(word) + 1
            
    if current_line:
        lines.append(" ".join(current_line))
    return lines[:3]

def compress_and_stamp_image(
    image_input,
    max_size: int = 1080,
    quality: int = 80,
    lat: float = None,
    lon: float = None,
    nrp: str = "",
    nama: str = ""
) -> bytes:
    """
    Compresses image and stamps an authentic GPS Map Camera style geotag overlay
    (Mini Map inset + Reverse Geocoded Address + Lat/Long + Timestamp + Identitas).
    """
    if isinstance(image_input, Image.Image):
        img = image_input.copy()
    elif isinstance(image_input, bytes):
        img = Image.open(io.BytesIO(image_input))
    else:
        img = Image.open(image_input)

    # 1. Correct EXIF orientation
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # 2. Resize maintaining aspect ratio
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    img_rgba = img.convert("RGBA")
    width, height = img_rgba.size

    # Prepare Geotag data
    address_str = reverse_geocode(lat, lon) if (lat and lon) else "Surabaya, Jawa Timur, Indonesia"
    time_str = datetime.datetime.now().strftime("%d/%m/%y %I:%M %p GMT+07:00")

    # Dimensions for GPS Map Camera Card Overlay
    card_w = min(width - 24, int(width * 0.95))
    card_h = int(height * 0.28) if height > 600 else 160
    card_h = max(140, min(220, card_h))

    map_size = card_h - 24

    # Fetch mini static map
    map_img = fetch_static_map(lat, lon, width=map_size, height=map_size)

    # Create composite overlay
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Card Position (Bottom-left margin 12px)
    card_x = 12
    card_y = height - card_h - 12

    # Draw dark semi-transparent card container
    draw.rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        fill=(15, 23, 42, 215),
        outline=(51, 65, 85, 255),
        width=2
    )

    # Paste Mini Map inset on left side
    overlay.paste(map_img, (card_x + 12, card_y + 12))

    # Load font
    try:
        font_main = ImageFont.truetype("DejaVuSans.ttf", max(11, int(card_h * 0.08)))
        font_bold = ImageFont.truetype("DejaVuSans-Bold.ttf", max(12, int(card_h * 0.09)))
    except Exception:
        font_main = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    # Right side text coordinates
    text_x = card_x + map_size + 24
    curr_y = card_y + 10

    # 1. Badge Header: GPS Map Camera
    draw.text((text_x, curr_y), "GPS Map Camera", fill=(56, 189, 248, 255), font=font_bold)
    curr_y += int(card_h * 0.13)

    # 2. Address Lines
    addr_lines = wrap_text(address_str, max_chars=35)
    for line in addr_lines:
        draw.text((text_x, curr_y), line, fill=(241, 245, 249, 255), font=font_main)
        curr_y += int(card_h * 0.12)

    curr_y += 2

    # 3. Lat & Long
    display_lat = lat if lat is not None else -7.281900
    display_lon = lon if lon is not None else 112.795100
    draw.text((text_x, curr_y), f"Lat  {display_lat:.6f}°", fill=(203, 213, 225, 255), font=font_main)
    curr_y += int(card_h * 0.12)
    draw.text((text_x, curr_y), f"Long {display_lon:.6f}°", fill=(203, 213, 225, 255), font=font_main)
    curr_y += int(card_h * 0.12)

    # 4. Nama & NRP + Timestamp
    id_line = f"{nama} ({nrp})" if nama or nrp else ""
    if id_line:
        draw.text((text_x, curr_y), id_line, fill=(251, 191, 36, 255), font=font_bold)
        curr_y += int(card_h * 0.12)

    draw.text((text_x, curr_y), time_str, fill=(148, 163, 184, 255), font=font_main)

    # Composite overlay onto original image
    stamped_img = Image.alpha_composite(img_rgba, overlay).convert("RGB")

    # Save to buffer as JPEG
    buf = io.BytesIO()
    stamped_img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

def get_image_size_kb(image_bytes: bytes) -> float:
    """Returns size of image bytes in KB."""
    return round(len(image_bytes) / 1024.0, 2)
