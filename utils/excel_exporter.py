import io
import pandas as pd
from utils.supabase_client import get_supabase_client, get_bucket_name

def export_mahasiswa_to_excel(records: list) -> bytes:
    """
    Generates Excel file (.xlsx) in bytes from student records data list,
    including formatted columns, Supabase Storage photo URLs, and Geotag links.
    """
    if not records:
        df = pd.DataFrame(columns=[
            "NRP", "Nama", "Prodi Asal", "Status Foto", "Asal", "Hobi", "First Impression", 
            "Lokasi GPS", "Google Maps Link", "Waktu Foto", "URL Foto"
        ])
    else:
        client = get_supabase_client()
        bucket_name = get_bucket_name()

        rows = []
        for r in records:
            photo_url = ""
            if r.get("photo_path"):
                if client:
                    try:
                        photo_url = client.storage.from_(bucket_name).get_public_url(r["photo_path"])
                    except Exception:
                        photo_url = r.get("photo_path", "")
                else:
                    photo_url = r.get("photo_path", "")

            gmaps_link = ""
            if r.get("latitude") is not None and r.get("longitude") is not None:
                gmaps_link = f"https://www.google.com/maps?q={r['latitude']},{r['longitude']}"

            rows.append({
                "NRP": r.get("nrp", ""),
                "Nama": r.get("nama", ""),
                "Prodi Asal": r.get("prodi_asal", ""),
                "Status Foto": "Sudah" if r.get("sudah_difoto") else "Belum",
                "Asal": r.get("asal", ""),
                "Hobi": r.get("hobi", ""),
                "First Impression": r.get("first_impression", ""),
                "Lokasi GPS": r.get("lokasi_gps", ""),
                "Google Maps Link": gmaps_link,
                "Waktu Foto": r.get("waktu_foto", ""),
                "URL Foto": photo_url
            })
        df = pd.DataFrame(rows)


    # Write to Excel BytesIO buffer using openpyxl engine
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data Angkatan")
    
    return output.getvalue()
