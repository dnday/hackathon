from io import BytesIO
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from typing import Any

def get_image_metadata(image_bytes: bytes) -> dict[str, Any]:
    metadata = {}
    try:
        img = Image.open(BytesIO(image_bytes))
        exif_data = img._getexif()
        if not exif_data:
            return {}

        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                gps_data = {}
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    gps_data[sub_tag] = value[t]
                metadata["gps"] = gps_data
            else:
                metadata[tag] = str(value)
    except Exception:
        return {}
    return metadata

def format_metadata_for_prompt(metadata_list: list[dict[str, Any]]) -> str:
    if not metadata_list:
        return "No technical metadata (EXIF) found in uploaded images."
    
    output = "Technical metadata found in images:\n"
    for i, meta in enumerate(metadata_list):
        output += f"Image {i+1}: "
        if not meta:
            output += "None\n"
            continue
        
        # Extract important fields only
        dt = meta.get("DateTimeOriginal") or meta.get("DateTime") or "Unknown Date"
        model = meta.get("Model") or "Unknown Device"
        output += f"Taken on: {dt}, Device: {model}"
        
        if "gps" in meta:
            output += ", GPS coordinates present."
        output += "\n"
    return output
