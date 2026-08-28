-- ============================================================
-- BUKANG Database Setup Script for Supabase Postgres
-- Execute this SQL script in Supabase SQL Editor
-- ============================================================

-- 1. Enable Fuzzy Trigram Search Extension
create extension if not exists pg_trgm;

-- 2. Create Table: mahasiswa
create table if not exists mahasiswa (
    id bigint generated always as identity primary key,
    nama text not null,
    nrp text unique not null,
    prodi_asal text,
    sudah_difoto boolean default false,
    photo_path text,
    asal text,
    hobi text,
    first_impression text,
    latitude double precision,
    longitude double precision,
    lokasi_gps text,
    waktu_foto timestamptz
);

-- Migration for existing table
alter table mahasiswa add column if not exists latitude double precision;
alter table mahasiswa add column if not exists longitude double precision;
alter table mahasiswa add column if not exists lokasi_gps text;
alter table mahasiswa add column if not exists hobi text;



-- 3. Create Indexes for Fast Lookup & Fuzzy Search
create index if not exists idx_nama_trgm on mahasiswa using gin (nama gin_trgm_ops);
create index if not exists idx_nrp on mahasiswa (nrp);
create index if not exists idx_sudah_difoto on mahasiswa (sudah_difoto);

-- 4. RPC Function: search_mahasiswa
-- Supports fuzzy name search via pg_trgm + fallback ILIKE for exact/partial NRP & Nama match
create or replace function search_mahasiswa(keyword text, limit_n int default 8)
returns setof mahasiswa as $$
begin
    return query
    select *
    from mahasiswa
    where 
        nama % keyword 
        or nama ilike '%' || keyword || '%' 
        or nrp ilike '%' || keyword || '%'
        or prodi_asal ilike '%' || keyword || '%'
    order by 
        similarity(nama, keyword) desc,
        nama asc
    limit limit_n;
end;
$$ language plpgsql;

-- 5. Storage Bucket Setup Instructions:
-- In Supabase Dashboard -> Storage -> Create a new bucket named: 'foto-angkatan'
-- Set privacy as desired (Private with signed URLs or Public for direct viewing).
