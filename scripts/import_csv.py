#!/usr/bin/env python3
import os
import sys
import glob
import argparse
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def parse_single_csv(filepath: str, default_prodi: str = "Teknik Informatika") -> list:
    """Parses a single CSV file, handling header offsets, kelas extraction, and cleaning NRP/Nama fields."""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' tidak ditemukan.")
        return []

    filename = os.path.basename(filepath)
    
    # Determine prodi and kelas group from filename
    if "RKA" in filename:
        prodi = "RKA"
        kelas = "RKA"
    elif "RPL" in filename:
        prodi = "RPL"
        kelas = "RPL"
    elif "IUP" in filename:
        prodi = default_prodi
        kelas = "IUP"
    else:
        prodi = default_prodi
        # Extract class letter (A, B, C, D, E) from filename
        kelas = "A"
        for k in ["A", "B", "C", "D", "E"]:
            if f"- {k}.csv" in filename or f"-{k}.csv" in filename or f" {k}.csv" in filename:
                kelas = k
                break

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    header_idx = -1
    for idx, line in enumerate(lines):
        if "NRP" in line and "Nama" in line:
            header_idx = idx
            break

    if header_idx != -1:
        df = pd.read_csv(filepath, skiprows=header_idx)
    else:
        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            print(f"Error membaca {filepath}: {e}")
            return []

    df.columns = [str(c).strip() for c in df.columns]

    if "NRP" not in df.columns or "Nama" not in df.columns:
        print(f"Peringatan: File {filename} tidak memiliki kolom 'NRP' dan 'Nama'")
        return []

    df = df.dropna(subset=["NRP", "Nama"])
    
    records = []
    for _, row in df.iterrows():
        nrp_raw = str(row["NRP"]).strip()
        if nrp_raw.endswith(".0"):
            nrp_raw = nrp_raw[:-2]
        nrp = "".join([c for c in nrp_raw if c.isdigit()])
        nama = str(row["Nama"]).strip()

        col_prodi = row.get("prodi_asal") or row.get("Prodi") or prodi
        col_kelas = row.get("kelas") or row.get("Kelas") or kelas

        if len(nrp) >= 8 and len(nama) > 1:
            records.append({
                "nama": nama,
                "nrp": nrp,
                "prodi_asal": str(col_prodi).strip(),
                "kelas": str(col_kelas).strip(),
                "sudah_difoto": False
            })
    return records

def import_all(target_path: str):
    """Imports CSV files into Supabase database with kelas breakdown."""
    records = []
    
    if os.path.isdir(target_path):
        csv_files = glob.glob(os.path.join(target_path, "*.csv"))
        print(f"Menemukan {len(csv_files)} file CSV di folder '{target_path}'")
        for f in sorted(csv_files):
            if "mahasiswa_tc25_all.csv" in f or "sample_mahasiswa.csv" in f:
                continue
            rec = parse_single_csv(f)
            records.extend(rec)
            print(f"-> {os.path.basename(f)}: {len(rec)} mahasiswa loaded")
    else:
        records = parse_single_csv(target_path)

    if not records:
        print("Tidak ada data mahasiswa valid yang berhasil diproses.")
        sys.exit(1)

    print(f"\nTotal data mahasiswa yang siap di-import: {len(records)}")
    
    # Save combined clean CSV copy with kelas column
    combined_df = pd.DataFrame(records)[["nama", "nrp", "prodi_asal", "kelas"]]
    combined_path = "database/mahasiswa_tc25_all.csv"
    combined_df.to_csv(combined_path, index=False)
    combined_df.to_csv("sample_mahasiswa.csv", index=False)
    print(f"File gabungan berhasil disimpan ke '{combined_path}' & 'sample_mahasiswa.csv'")

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("\nPeringatan: SUPABASE_URL dan SUPABASE_KEY belum diatur.")
        return

    supabase = create_client(url, key)
    print(f"\nMengunggah {len(records)} data mahasiswa ke Supabase...")
    
    batch_size = 50
    success_count = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            res = supabase.table("mahasiswa").upsert(batch, on_conflict="nrp").execute()
            if res.data:
                success_count += len(res.data)
            print(f"Progress: {min(i + batch_size, len(records))}/{len(records)} tersimpan.")
        except Exception as e:
            print(f"Error saat upsert batch {i}: {e}")

    print(f"Selesai. Total {success_count} record berhasil tersimpan ke Supabase.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import data mahasiswa CSV ke Supabase.")
    parser.add_argument("--path", "-p", default="database", help="Path file CSV atau folder database (default: database)")
    args = parser.parse_args()
    import_all(args.path)
