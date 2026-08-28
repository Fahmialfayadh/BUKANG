import os
import pandas as pd
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Cache local NRP to Kelas lookup mapping from database/mahasiswa_tc25_all.csv
@st.cache_data
def load_kelas_map():
    """Loads local NRP -> Kelas mapping fallback dict from CSV."""
    csv_path = "database/mahasiswa_tc25_all.csv"
    if not os.path.exists(csv_path):
        csv_path = "sample_mahasiswa.csv"
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            if "nrp" in df.columns and "kelas" in df.columns:
                return dict(zip(df["nrp"].astype(str), df["kelas"].astype(str)))
        except Exception:
            pass
    return {}

@st.cache_resource
def get_supabase_client() -> Client:
    """
    Retrieve initialized Supabase client.
    Checks st.secrets first (for Streamlit Cloud), then environment variables.
    """
    url = None
    key = None

    try:
        if "SUPABASE_URL" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_SERVICE_KEY")
    except Exception:
        pass

    if not url:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        st.warning("Kredensial Supabase belum dikonfigurasi. Harap atur SUPABASE_URL dan SUPABASE_KEY di st.secrets atau .env.")
        return None

    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"Gagal menghubungkan ke Supabase: {str(e)}")
        return None

def get_bucket_name() -> str:
    try:
        if "SUPABASE_BUCKET" in st.secrets:
            return st.secrets["SUPABASE_BUCKET"]
    except Exception:
        pass
    return os.getenv("SUPABASE_BUCKET", "foto-angkatan")

def enrich_student_kelas(student_dict: dict) -> dict:
    """Ensures student record dictionary contains valid kelas field."""
    if not student_dict:
        return student_dict
    
    if not student_dict.get("kelas") or str(student_dict.get("kelas")).lower() == "none":
        kelas_map = load_kelas_map()
        nrp_str = str(student_dict.get("nrp", ""))
        if nrp_str in kelas_map:
            student_dict["kelas"] = kelas_map[nrp_str]
        elif student_dict.get("prodi_asal") in ["RKA", "RPL"]:
            student_dict["kelas"] = student_dict["prodi_asal"]
        else:
            student_dict["kelas"] = "Lainnya"
    return student_dict

def cari_mahasiswa(keyword: str, limit: int = 10):
    """
    Fuzzy search student by name/NRP/kelas using pg_trgm RPC function,
    with fallback to ILIKE query if RPC is unavailable.
    """
    client = get_supabase_client()
    if not client or not keyword.strip():
        return []

    results = []
    try:
        res = client.rpc("search_mahasiswa", {"keyword": keyword.strip(), "limit_n": limit}).execute()
        if res.data:
            results = res.data
    except Exception:
        pass

    if not results:
        try:
            res = client.table("mahasiswa") \
                .select("*") \
                .or_(f"nama.ilike.%{keyword}%,nrp.ilike.%{keyword}%") \
                .limit(limit) \
                .execute()
            results = res.data or []
        except Exception as e:
            st.error(f"Error pencarian: {str(e)}")
            return []

    return [enrich_student_kelas(r) for r in results]

def get_mahasiswa_by_nrp(nrp: str):
    """Retrieve single student record by exact NRP."""
    client = get_supabase_client()
    if not client:
        return None
    try:
        res = client.table("mahasiswa").select("*").eq("nrp", nrp).execute()
        if res.data and len(res.data) > 0:
            return enrich_student_kelas(res.data[0])
        return None
    except Exception:
        return None

def simpan_foto_dan_data(
    nrp: str, 
    foto_bytes: bytes, 
    asal: str, 
    hobi: str,
    first_impression: str,
    lat: float = None,
    lon: float = None
) -> bool:
    """
    Upload compressed photo to Supabase Storage and update student record in DB with Geotag & Hobi.
    """
    client = get_supabase_client()
    if not client:
        raise Exception("Client Supabase tidak terhubung")

    bucket_name = get_bucket_name()
    file_path = f"{nrp}.jpg"

    # 1. Upload photo bytes to Storage
    try:
        client.storage.from_(bucket_name).upload(
            file_path,
            foto_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"}
        )
    except Exception as upload_err:
        raise Exception(f"Gagal mengunggah foto ke storage ({bucket_name}): {str(upload_err)}")

    # 2. Update record in table mahasiswa
    try:
        update_payload = {
            "sudah_difoto": True,
            "photo_path": file_path,
            "asal": asal.strip() if asal else "",
            "hobi": hobi.strip() if hobi else "",
            "first_impression": first_impression.strip() if first_impression else "",
            "waktu_foto": "now()"
        }
        if lat is not None and lon is not None:
            update_payload["latitude"] = lat
            update_payload["longitude"] = lon
            update_payload["lokasi_gps"] = f"{lat:.6f}, {lon:.6f}"

        client.table("mahasiswa").update(update_payload).eq("nrp", nrp).execute()
        return True
    except Exception as db_err:
        raise Exception(f"Gagal memperbarui data mahasiswa di database: {str(db_err)}")

def tambah_mahasiswa_manual(nama: str, nrp: str, prodi_asal: str, kelas: str = "Manual"):
    """Insert a new student manually if not present in CSV."""
    client = get_supabase_client()
    if not client:
        raise Exception("Client Supabase tidak terhubung")

    try:
        payload = {
            "nama": nama.strip(),
            "nrp": nrp.strip(),
            "prodi_asal": prodi_asal.strip(),
            "kelas": kelas.strip(),
            "sudah_difoto": False
        }
        res = client.table("mahasiswa").insert(payload).execute()
        return res.data
    except Exception as e:
        raise Exception(f"Gagal menambah mahasiswa manual: {str(e)}")

def get_stats():
    """Retrieve count of photographed students and total count."""
    client = get_supabase_client()
    if not client:
        return 0, 0
    try:
        res_total = client.table("mahasiswa").select("id", count="exact").execute()
        res_done = client.table("mahasiswa").select("id", count="exact").eq("sudah_difoto", True).execute()
        
        total = res_total.count if res_total.count is not None else 0
        done = res_done.count if res_done.count is not None else 0
        return done, total
    except Exception:
        return 0, 0

def get_mahasiswa_belum_difoto():
    """Retrieve list of students who haven't been photographed yet with kelas enriched."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        res = client.table("mahasiswa").select("*").eq("sudah_difoto", False).order("nama").execute()
        raw_list = res.data or []
        return [enrich_student_kelas(r) for r in raw_list]
    except Exception:
        return []

def get_all_mahasiswa():
    """Retrieve all student records for export with kelas enriched."""
    client = get_supabase_client()
    if not client:
        return []
    try:
        res = client.table("mahasiswa").select("*").order("nama").execute()
        raw_list = res.data or []
        return [enrich_student_kelas(r) for r in raw_list]
    except Exception:
        return []
