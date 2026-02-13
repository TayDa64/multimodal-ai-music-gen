# Phase 2 — Embeddings & Semantic Search

## Phase Overview

**Goal**: Build a local vector embedding index over all MPC Beats assets (progressions, arp patterns, synth presets, effects, controller maps). Enable natural-language semantic search: "warm Sunday morning feeling" → ranked list of matching progressions, presets, and arp patterns. All inference runs locally via ONNX Runtime; no cloud API calls for embeddings.

**Dependencies**: Phase 0 (parsers, asset manifest), Phase 1 (enriched progression analysis for descriptions)

**Exports consumed by**: Phase 4 (preset recommendation), Phase 6 (pipeline asset selection), Phase 8 (creative search), Phase 9 (preference centroid tracking)

---

## SDK Integration Points

| SDK Feature | Phase 2 Usage |
|---|---|
| `defineTool()` | `search_assets` — semantic search across all asset types |
| `hooks.onSessionStart` | Load embedding index into memory on session start |
| `skillDirectories` | `skills/sound/preset-catalog.json` — pre-authored descriptions available to LLM |
| MCP Server (optional) | Filesystem watcher MCP to detect new assets and re-index |

---

## Task Breakdown

### Task 2.1 — Description Catalog: Progressions

**Description**: Author rich natural-language descriptions for all 47 progression files. These descriptions are the input to the embedding model and must capture harmonic character, emotional quality, genre association, and production context.

**Input**: `EnrichedProgression` for each file (from Phase 1)

**Output**: `data/descriptions/progressions.json`
```typescript
interface ProgressionDescription {
  filePath: string;
  name: string;
  description: string;        // 50-100 words of rich musical description
  tags: string[];              // searchable keywords
}
```

**Implementation Hints**:
- This is partially manual curation, partially algorithmic:
  - Algorithmic: genre (from name), key, chord count, complexity score, tension arc description
  - Manual/LLM-assisted: emotional quality, production context, reference artists
- Template for generation:
  ```
  "{genre} progression in {key} {mode}. {chord_count} chords with {complexity} harmony.
   Features {notable_features}. Evokes {emotional_quality}. Suitable for {use_cases}.
   Similar artists/styles: {references}."
  ```
- Example (Godly):
  ```
  "Gospel minor key progression in E pentatonic minor. 16 chords with high harmonic complexity.
   Features chromatic descending bass, secondary dominants (D7/F#, A7/C#), creating yearning devotional pull.
   Evokes spiritual intensity, soulful worship, emotional crescendo.
   Suitable for gospel, neo-soul, worship music, dramatic ballads.
   Similar artists: Kirk Franklin, Tye Tribbett, Fred Hammond."
  ```
- Store as JSON array for easy loading and re-generation

**Testing**: Verify all 47 progressions have descriptions ≥ 40 words. Verify tags are non-empty. Spot-check 5 descriptions for musical accuracy.

**Complexity**: M

---

### Task 2.2 — Description Catalog: Arp Patterns

**Description**: Author descriptions for all 80 arp pattern MIDI files. Since these are instrumental patterns without explicit naming beyond category, descriptions are more algorithmically derived.

**Input**: `ParsedArpPattern` for each file (from Phase 0)

**Output**: `data/descriptions/arp-patterns.json` (same schema shape as 2.1)

**Implementation Hints**:
- Description template:
  ```
  "{category} arp pattern in {genre} style. {density} note density at {rhythmic_grid} resolution.
   Pitch range: {range} semitones. Velocity dynamics: {velocity_profile}.
   Character: {character_adjectives}. Suitable for {use_cases}."
  ```
- Character adjectives derived algorithmically:
  - High density (>4 notes/beat) → "busy", "energetic", "driving"
  - Low density (<2 notes/beat) → "sparse", "breathing", "atmospheric"
  - Wide pitch range (>12 semitones) → "expansive", "sweeping"
  - Narrow pitch range (<6) → "focused", "hypnotic", "repetitive"
  - High velocity variance → "dynamic", "expressive"
  - Low velocity variance → "mechanical", "steady", "consistent"
- Genre inference from sub-category: "Lead Hip Hop" → hip_hop, "SynBass" → electronic, "Soul Ballad" → soul
- Patterns like "Dance" map to multiple electronic sub-genres

**Testing**: Verify all 80 patterns have descriptions ≥ 30 words. Verify category (Chord/Melodic/Bass) matches the actual category parsed from filename.

**Complexity**: M

---

### Task 2.3 — Description Catalog: Synth Presets

**Description**: Author descriptions for all synth presets. This is the largest catalog (~297 TubeSynth + presets from Bassline, Electric, DrumSynth, and VSTs).

**Input**: `PresetCatalog` (from Phase 0), preset naming conventions

**Output**: `data/descriptions/presets.json`

**Implementation Hints**:
- Since `.xpl` files are binary, we CANNOT read parameter values. Descriptions are derived from:
  1. **Preset name**: "Warm Pad" → warm, sustained, atmospheric
  2. **Category**: Pad → sustained, background; Lead → monophonic, cutting; Bass → low-frequency, foundational
  3. **Engine**: TubeSynth → analog-modeled; Bassline → 303-style acid; Electric → Rhodes/Wurlitzer
  4. **Musical knowledge**: what "Analog Tube Richness" sounds like based on synth terminology
- TubeSynth category descriptions:
  - **Synth (44)**: Polyphonic, often saw/pulse-based, bright, aggressive to smooth
  - **Lead (50)**: Monophonic, cutting, present, designed for melody lines
  - **Pluck (40)**: Short attack, quick decay, percussive, harp/guitar-like
  - **Pad (68)**: Slow attack, long sustain, atmospheric, warm to ethereal
  - **Bass (65)**: Low-frequency, foundational, tight to wobbly
  - **Organ (7)**: Hammond/drawbar-style, warm, rotary
  - **FX (23)**: Risers, drops, impacts, transitions, sound design
- Description budget: 20-40 words per preset (volume demands efficiency)
- For VSTs (DB-33, Hybrid, Loom, etc.), descriptions can be more generic since we don't have per-preset visibility — describe the engine character

**Testing**: Verify all presets have descriptions. Verify category alignment: all "Pad-*" presets tagged as "pad". Verify no preset is missed from directory listing.

**Complexity**: L

---

### Task 2.4 — Description Catalog: Effects

**Description**: Author descriptions for all 60+ effect plugins covering their sonic character and typical use cases.

**Input**: Effect directory listing (from Phase 0 scanner)

**Output**: `data/descriptions/effects.json`

**Implementation Hints**:
- Effects by family:
  - **Compressors** (4): Opto (smooth, transparent), VCA (punchy, fast), Vintage (colored, warm), Bus (glue, master bus)
  - **EQs** (3): PEQ 2-Band, PEQ 4-Band, Para EQ — parametric surgical to broad tonal
  - **Delays** (12): Analog (warm, dark), Ping Pong (wide, bouncy), Tape (vintage, wobbly), Multi-Tap (complex), Stereo (spatial)
  - **Reverbs** (6): Small (room), Medium (hall), Large (cathedral), Large 2 (lush), In Gate (80s effect), Out Gate (modern rhythmic)
  - **Distortions** (6): Amp (guitar), Fuzz (extreme), Overdrive (warm), Custom, Grimey (lo-fi), Tube Drive
  - **Filters** (8): HP, LP, with Sweep/Sync variants — movement and rhythm
  - **Modulation** (7): Chorus, Flanger, Phaser, Ensemble, Tremolo, Autopan
  - **Character** (3): MPC3000 (grit), MPC60 (warmth, Dilla swing), SP1200 (12-bit crunch)
- Each description: what it does sonically, when to use it, genre associations
- Example: "SP1200 — 12-bit digital sampler emulation. Adds lo-fi grit, aliasing warmth, and vintage crunch. Essential for boom-bap, lo-fi hip hop, and classic sample-based production. Used by DJ Premier, Pete Rock, J Dilla."

**Testing**: Verify all 60+ effects have descriptions. Verify no duplicate names. Cross-reference with directory listing from Phase 0 scanner.

**Complexity**: S

---

### Task 2.5 — ONNX Runtime Integration

**Description**: Set up `onnxruntime-node` to run the `all-MiniLM-L6-v2` sentence-transformer model locally. Create an embedding service that takes text → 384-dimensional float vector.

**Input**: Text string (description)

**Output**: `Float32Array` (384 dimensions)

**Implementation Hints**:
- Model: `all-MiniLM-L6-v2` from Hugging Face, converted to ONNX format (~80MB model file)
- Dependencies: `onnxruntime-node` (~30MB native binary)
- Tokenizer: use `@xenova/transformers` tokenizer (pure JS) or bundle pre-computed tokenizer vocab
- Inference pipeline:
  1. Tokenize input text (WordPiece tokenizer, max 256 tokens)
  2. Run ONNX session: input `input_ids`, `attention_mask`, `token_type_ids`
  3. Output: token embeddings → mean pooling → normalize → 384-dim vector
- Mean pooling: average token embeddings weighted by attention mask
- L2 normalization: divide vector by its L2 norm (makes cosine similarity = dot product)
- **Model file shipping**: Bundle as `data/models/all-MiniLM-L6-v2.onnx` or download on first use
- Lazy initialization: load model only when first embedding is requested
- Batched embedding for catalog generation: process all descriptions in one session

**Testing**: Embed "warm pad sound" and "cold harsh lead" → verify cosine similarity < 0.5. Embed "gospel progression" twice → verify similarity > 0.99 (deterministic). Verify vector is normalized (L2 norm ≈ 1.0). Benchmark: should process 100 descriptions in < 5 seconds.

**Complexity**: L

---

### Task 2.6 — Embedding Index Builder

**Description**: Process all description catalogs (Tasks 2.1-2.4) through the embedding service (Task 2.5) to create the persistent `EmbeddingIndex` (C6 contract).

**Input**: All description catalog JSON files

**Output**: `data/embedding-index.json` — serialized `EmbeddingIndex`
```typescript
interface SerializedEmbeddingIndex {
  model: string;              // "all-MiniLM-L6-v2"
  dimensions: number;         // 384
  builtAt: string;
  entries: {
    id: string;
    type: string;
    name: string;
    description: string;
    vector: number[];         // serialized Float32Array
    metadata: Record<string, unknown>;
  }[];
}
```

**Implementation Hints**:
- Estimated entries: ~47 progressions + ~80 arps + ~400 presets + ~60 effects = ~587
- Estimated index size: 587 × 384 × 4 bytes = ~900KB (trivially small)
- Build process:
  1. Load all description catalogs
  2. For each entry, embed(description) → vector
  3. Bundle into index JSON
  4. Write to `data/embedding-index.json`
- Incremental rebuild: hash each description; if hash unchanged, reuse cached vector
- Index format supports type-filtered search (search only presets, or only progressions)
- Include metadata for each entry: file path, category, genre, complexity score, etc.

**Testing**: Build index from all catalogs. Verify entry count matches sum of all catalogs. Verify all vectors are 384-dimensional and normalized. Verify index file size < 2MB.

**Complexity**: M

---

### Task 2.7 — Semantic Search Engine

**Description**: Implement the runtime search function that takes a natural-language query, embeds it, and returns ranked matches from the index.

**Input**: Query string + optional filters (type, genre, category)

**Output**: `SearchResult[]` (C6 contract — ranked by cosine similarity)

**Implementation Hints**:
- At ~587 entries, brute-force cosine similarity is plenty fast (<1ms)
- Algorithm:
  1. Embed query using ONNX service (same model)
  2. Compute dot product with every index vector (pre-normalized, so dot = cosine)
  3. Filter by type/genre/category if specified
  4. Sort descending by similarity
  5. Return top-K results (default K=10)
- Cosine similarity function: `dotProduct(a, b) / (norm(a) * norm(b))` but since normalized, just `dotProduct(a, b)`
- Float32Array operations should use SIMD-friendly patterns (tight loops, avoid allocation)
- Consider: re-ranking by metadata relevance (e.g., boost genre match if user's SongState has a genre)
- Optional: TF-IDF keyword fallback for exact name matches that might not embed well

**Testing**: 
- "warm Sunday morning feeling" → expect "Slow Praise", "RhodesBallad" in top 5
- "aggressive trap bass" → expect Bass presets, Trap progressions in top results
- "80s gated reverb" → expect "Reverb In Gate" effect in top 3
- "gospel" → expect Gospel progressions ranked highest
- Verify top-K parameter works: K=3 returns exactly 3 results
- Verify type filter: type="progression" excludes presets

**Complexity**: M

---

### Task 2.8 — Search Tool Registration & Integration

**Description**: Register the `search_assets` tool via `defineTool()` and integrate the embedding index into the session lifecycle.

**Input**: User query (via LLM tool call)

**Output**: Formatted search results with similarity scores, descriptions, and file paths

**Tool Definition**:
```typescript
defineTool("search_assets", {
  description: "Search all MPC Beats assets (progressions, arp patterns, synth presets, effects) using natural language. Returns ranked matches by relevance.",
  parameters: z.object({
    query: z.string().describe("Natural language search query describing the sound, mood, or character you're looking for"),
    type: z.enum(["progression", "arp", "preset", "effect", "all"]).default("all").describe("Filter to specific asset type"),
    topK: z.number().int().min(1).max(25).default(10).describe("Number of results to return"),
    genre: z.string().optional().describe("Filter to a specific genre"),
  }),
  handler: async ({ query, type, topK, genre }) => {
    // embed query, search index, format results
  }
});
```

**Implementation Hints**:
- Format results for LLM consumption (not raw JSON):
  ```
  Found 10 results for "warm Sunday morning":
  1. [0.87] Slow Praise.progression — Gospel ballad in Db major, warm devotional progression...
  2. [0.84] RhodesBallad.progression — Soulful Rhodes-based ballad...
  3. [0.82] 169-Pad-Warm Pad (TubeSynth) — Warm, enveloping analog pad...
  ```
- Include file paths so the LLM can follow up with `read_progression` or `read_arp_pattern`
- Hook into `onSessionStart`: load index into memory (warm up)
- Index loading strategy: parse JSON → reconstruct Float32Array vectors → hold in memory
- Memory footprint: ~587 entries × 384 floats × 4 bytes ≈ 900KB — negligible

**Testing**: End-to-end: create session, send "Find me something that sounds like a rainy day", verify tool is called, verify results returned, verify results are musically plausible.

**Complexity**: S

---

## Modular Boundaries

| Can develop independently | Notes |
|---|---|
| Tasks 2.1-2.4 (all description catalogs) | Fully parallel; only need Phase 0 parsers + Phase 1 enrichment for 2.1 |
| Task 2.5 (ONNX integration) | Independent — pure ML infrastructure |
| Task 2.6 (index builder) | Requires 2.1-2.5 |
| Task 2.7 (search engine) | Requires 2.6 |
| Task 2.8 (tool registration) | Requires 2.7 + Phase 0 tool infra |

**Parallelization**: 2.1+2.2+2.3+2.4+2.5 all in parallel → 2.6 → 2.7 → 2.8

---

## Cross-Phase Exports

| Export | Consumer |
|---|---|
| `EmbeddingIndex` (C6 contract) | Phase 4 (preset search), Phase 6 (pipeline asset selection), Phase 8 (creative search with inverted queries), Phase 9 (preference centroid tracking) |
| `search_assets` tool | Available to all agents in Phase 6+ |
| `embed(text): Float32Array` function | Phase 9 (embedding user preferences for centroid tracking) |
| Description catalogs (JSON files) | Phase 4 (Sound Oracle reads descriptions), Phase 6 (pipeline uses descriptions for LLM context) |
| `skills/sound/preset-catalog.json` | Loaded by Sound Oracle agent via skillDirectories |

---

## Risk Flags

| Risk | Severity | Description |
|---|---|---|
| ONNX model size (~80MB) | Medium | Increases distribution size. Mitigation: download on first use with progress indicator. |
| Description quality | High | Embedding quality is only as good as the descriptions. Poor descriptions → poor search. The 400+ preset descriptions are the biggest risk — must be reviewed. |
| `onnxruntime-node` platform compatibility | Medium | Native binding — must test on Windows (primary), could be tricky with certain Node.js versions. |
| Tokenizer compatibility | Low | Must use the exact tokenizer that matches the ONNX model. WordPiece vocab file must be bundled. |
| Cold start latency | Low | First embedding call loads the model (~1-2s). Subsequent calls: ~5-10ms per embedding. Mitigate with eager loading on session start. |
| Musical embedding quality | Medium | `all-MiniLM-L6-v2` is a general-purpose text model; it doesn't "understand" music. Query "ii-V-I" won't embed near "jazz" unless the description catalog bridges that gap with text. |
