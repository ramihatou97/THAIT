# Vector Search Design - NeuroscribeAI

**Purpose**: Enable semantic similarity search across clinical documents using pgvector
**Model**: all-MiniLM-L6-v2 (384 dimensions, optimized for semantic similarity)

---

## Architecture Overview

### Components

1. **Embedding Generation**
   - Model: sentence-transformers/all-MiniLM-L6-v2
   - Dimensions: 384
   - Input: Clinical text (max 512 tokens)
   - Output: Float vector [384]

2. **Document Chunking**
   - Strategy: Sliding window with overlap
   - Chunk size: 500 characters (configurable)
   - Overlap: 50 characters (configurable)
   - Preserves context across chunks

3. **Vector Storage**
   - Table: document_chunks
   - Index: IVFFlat (vector_cosine_ops)
   - Lists: 100 (for ~10K documents)

4. **Similarity Search**
   - Algorithm: Cosine similarity
   - Index: IVFFlat for approximate nearest neighbor
   - Performance: <100ms for top-10 results

---

## Data Flow

### Indexing Pipeline

```
Document Upload
      ↓
Text Extraction
      ↓
Chunking (500 char chunks, 50 char overlap)
      ↓
Embedding Generation (sentence-transformers)
      ↓
Store in document_chunks table with vector column
      ↓
Index ready for search
```

### Search Pipeline

```
User Query ("find patients with glioblastoma")
      ↓
Generate query embedding (same model)
      ↓
Vector similarity search (pgvector)
      ↓
Rank by cosine similarity
      ↓
Return top-k chunks with source documents
```

---

## Implementation Details

### Chunking Strategy

**Sliding Window Algorithm**:
```python
chunk_size = 500  # characters
overlap = 50      # characters
stride = chunk_size - overlap  # 450

chunks = []
for i in range(0, len(text), stride):
    chunk = text[i:i + chunk_size]
    chunks.append({
        'text': chunk,
        'char_start': i,
        'char_end': i + len(chunk)
    })
```

**Why Overlap?**
- Preserves context across boundaries
- Ensures entities at chunk edges are captured
- 50 char overlap = ~8-10 words of context

**Smart Chunking** (Optional Enhancement):
- Split on sentence boundaries
- Keep clinical sections together
- Preserve POD markers

---

## Vector Search Methods

### 1. Semantic Document Search

**Use Case**: "Find documents about postoperative complications"

```sql
SELECT
    dc.document_id,
    dc.chunk_text,
    dc.section_name,
    1 - (dc.embedding <=> $query_embedding) as similarity_score
FROM document_chunks dc
WHERE dc.embedding <=> $query_embedding < 0.5  -- Similarity threshold
ORDER BY dc.embedding <=> $query_embedding
LIMIT 10
```

**Operator**: `<=>` = cosine distance (1 - cosine similarity)

---

### 2. Similar Document Finder

**Use Case**: "Find documents similar to this discharge summary"

```python
# Generate embeddings for all chunks of source document
source_embeddings = get_document_embeddings(source_document_id)

# Average embeddings to get document vector
doc_embedding = np.mean(source_embeddings, axis=0)

# Find similar documents
similar = vector_search(doc_embedding, exclude_document_id=source_document_id)
```

---

### 3. Similar Patient Finder (by Clinical Profile)

**Use Case**: "Find patients with similar clinical presentation"

```python
# Combine all patient document embeddings
patient_embeddings = get_patient_embeddings(patient_id)

# Create patient "signature" vector
patient_vector = weighted_average(patient_embeddings)

# Find patients with similar vectors
similar_patients = vector_search_patients(patient_vector)
```

---

### 4. Fact-Based Semantic Search

**Use Case**: "Find all mentions of 'motor weakness' (including synonyms)"

```python
# Query expansion via embeddings
query = "motor weakness"
query_embedding = generate_embedding(query)

# Finds: "decreased strength", "paresis", "hemiparesis", etc.
results = vector_search(query_embedding, filter_by='PHYSICAL_EXAM')
```

---

## Performance Optimization

### Index Tuning

**IVFFlat Parameters**:
```sql
-- Current setting (good for <10K documents):
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- For 10K-100K documents:
lists = sqrt(num_documents) ≈ 316

-- For 100K+ documents:
Consider HNSW index (more accurate, slower build)
```

### Query Optimization

**Threshold Selection**:
- Distance < 0.3: Very similar (same topic)
- Distance < 0.5: Related (same domain)
- Distance < 0.7: Somewhat related
- Distance > 0.7: Unrelated

**Probes Setting**:
```sql
SET ivfflat.probes = 10;  -- Default
-- Higher = more accurate, slower
-- Lower = faster, less accurate
```

---

## Embedding Model Details

**Model**: sentence-transformers/all-MiniLM-L6-v2

**Specifications**:
- Dimensions: 384
- Max sequence length: 256 tokens (~512 characters)
- Embedding time: ~10-20ms per chunk
- Model size: ~90MB
- Performance: Good balance of speed vs accuracy

**Alternatives** (Future):
- all-mpnet-base-v2 (768 dims, more accurate, slower)
- all-MiniLM-L12-v2 (384 dims, more accurate than L6)
- Clinical-specific: Bio_ClinicalBERT (768 dims)

---

## Use Cases & Examples

### Use Case 1: Research Cohort Building

**Query**: "Find all patients with frontal lobe tumors and motor deficits"

```python
query = "frontal lobe glioblastoma with motor weakness"
embedding = generate_embedding(query)
similar_chunks = vector_search(embedding, top_k=50)

# Group by patient
patients = group_chunks_by_patient(similar_chunks)
# Filter by similarity threshold
relevant_patients = [p for p in patients if p.avg_similarity > 0.7]
```

---

### Use Case 2: Evidence-Based Treatment

**Query**: "What happened to patients with similar presentation?"

```python
current_patient_profile = get_patient_embedding(patient_id)
similar_patients = find_similar_by_embedding(current_patient_profile, top_k=10)

# Extract outcomes
outcomes = []
for similar_p in similar_patients:
    outcomes.append({
        'patient': similar_p.id,
        'treatment': get_treatments(similar_p.id),
        'outcome': get_outcome_metrics(similar_p.id),
        'similarity': similar_p.similarity_score
    })
```

---

### Use Case 3: Documentation Quality

**Query**: "Find incomplete discharge summaries"

```python
complete_summary_embedding = generate_embedding(
    "discharge summary with diagnosis, procedure, medications, "
    "neurological exam, laboratory results, and discharge plan"
)

all_summaries = get_all_discharge_summaries()
for summary in all_summaries:
    summary_embedding = generate_embedding(summary.text)
    similarity = cosine_similarity(summary_embedding, complete_summary_embedding)

    if similarity < 0.6:  # Significantly different from complete template
        flag_as_potentially_incomplete(summary)
```

---

## Integration Points

### 1. Automatic Indexing

**Trigger**: When document is uploaded and extracted

```python
@app.post("/api/v1/extract/file")
async def extract_from_file(...):
    # Existing extraction
    facts = extract_clinical_facts(text, patient_id, document_id)

    # NEW: Trigger async chunking and embedding
    from app.tasks.embeddings import generate_document_embeddings
    generate_document_embeddings.delay(document_id, text)

    return facts
```

### 2. Search-Enhanced Extraction

**Enhancement**: Use vector search to find similar past cases

```python
def extract_with_context(text: str, patient_id: int):
    # Find similar past documents
    similar_docs = vector_search(generate_embedding(text), top_k=5)

    # Extract facts from similar docs for context
    context_facts = get_facts_from_documents(similar_docs)

    # Use context to improve current extraction
    # (e.g., if similar patients all had seizure prophylaxis, flag if missing)
```

### 3. Validation Enhancement

**Enhancement**: Check completeness via semantic similarity

```python
def validate_completeness(document_text: str):
    doc_embedding = generate_embedding(document_text)

    # Compare to "ideal" discharge summary template
    template_embedding = get_template_embedding("discharge_summary")

    similarity = cosine_similarity(doc_embedding, template_embedding)
    completeness_score = similarity * 100

    if completeness_score < 70:
        missing_sections = detect_missing_sections(document_text)
        return ValidationIssue(
            severity="WARNING",
            message=f"Document may be incomplete (score: {completeness_score})",
            recommendation=f"Consider adding: {missing_sections}"
        )
```

---

## Performance Benchmarks

### Target Metrics

- **Embedding Generation**: <30ms per chunk
- **Vector Search**: <100ms for top-10 results
- **Full Document Indexing**: <2 seconds for 10-page document
- **Batch Indexing**: 100+ documents/minute

### Resource Requirements

- **Memory**: ~200MB for model
- **Disk**: ~2KB per chunk (text + vector)
- **CPU**: Moderate during embedding generation

---

## Security & Privacy

### PHI Considerations

**Embeddings**: Are NOT human-readable
- Cannot reverse engineer to get original text
- Safe to use for similarity without exposing PHI
- Can be shared for research (with IRB approval)

**Storage**: Embeddings stored in same database as text
- Same security controls apply
- HIPAA compliance maintained

---

## Monitoring & Metrics

### Metrics to Track

```python
# Prometheus metrics
embedding_generation_duration_seconds
vector_search_duration_seconds
embedding_cache_hit_rate
vector_search_result_count

# Quality metrics
average_similarity_score_histogram
embedding_generation_errors_total
vector_index_size_bytes
```

---

## Future Enhancements

1. **Hybrid Search**: Combine vector search + keyword search
2. **Re-ranking**: Use cross-encoder for more accurate top results
3. **Query Expansion**: Automatically expand queries with synonyms
4. **Clustering**: Group similar documents automatically
5. **Anomaly Detection**: Flag unusual clinical presentations

---

## Implementation Checklist

- [ ] VectorSearchService class
- [ ] Embedding generation (sentence-transformers)
- [ ] Document chunking logic
- [ ] Store chunks with embeddings
- [ ] Similarity search queries
- [ ] API endpoints for search
- [ ] Integration with extraction
- [ ] Performance testing
- [ ] Documentation

This design provides a robust foundation for semantic search
across clinical documents with sub-second query times.
