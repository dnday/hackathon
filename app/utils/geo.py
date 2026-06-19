import math

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Hitung jarak dalam meter antara dua koordinat."""
    R = 6371000  # Radius bumi dalam meter
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def extract_decimal_from_dms(dms, ref) -> float:
    """Konversi format Derajat, Menit, Detik (GPS EXIF) ke Decimal."""
    degrees, minutes, seconds = dms
    decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
    if ref in ['S', 'W']:
        decimal = -decimal
    return decimal

def extract_lat_lon(gps_info: dict) -> tuple[float, float] | None:
    """Ekstrak Latitude dan Longitude dari dictionary metadata GPS EXIF."""
    if not gps_info:
        return None
    try:
        lat = extract_decimal_from_dms(gps_info['GPSLatitude'], gps_info['GPSLatitudeRef'])
        lon = extract_decimal_from_dms(gps_info['GPSLongitude'], gps_info['GPSLongitudeRef'])
        return lat, lon
    except Exception:
        return None
