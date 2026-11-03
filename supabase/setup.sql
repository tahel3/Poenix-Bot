-- מריצים פעם אחת ב-Supabase: SQL Editor -> New query -> הדביקי -> Run.

-- 1. מפעילים את התוסף של חיפוש וקטורי
create extension if not exists vector;

-- 2. טבלת הקטעים. 768 חייב להיות זהה ל-DIMS ב-ingest/build_index.py ול-DIMS ב-web/lib/rag.ts
create table if not exists chunks (
  id          bigserial primary key,
  url         text not null,
  title       text,
  section     text,
  content     text not null,
  scraped_at  date,
  embedding   vector(768) not null,
  -- עמודה לחיפוש מילות מפתח. 'simple' כי ל-Postgres אין הגדרה מובנית לעברית
  fts         tsvector generated always as (to_tsvector('simple', content)) stored
);

-- 3. אינדקסים: אחד לחיפוש וקטורי (קוסינוס), אחד למילות מפתח
create index if not exists chunks_embedding_idx on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_fts_idx on chunks using gin (fts);

-- 4. אבטחה: הטבלה סגורה לגישה ציבורית. רק המפתח הסודי (בשרת) יכול לקרוא ולכתוב
alter table chunks enable row level security;

-- 5. פונקציית החיפוש ההיברידי:
--    מקבלת וקטור של השאלה + מילות מפתח (בפורמט tsquery, מחוברות ב-|),
--    מאחדת את שני הדירוגים בשיטת RRF, ומחזירה את הקטעים הטובים ביותר.
--    similarity הוא דמיון קוסינוס אמיתי של הקטע לשאלה (1 = זהה), ועליו מבוסס הסף ב-rag.ts.
create or replace function match_chunks(
  query_embedding vector(768),
  query_text text,
  match_count int default 8
)
returns table (
  id bigint,
  url text,
  title text,
  section text,
  content text,
  similarity float,
  keyword_hit boolean
)
language sql stable
as $$
  with vec as (
    select c.id, row_number() over (order by c.embedding <=> query_embedding) as rnk
    from chunks c
    order by c.embedding <=> query_embedding
    limit match_count * 3
  ),
  kw as (
    select c.id, row_number() over (order by ts_rank(c.fts, q.tsq) desc) as rnk
    from chunks c, (select to_tsquery('simple', query_text) as tsq) q
    where c.fts @@ q.tsq
    order by ts_rank(c.fts, q.tsq) desc
    limit match_count * 3
  ),
  fused as (
    select coalesce(vec.id, kw.id) as id,
           coalesce(1.0 / (60 + vec.rnk), 0) + coalesce(1.0 / (60 + kw.rnk), 0) as score,
           (kw.id is not null) as keyword_hit
    from vec full outer join kw on vec.id = kw.id
  )
  select c.id, c.url, c.title, c.section, c.content,
         (1 - (c.embedding <=> query_embedding))::float as similarity,
         f.keyword_hit
  from fused f
  join chunks c on c.id = f.id
  order by f.score desc
  limit match_count;
$$;
