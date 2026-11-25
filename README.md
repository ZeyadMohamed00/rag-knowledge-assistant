# RAG Knowledge Assistant

Ask questions over a folder of documents. The system splits documents into chunks, retrieves the most relevant ones, and answers **with citations** (`[doc#chunk]`). Says "I don't know" when nothing relevant is found.

> Honest scope
> - No LLM is required. By default answers are **extractive** (best-matching sentences from retrieved chunks). If `LLM_API_KEY` is set, an OpenAI-compatible endpoint writes the answer from the retrieved chunks only. **The LLM path was written but not run** (no API key was available), so treat it as untested.
> - Retrieval is keyword/TF-IDF based (BM25 written from scratch + scikit-learn TF-IDF). There are **no embeddings** yet.
> - The Docker files were **not built or run** (Docker was unavailable when this was written). Tests and the API were run locally on Python 3.10.

## Run
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q                                   # 11 tests
python eval/run_eval.py                     # retrieval metrics
python -m rag.cli data/docs "What does a foreign key do?"
uvicorn rag.api:app --reload                # POST /ask {"question": "..."}
```
Put your own `.txt`/`.md` files in `data/docs` (or set `DOCS_DIR`).

## Architecture
```
docs -> chunking (60 words, 15 overlap) -> index: BM25 + TF-IDF -> hybrid score
question -> retrieve top-k chunks -> generate (extractive | LLM) -> answer + sources
```
Files: `rag/chunking.py`, `rag/retrieval.py`, `rag/generate.py`, `rag/store.py`, `rag/api.py`, `eval/run_eval.py`.

## Evaluation (real run of `python eval/run_eval.py`)
12 short docs (22 chunks), 24 questions, hit = a top-k chunk is from the expected document.

| mode | hit@1 | hit@3 | MRR |
|---|---|---|---|
| bm25 | 0.96 | 1.00 | 0.979 |
| tfidf | 0.96 | 1.00 | 0.979 |
| hybrid | 0.96 | 1.00 | 0.979 |

**Read this carefully:** the corpus and the questions were written by the same person, the corpus is tiny, and questions share vocabulary with the docs. So all modes tie and the numbers are optimistic. This shows the pipeline works, it does **not** prove it is good on real data. Next step: a larger real corpus and paraphrased questions, plus embeddings to handle synonyms.

## How it works / key decisions
1. **Chunking**: fixed windows of words with overlap, so a fact split at a boundary is still found. Trade-off: small chunks are precise but lose context; large chunks keep context but add noise.
2. **BM25**: score = sum over query terms of `idf * tf*(k1+1) / (tf + k1*(1-b+b*len/avglen))`. Rare words count more, and long chunks are not unfairly favoured.
3. **TF-IDF cosine** with bigrams catches phrases. **Hybrid** averages max-normalised BM25 and TF-IDF scores.
4. **Grounding**: answers cite chunk ids; if retrieval returns nothing the system refuses instead of guessing. This is the main defence against hallucination.
5. **Pluggable generation**: `answer()` switches between extractive and LLM, so the retrieval part is testable with no API.

## Interview questions to prepare
Why chunk with overlap? What does BM25's `b` do? Keyword vs embedding search trade-offs? How would you measure answer quality (faithfulness vs retrieval hit rate)? What would break at 1M documents (need an ANN index / vector DB)?

## CI
A GitHub Actions workflow is in `ci/github-actions-ci.yml`. Move it to `.github/workflows/ci.yml` to enable it. It is not enabled because the push token had no `workflow` scope, and it has not been run on GitHub.
