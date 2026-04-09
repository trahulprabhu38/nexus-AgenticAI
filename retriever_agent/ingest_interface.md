# Ingest interface (for reference)

This describes the metadata and chunking contract expected by the retriever.

- Chunk policy: ~400 words per chunk, 50 words overlap.
- Metadata per chunk (meta.pkl entries):
  - doc_id: unique string (e.g., syllabus_cs_s7)
  - chunk_id: integer
  - semester: canonical token (S1..S8)
  - subject: canonical name
  - source: filename or URL
  - created_at: ISO8601
  - text_preview: first 200 chars (optional)

When ingestion team produces faiss.index + meta.pkl they must maintain the alignment: vector i → meta_list[i].
