import streamlit as st
import pandas as pd
from streamlit_js_eval import get_geolocation
from utils.supabase_client import (
    get_supabase_client,
    cari_mahasiswa,
    get_mahasiswa_by_nrp,
    simpan_foto_dan_data,
    tambah_mahasiswa_manual,
    get_stats,
    get_mahasiswa_belum_difoto,
    get_all_mahasiswa
)
from utils.image_processor import compress_and_stamp_image, get_image_size_kb, extract_exif_gps
from utils.excel_exporter import export_mahasiswa_to_excel

# Page Configuration
st.set_page_config(
    page_title="BUKANG - Pendataan Foto Angkatan",
    page_icon="📷",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS styling following rule #4 (No emotes, clean modern UI)
st.markdown("""
    <style>
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
    }
    .card-box {
        background-color: #1e293b;
        padding: 1.25rem;
        border-radius: 0.5rem;
        border: 1px solid #334155;
        margin-bottom: 1rem;
    }
    .retake-warning {
        background-color: #451a03;
        color: #fde68a;
        padding: 0.75rem;
        border-radius: 0.375rem;
        border: 1px solid #78350f;
        margin-bottom: 1rem;
        font-size: 0.9rem;
    }
    .stButton > button {
        width: 100%;
        font-weight: 600;
        border-radius: 0.375rem;
        padding: 0.6rem 1rem;
    }
    /* Mirror live camera video stream AND captured still preview image */
    [data-testid="stCameraInput"] video,
    [data-testid="stCameraInput"] img,
    [data-testid="stCameraInput"] canvas {
        transform: scaleX(-1) !important;
        -webkit-transform: scaleX(-1) !important;
    }
    </style>


""", unsafe_allow_html=True)

# Application Header
st.markdown('<div class="main-header">BUKANG - Pendataan Foto Angkatan</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Sistem Pengambilan Foto & Geotag Mahasiswa Real-Time</div>', unsafe_allow_html=True)

# Check Supabase connection state
client = get_supabase_client()
if not client:
    st.info("Aplikasi berjalan dalam mode konfigurasi. Masukkan SUPABASE_URL dan SUPABASE_KEY pada file .env atau Secrets Streamlit Cloud untuk menghubungkan database.")

# Navigation Tabs
tab_input, tab_progress, tab_tools = st.tabs([
    "Motret & Input Data",
    "Tracking Progress",
    "Tools & Export"
])

# -----------------------------------------------------------------------------
# TAB 1: MOTRET & INPUT DATA
# -----------------------------------------------------------------------------
with tab_input:
    st.subheader("1. Ambil Foto")
    
    col_cam, col_file = st.tabs(["Kamera HP", "Unggah Galeri"])
    
    foto_input = None
    with col_cam:
        cam_photo = st.camera_input("Jepret Foto Mahasiswa", key="camera_source")
        if cam_photo:
            foto_input = cam_photo
            
    with col_file:
        file_photo = st.file_uploader("Pilih foto dari perangkat", type=["jpg", "jpeg", "png"], key="file_source")
        if file_photo:
            foto_input = file_photo

    # Extract EXIF Geotag if photo from file
    exif_lat, exif_lon = (None, None)
    if foto_input:
        exif_lat, exif_lon = extract_exif_gps(foto_input)

    st.markdown("---")
    st.subheader("2. Identitas & Pencarian Mahasiswa")

    search_query = st.text_input("Ketik Nama atau NRP", placeholder="Contoh: Budi / 5025211001")

    selected_student = None
    manual_mode = st.checkbox("Mahasiswa tidak ditemukan di pencarian (Tambah Manual)")

    if manual_mode:
        st.markdown('<div class="card-box">', unsafe_allow_html=True)
        st.write("Form Tambah Mahasiswa Baru:")
        manual_nama = st.text_input("Nama Lengkap Mahasiswa")
        manual_nrp = st.text_input("NRP Mahasiswa")
        manual_prodi = st.text_input("Prodi Asal")
        
        if manual_nama and manual_nrp:
            selected_student = {
                "nama": manual_nama.strip(),
                "nrp": manual_nrp.strip(),
                "prodi_asal": manual_prodi.strip(),
                "is_manual": True
            }
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        if search_query.strip():
            results = cari_mahasiswa(search_query)
            if results:
                options = {
                    f"{item['nama']} | NRP: {item['nrp']} ({item.get('prodi_asal', '-')})": item
                    for item in results
                }
                selected_label = st.selectbox("Pilih Mahasiswa dari Hasil Pencarian", list(options.keys()))
                if selected_label:
                    selected_student = options[selected_label]
            else:
                st.warning("Tidak ditemukan mahasiswa dengan kata kunci tersebut. Aktifkan centang 'Tambah Manual' di atas jika belum terdaftar.")

    # Show selected student status summary
    if selected_student:
        st.info(f"Terpilih: **{selected_student['nama']}** (NRP: {selected_student['nrp']}) - {selected_student.get('prodi_asal', '-')}")
        
        # Check if already photographed (Retake Warning)
        if not selected_student.get("is_manual", False):
            db_record = get_mahasiswa_by_nrp(selected_student["nrp"])
            if db_record and db_record.get("sudah_difoto"):
                waktu_foto = db_record.get("waktu_foto", "Sebelumnya")
                st.markdown(
                    f'<div class="retake-warning">Peringatan: Mahasiswa ini sudah pernah difoto (Waktu: {waktu_foto}). '
                    'Menekan Simpan akan memperbarui foto dan data lama (Retake).</div>',
                    unsafe_allow_html=True
                )

    # Get real-time browser Geolocation asynchronously without page reload
    geo_data = get_geolocation()

    auto_lat = None
    auto_lon = None

    if geo_data and "coords" in geo_data:
        auto_lat = round(geo_data["coords"]["latitude"], 6)
        auto_lon = round(geo_data["coords"]["longitude"], 6)
    elif exif_lat is not None and exif_lon is not None:
        auto_lat = exif_lat
        auto_lon = exif_lon

    st.markdown("---")
    st.subheader("3. Informasi Tambahan & Geotag")

    asal_input = st.text_input("Kota / Daerah Asal", placeholder="Contoh: Surabaya / Jakarta")
    hobi_input = st.text_input("Hobi", placeholder="Contoh: Basket, Coding, Gaming")
    impression_input = st.text_area("First Impression / Catatan Singkat", placeholder="Contoh: Ramah, supel")

    # Dynamic Geotag Status Display
    if auto_lat is not None and auto_lon is not None:
        final_lat = auto_lat
        final_lon = auto_lon
        st.success(f"GPS HP Terhubung: {final_lat:.6f}, {final_lon:.6f} ([Lihat di Google Maps](https://www.google.com/maps?q={final_lat},{final_lon}))")
    else:
        final_lat = None
        final_lon = None
        st.info("Menghubungkan ke GPS HP... Pastikan izin Lokasi (Location) diizinkan di browser HP Anda.")

    st.markdown("---")

    if st.button("Simpan Foto & Data", type="primary"):
        if not foto_input:
            st.error("Gagal: Foto belum diambil atau diunggah.")
        elif not selected_student:
            st.error("Gagal: Mahasiswa belum dipilih dari hasil pencarian.")
        else:
            try:
                with st.spinner("Mengompresi foto, memasang Geotag watermark & mengunggah ke Supabase..."):
                    # 1. Compress Image & Stamp Geotag Watermark onto Photo (Mirrored for Camera)
                    is_from_camera = (foto_input == cam_photo) if 'cam_photo' in locals() else True
                    compressed_bytes = compress_and_stamp_image(
                        foto_input,
                        max_size=1080,
                        quality=80,
                        lat=final_lat,
                        lon=final_lon,
                        nrp=selected_student["nrp"],
                        nama=selected_student["nama"],
                        mirror_photo=is_from_camera
                    )
                    size_kb = get_image_size_kb(compressed_bytes)

                    # 2. Insert manual student if applicable
                    if selected_student.get("is_manual"):
                        tambah_mahasiswa_manual(
                            selected_student["nama"],
                            selected_student["nrp"],
                            selected_student.get("prodi_asal", "")
                        )

                    # 3. Save photo, metadata, hobi & geotag to Supabase
                    simpan_foto_dan_data(
                        selected_student["nrp"],
                        compressed_bytes,
                        asal_input,
                        hobi_input,
                        impression_input,
                        lat=final_lat,
                        lon=final_lon
                    )


                st.success(f"Berhasil! Foto ({size_kb} KB) dan data untuk {selected_student['nama']} ({selected_student['nrp']}) telah tersimpan.")
                st.balloons()
            except Exception as err:
                st.error(f"Terjadi kesalahan saat menyimpan: {str(err)}")
                st.info("Silakan periksa koneksi internet Anda dan tekan tombol 'Simpan Foto & Data' lagi untuk mencoba ulang (retry).")


# -----------------------------------------------------------------------------
# TAB 2: TRACKING PROGRESS
# -----------------------------------------------------------------------------
with tab_progress:
    st.subheader("Dashboard Progress Pendataan")
    
    done, total = get_stats()
    percentage = (done / total * 100) if total > 0 else 0.0

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Mahasiswa Difoto", f"{done} / {total}")
    with col2:
        st.metric("Persentase Selesai", f"{percentage:.1f}%")

    st.progress(percentage / 100.0)

    if total > 0 and percentage < 80.0:
        st.warning(f"Progress masih di bawah target (80%). Masih ada {total - done} mahasiswa yang belum difoto.")

    st.markdown("---")
    st.subheader("Daftar Mahasiswa Belum Difoto")

    belum_list = get_mahasiswa_belum_difoto()
    if not belum_list:
        st.success("Luar biasa! Semua mahasiswa terdaftar sudah selesai difoto.")
    else:
        filter_text = st.text_input("Filter daftar nama belum difoto", placeholder="Cari nama / prodi...")
        
        df_belum = pd.DataFrame(belum_list)
        if "nama" in df_belum.columns:
            display_cols = ["nama", "nrp", "prodi_asal"]
            existing_cols = [c for c in display_cols if c in df_belum.columns]
            df_filtered = df_belum[existing_cols].copy()
            df_filtered.columns = ["Nama", "NRP", "Prodi Asal"][:len(existing_cols)]

            if filter_text.strip():
                mask = df_filtered.apply(lambda row: row.astype(str).str.contains(filter_text, case=False).any(), axis=1)
                df_filtered = df_filtered[mask]

            st.write(f"Menampilkan {len(df_filtered)} dari {len(belum_list)} mahasiswa belum difoto:")
            st.dataframe(df_filtered, use_container_width=True, hide_index=True)


# -----------------------------------------------------------------------------
# TAB 3: TOOLS & EXPORT
# -----------------------------------------------------------------------------
with tab_tools:
    st.subheader("1. Ekspor Data ke Excel")
    st.write("Unduh seluruh data mahasiswa beserta status pendataan, informasi tambahan, Geotag lokasi, dan URL foto dari Supabase Storage.")

    if st.button("Generate File Excel"):
        with st.spinner("Mengambil data dari Supabase..."):
            all_records = get_all_mahasiswa()
            excel_bytes = export_mahasiswa_to_excel(all_records)
            
            st.download_button(
                label="Unduh File Data Angkatan (.xlsx)",
                data=excel_bytes,
                file_name="bukang_data_angkatan.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )

    st.markdown("---")
    st.subheader("2. Benchmark Kecepatan Upload Jaringan")
    st.write("Uji latensi dan kecepatan transfer ke Supabase Storage pada koneksi jaringan lokasi acara.")

    num_trials = st.slider("Jumlah Pengujian Upload", min_value=1, max_value=10, value=3)
    if st.button("Jalankan Uji Benchmark Network"):
        with st.spinner("Menjalankan pengujian upload ke Supabase Storage..."):
            from scripts.benchmark_upload import run_benchmark
            res = run_benchmark(num_samples=num_trials, target_size_kb=400)
            if "error" in res:
                st.error(res["error"])
            else:
                st.success("Pengujian selesai!")
                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    st.metric("Rata-rata Waktu Transfer", f"{res['avg_latency_sec']} detik")
                    st.metric("Estimasi Speed Jaringan", f"{res['est_upload_mbps']} Mbps")
                with bcol2:
                    st.metric("Hasil Upload Berhasil", res['success_rate'])
                    st.metric("Estimasi Waktu 250 Foto", f"{res['est_total_250_min']} menit")
