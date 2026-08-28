#!/usr/bin/env python3
import os
import time
import io
from PIL import Image
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def run_benchmark(num_samples: int = 5, target_size_kb: int = 400):
    """
    Runs upload speed & latency benchmark against Supabase Storage.
    Generates dummy image bytes of approximately target_size_kb KB and uploads num_samples times.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    bucket = os.getenv("SUPABASE_BUCKET", "foto-angkatan")

    if not url or not key:
        return {
            "error": "SUPABASE_URL dan SUPABASE_KEY tidak ditemukan di environment/secrets."
        }

    print("==================================================")
    print(" BUKANG - Supabase Storage Upload Latency Benchmark")
    print("==================================================")
    print(f"Target Bucket : {bucket}")
    print(f"Sample Count  : {num_samples} uploads")
    print(f"File Size     : ~{target_size_kb} KB per foto")
    print("--------------------------------------------------")

    # Generate sample image bytes (~400KB JPEG)
    img = Image.new("RGB", (1080, 1080), color=(73, 109, 137))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    img_bytes = buf.getvalue()
    actual_size_kb = len(img_bytes) / 1024.0

    print(f"Ukuran file uji: {actual_size_kb:.2f} KB")

    supabase = create_client(url, key)

    latencies = []
    successes = 0

    for i in range(num_samples):
        file_path = f"benchmark_test_{i+1}.jpg"
        start_time = time.time()
        try:
            supabase.storage.from_(bucket).upload(
                file_path,
                img_bytes,
                file_options={"content-type": "image/jpeg", "upsert": "true"}
            )
            elapsed = time.time() - start_time
            latencies.append(elapsed)
            successes += 1
            print(f"Upload #{i+1}: {elapsed:.3f} detik ({actual_size_kb / elapsed:.1f} KB/s)")
            
            # Clean up test file
            try:
                supabase.storage.from_(bucket).remove([file_path])
            except Exception:
                pass
        except Exception as e:
            print(f"Upload #{i+1} Gagal: {e}")

    if not latencies:
        return {"error": "Semua pengujian upload gagal."}

    avg_latency = sum(latencies) / len(latencies)
    min_latency = min(latencies)
    max_latency = max(latencies)
    speed_mbps = ((actual_size_kb * 8) / 1024.0) / avg_latency
    est_total_250_sec = (avg_latency * 250) / 60.0

    results = {
        "actual_size_kb": round(actual_size_kb, 2),
        "success_rate": f"{successes}/{num_samples}",
        "avg_latency_sec": round(avg_latency, 3),
        "min_latency_sec": round(min_latency, 3),
        "max_latency_sec": round(max_latency, 3),
        "est_upload_mbps": round(speed_mbps, 2),
        "est_total_250_min": round(est_total_250_sec, 2)
    }

    print("--------------------------------------------------")
    print(f"Rata-rata Waktu Upload : {avg_latency:.3f} detik")
    print(f"Waktu Tercepat         : {min_latency:.3f} detik")
    print(f"Waktu Terlama          : {max_latency:.3f} detik")
    print(f"Estimasi Kecepatan     : {speed_mbps:.2f} Mbps")
    print(f"Estimasi Total 250 Foto: {est_total_250_sec:.2f} menit")
    print("==================================================")

    return results

if __name__ == "__main__":
    run_benchmark(num_samples=5, target_size_kb=400)
