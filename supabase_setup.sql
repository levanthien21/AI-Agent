-- Chạy toàn bộ mã SQL này trong phần SQL Editor của Supabase

-- 1. Kích hoạt extension pgvector để lưu trữ và tính toán embedding
create extension if not exists vector;

-- 2. Tạo bảng lưu thông tin các lĩnh vực (domains)
create table domains (
  name text primary key,
  config jsonb not null default '{}'::jsonb
);

-- 3. Tạo bảng lưu trữ kiến thức (chunks)
create table chunks (
  id uuid primary key default gen_random_uuid(),
  domain_name text references domains(name) on delete cascade,
  source text not null,
  text text not null,
  embedding vector(768) -- Google Gemini nhúng vector 768 chiều
);

-- 4. Tạo Index để tăng tốc độ tìm kiếm Vector (tuỳ chọn nhưng khuyên dùng)
create index on chunks using hnsw (embedding vector_ip_ops);

-- 5. Hàm tìm kiếm kiến thức tương đồng (RAG - Cosine Similarity)
create or replace function match_chunks (
  query_embedding vector(768),
  match_domain text,
  match_count int,
  match_threshold float
) returns table (
  id uuid,
  text text,
  source text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    chunks.id,
    chunks.text,
    chunks.source,
    1 - (chunks.embedding <=> query_embedding) as similarity
  from chunks
  where chunks.domain_name = match_domain
    and 1 - (chunks.embedding <=> query_embedding) > match_threshold
  order by chunks.embedding <=> query_embedding
  limit match_count;
end;
$$;

-- 6. Hàm đếm thống kê cho màn hình quản trị
create or replace function get_domain_stats()
returns table(name text, display_name text, chunk_count bigint, source_count bigint)
language sql
as $$
  select 
    d.name, 
    (d.config->>'display_name')::text as display_name,
    count(c.id) as chunk_count,
    count(distinct c.source) as source_count
  from domains d
  left join chunks c on d.name = c.domain_name
  group by d.name;
$$;
