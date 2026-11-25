# RAG options for the HIV decision-support demo

*Research note, 18 November 2026. It is for learning and fact-finding. It is not a paper. The design choice belongs to the project owner. Section 4 sets out the options without picking one.*

## The short answer

The inconsistent results are most likely a **retrieval** problem, and parts of it can be measured today. I ran the current indexing code on the 7 test patients. The single fixed "audit checklist" query returned the same top passage for three of the four mock patients: a pharmacovigilance-reporting section about adverse-event forms and HMIS reporting. The fourth patient got it at rank 4. Nearly a third of the excerpts (11 of 35) came from the South African guideline even though the patients are Ugandan. 42% of the chunks are longer than the embedding model can read. For one patient, all five "per-drug" sub-queries in the agentic planner turned into the *identical* vector, so they could only retrieve the same five chunks. Fix and measure retrieval first (section 3), then choose an architecture (section 4).

---

## 1. How RAG has evolved

**RAG (retrieval-augmented generation)** means you look up relevant text from your own documents and paste it into the prompt, so the model answers from that text and not from memory. The idea was formalised in 2020 [1]. A widely cited survey splits its history into three stages: naive, advanced and modular [2].

**Naive RAG (2020 to 2023).** You cut documents into fixed-size **chunks** (pieces of text). You turn each chunk into an **embedding**, a list of numbers where similar meanings sit close together. At question time you embed the question and take the nearest *k* chunks (**top-k**). This is what the demo does now. Its weak spots are well documented. In a large expert evaluation of medical RAG, only 22% of the top-16 retrieved passages were relevant, and plain RAG sometimes made answers *worse* than no retrieval [5] (preprint). Models also use evidence less well when it sits in the middle of the prompt, the **"lost in the middle"** effect [27]. The same effect was found in medical RAG [4].

**Advanced RAG (2023 to 2025)** improves each step:
- **Hybrid search.** Combine **BM25** (classic keyword scoring that rewards exact rare words like "TDF" or "creatinine") with **dense** (embedding) search, then merge the two ranked lists. On the MIRAGE medical benchmark, BM25 and the medical retriever MedCPT were the strongest single retrievers, and combining retrievers did best [4].
- **Reranking.** A **cross-encoder** (a small model that reads the question and a candidate chunk *together* and scores the pair) re-orders the top 20 to 50 hits. Two-stage "hybrid then rerank" beat every single-stage method on a mixed text-and-table benchmark [16] (preprint). BM25 for the top 50 followed by MedCPT reranking was the best balance of accuracy and speed on PubMed [18].
- **Query rewriting and HyDE.** An LLM rewrites the question, or writes a fake answer and searches with that (**HyDE**, hypothetical document embeddings) [20]. Results are mixed. Multi-query expansion added noise in a controlled biomedical test [17] and helped little for precise lookups [16] (both preprints). For medicine specifically, query reformulation plus evidence filtering recovered up to 12 points [5].
- **Better chunking.** Split along the document's own structure (headings, tables) instead of every N characters. Content-aware chunking clearly beat fixed-size splitting across 36 methods [21] (preprint). Adding each chunk's heading path ("6.12 Monitoring > 6.12.3 Frequency of VL") raised MRR@5 by 24% on a Markdown knowledge base [22] (preprint). **Contextual retrieval** (Anthropic, 2024) prepends a short LLM-written note to each chunk saying where it sits. Combined with BM25 and a reranker, it cut top-20 retrieval failures by 67% on their benchmarks [33].

**Modular and agentic RAG (2023 to now)** treats retrieval as steps the system can repeat or skip [3]:
- **Self-RAG** trains a model to decide when to retrieve and to critique its own evidence [23].
- **CRAG** (corrective RAG) scores the retrieved set. If the set is poor, CRAG discards or supplements it before answering [24].
- **Iterative or multi-hop RAG** asks follow-up queries based on what it has found so far. i-MedRAG improved over one-shot RAG on complex clinical vignettes [6].
- **Adaptive routing** sends each question to RAG or to the full long document. Self-Route kept long-context quality at lower cost [25].

**GraphRAG and knowledge graphs.** An LLM extracts entities and relations (drug, toxicity, test) into a graph, and retrieval walks the graph [28]. MedGraphRAG reports gains on medical QA [29]. In a direct guideline comparison for chronic kidney disease, though, GraphRAG matched plain RAG on clinician-rated correctness (75.6% vs 76.6%) and produced longer, less clear answers [13]. Indexing is expensive because every chunk goes through an LLM for entity extraction [39].

**Long context instead of retrieval.** Put a whole guideline section, or the whole guideline, into the prompt. With enough compute, long context beat chunk RAG on average [25]. A simple "retrieve, then keep original document order" baseline matched more complex pipelines [26]. For a hepatitis C guideline, giving GPT-4 the guideline as clean, coherent text (tables converted to text) raised accuracy from 43% to 99% [8]. Anthropic suggests skipping RAG entirely for knowledge bases under about 200,000 tokens [33]. The counterweight is that performance still drops as input grows, even on simple tasks ("context rot") [38]. There is no single winner between long context and RAG; it depends on model, task and chunk properties [40] (preprint).

**What the medical evidence says overall.** A meta-analysis of 20 studies found RAG raised the odds of a correct answer by 1.35 times [7]. In guideline studies, retrieval reliably cut hallucination and improved traceability. Accuracy gains were largest for weaker models [11]. With 58 perioperative guidelines, GPT-4 with RAG beat human-written answers (96.4% vs 86.6%) [12]. Three findings matter most for this app:
- RAG did worse on **case-based** questions than on knowledge questions [9]. This app's task is case-based.
- Structured guidelines are easier for models to use than narrative text [32].
- General LLMs were much less accurate on guideline-based HIV questions (35 to 48%) than on general HIV questions [15], and no model was safe without oversight on HIVMedQA [14].

A NICE-guideline system reached 99% recall@10 with hybrid retrieval [10] (preprint). Good retrieval on guidelines is achievable.

## 2. Why the current setup is inconsistent: suspects found in the code

All of these come from the code. Suspects 1 to 3 and 5 I measured on the 7 patients in `Data/`.

1. **Text past the embedder's limit is ignored.** all-MiniLM-L6-v2 truncates input at 256 word pieces (word fragments) [34]. 367 of 879 chunks (42%) are longer than that, so their endings are invisible to search. The chunker (`guideline_processor.py`) also re-seeds each chunk with 200 characters of the previous one.
2. **The query is mostly boilerplate.** `rag_engine._build_query` sends "Alert: Guideline audit checklist / Hint: visit audit checklist labs monitoring regimen…" plus the patient notes. For the longest case the query is 325 tokens, so it is cut off as well. The fixed words dominate, which is why three of the four mock patients got the same top chunk: a pharmacovigilance reporting passage about HMIS forms.
3. **The agentic per-drug queries collapse.** In `agentic_flow._retrieve_evidence`, the patient notes come *before* the sub-task text. For patient "Kintu-Test 001" the notes alone fill the 256-token window, so all 5 sub-queries had cosine similarity 1.000 (identical vectors). The other custom cases scored 0.95 to 0.96. Regimen parsing also produces "drugs" like `"Current ART Regimen: TDF"` and `"TDF/3TC/DTG (TLD) initiated 10 weeks ago."`.
4. **The model sees a fragment.** `llm_screening._build_screening_bundle` passes only the first 480 characters of each 1,200-character chunk. Up to 200 of those characters can be the overlap from the previous chunk. Fixed windows also split headings from their content: one chunk ends with the heading "Frequency of viral load monitoring" and the rule itself is in the next chunk.
5. **Jurisdictions are mixed.** Uganda, South African and WHO guidelines share one index with no source filter. 11 of 35 checklist excerpts for Ugandan patients came from the South African guideline. `page_number` is a page-break counter per file, so a page-range filter means different pages in each file.
6. **There is no reranker, no relevance threshold and no retrieval test.** `tests/test_rag_engine.py` only checks that k results come back.
7. **Silent fallbacks.** If the model fails to load, `Embedder` switches to a hashing bag-of-words. If Chroma fails, `InMemoryVectorStore` is used. Its `index_guidelines` *overwrites* the store on each call, so only the last file (WHO) stays indexed. Neither fallback tells the user.
8. **Generation noise on top.** The LLM ran at temperature 0.2 when this was written (0 since 2026-11-25, `artemis/ai/client.py`). Identical inputs can therefore still produce different alerts. Section 3 shows how to separate the two sources of variation.

## 3. How to find out: evaluate retrieval separately from answers

The literature recommends **stage-aware evaluation**: score retrieval, evidence use and the final answer separately [5]. Without that, a bad alert cannot be blamed on the right step.

- **Gold passages.** For each test case or question, a clinician marks the 1 to 3 guideline passages (or sections) that must be found. Start with 20 to 40 items. The mock patients already carry `expected_demo_outcome`, which can serve as answer-level gold.
- **Retrieval metrics.** **Recall@k**: did a gold passage appear in the top k? **MRR**: how high did the first gold passage rank? Both are a few lines of Python. Ragas has ID-based context recall that does the same [35]. Score by *section*, not by chunk id, so that changing the chunking does not break the gold labels.
- **Answer metrics.** Compare alerts against the expected outcomes. Ragas-style LLM metrics such as faithfulness ("is every claim supported by the excerpts?") work without labels [30]. LLM judges can disagree with clinicians, so spot-check them [13], [11].
- **Noise check.** Run each case 3 to 5 times. If the retrieved chunk ids are identical but the alerts differ, the problem is generation. If the ids differ between similar cases, the problem is retrieval.
- **Retrieval labels that predict answers.** eRAG scores each retrieved passage by whether the LLM answers correctly with it. That label tracks final quality better than relevance labels do [31].

## 4. Options for this app

**For comparison: PolicyLens.** PolicyLens (`graph.py`, `nodes.py`) is a LangGraph loop:
1. **Plan:** an LLM splits the question into up to 5 sub-questions, each tagged with a country.
2. **Retrieve:** top-5 chunks from Chroma, filtered by country metadata, dropping chunks scored below 0.45.
3. **Evaluate:** a strict LLM check answers SUFFICIENT or INSUFFICIENT.
4. **Rewrite:** if insufficient, the query is reworded with alternative legal terms, up to 2 retries.
5. **Synthesize:** the answer is written per country, followed by follow-up questions.

Its chunks carry section headings. The MedGemma planner has none of these: no metadata filter, no threshold, no sufficiency check and no rewrite. Its "agentic" step is a fixed list of templates.

The four options run from simplest to most ambitious.

**Option A: Fix retrieval (structure-aware chunks, hybrid search, reranker).**
- *What:* Split the Markdown at headings and keep tables whole. Prefix each chunk with its heading path and source (contextual retrieval [33], or the free title-chain version [22]). Add `country` and `guideline` metadata and filter to Uganda first. Use short targeted queries, one per problem or drug, with no notes dump. Combine BM25 and dense search, rerank the top 30 to 50 with a cross-encoder, and pass whole chunks to the model.
- *Why here:* It targets suspects 1 to 6 directly and is the best-supported pattern [4], [16], [18], [21].
- *Embedder and reranker:* The evidence is mixed. MedCPT, trained on PubMed search logs, was a top retriever on MIRAGE [19], [4]. A dense baseline came within 0.005 of a reranker on BioASQ, though [17]. MedCPT was trained on literature, not guideline prose. Candidates worth testing on your gold set: MedCPT; a modern general model such as Qwen3-Embedding-0.6B with Qwen3-Reranker-0.6B [37]; and bge-reranker-v2-m3. vLLM can serve rerankers and embedders behind `/rerank`, `/score` and `/embeddings` routes [36].
- *Cost and latency:* About 50 to 300 ms extra for reranking on a GPU. No extra LLM calls (contextual retrieval adds a one-time indexing pass).
- *Effort:* About 2 to 4 days.
- *Risk:* Low.

**Option B: Agentic loop like PolicyLens.**
- *What:* An LLM plans sub-questions from the patient's actual problems, then for each: retrieve (Option A retrieval), check sufficiency, rewrite if needed, and finally synthesize.
- *Why here:* Iterative follow-up helps complex cases [6]. Corrective checks recover from bad retrieval [24]. Reformulation plus filtering helped in medicine [5].
- *Cost and latency:* About 2 to 4 extra 70B calls per sub-question, so tens of seconds per patient.
- *Effort:* About 1 week if Option A is done first.
- *Risk:* The loop cannot fix an index that never surfaces the right passage. The sufficiency judge can also be wrong, and it makes runs less repeatable. Build it on top of A, not instead of A.

**Option C: Long-context section routing.**
- *What:* Build a table of contents from the guideline headings. A rule map (drug or problem to section) or a cheap LLM call picks 2 to 6 sections, and the model gets those sections whole, in document order.
- *Why here:* The Uganda ART extract is about 32,000 tokens (rough estimate at 4 characters per token). Its median section is about 800 tokens and the largest about 4,000, so whole sections fit easily in 65k. This approach has the strongest guideline-specific evidence [8], [25], [26], and it avoids the chunking problems altogether.
- *Cost and latency:* 10,000 to 40,000 prompt tokens per call, so slower prefill on the A100.
- *Effort:* About 2 to 3 days.
- *Risk:* Lost in the middle and context rot [27], [38], [4]. Prompts must stay to one jurisdiction. Routing errors become the new failure point, so measure routing accuracy the same way as recall.

**Option D: Structured rules or GraphRAG (most ambitious).**
- *What:* Extract monitoring and toxicity rules (drug, test, interval, threshold, action) into a reviewed table that `alert_rules.py` checks deterministically. The LLM explains the alerts and catches what the table lacks. Full GraphRAG is the heavier variant.
- *Why here:* It is the most consistent and auditable approach. Structured guideline content is what models handle best [32].
- *Cost:* GraphRAG indexing is costly [39].
- *Effort:* Weeks, plus clinical review of every rule.
- *Risk:* Coverage gaps, and the graph showed no correctness gain over plain RAG in kidney disease [13].

## 5. Suggested experiment order (measure after every step)

1. Build the gold set (section 3) and record the **baseline** recall@5, recall@10, MRR and alert match. Include 3 to 5 repeat runs per case.
2. **Hygiene fixes:** stop the 480-character cut, put sub-task text first in queries, fix regimen parsing, make fallbacks loud, and fix the in-memory overwrite.
3. **Structure-aware chunks** with heading prefixes and source and country metadata.
4. **Embedder swap:** MiniLM vs MedCPT vs Qwen3-Embedding or BGE-M3, each with a longer input window.
5. **Hybrid** BM25 and dense, merged with reciprocal-rank fusion (a simple way to merge ranked lists).
6. **Reranker** on the top 30 to 50.
7. Compare **Option A vs Option C** on the answer-level metrics.
8. Add **Option B's loop** only if answer failures remain where gold passages were retrieved but are spread across sections (multi-hop).

Change one thing at a time. The point is to know which change moved the numbers.

---

## How this was researched

- **Consensus:** 14 searches, all successful (about 95 unique papers returned, 33 cited). Coverage was thinner on HIV-specific RAG: no HIV guideline RAG study was found.
- **Web:** 8 searches and fetches for 2024 to 2026 practice (Anthropic, Hugging Face, Ragas, vLLM, Chroma, Microsoft GraphRAG).
- **Code measurements:** run with the project `.venv` against the worktree code. The in-memory store was patched to keep all four files. Chroma ranking should match, because cosine and L2 distance rank normalised vectors the same way.
- **Preprints:** sources marked "preprint" are not yet peer reviewed.

## Sources

1. Lewis et al., 2020. [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://consensus.app/papers/details/w:46eb700b-7af5-45cf-b391-053d1fcf4851/?utm_source=claude_desktop). NeurIPS.
2. Gao et al., 2023. [Retrieval-Augmented Generation for Large Language Models: A Survey](https://consensus.app/papers/details/w:15622e07-05ae-4b5d-b8a3-57cad2682944/?utm_source=claude_desktop). arXiv.
3. Gao et al., 2026. [Modular RAG: Transforming RAG Systems into LEGO-like Reconfigurable Frameworks](https://consensus.app/papers/details/w:57d42e92-b3dd-4a4c-aa2d-1bd99f3731ec/?utm_source=claude_desktop). ACM TOIS.
4. Xiong et al., 2024. [Benchmarking Retrieval-Augmented Generation for Medicine](https://consensus.app/papers/details/w:0a7560d7-8d75-42ee-a901-86831c222780/?utm_source=claude_desktop). Findings of ACL.
5. Kim et al., 2025. [Rethinking Retrieval-Augmented Generation for Medicine: A Large-Scale, Systematic Expert Evaluation and Practical Insights](https://consensus.app/papers/details/w:738cfd47-5b29-4e83-aeaa-0e1d416e06ca/?utm_source=claude_desktop). arXiv preprint.
6. Xiong et al., 2024. [Improving Retrieval-Augmented Generation in Medicine with Iterative Follow-up Questions](https://consensus.app/papers/details/w:ba5e9da0-29c7-4632-bb6c-3508385d43cf/?utm_source=claude_desktop). PSB.
7. Liu, McCoy and Wright, 2025. [Improving large language model applications in biomedicine with retrieval-augmented generation: a systematic review, meta-analysis, and clinical development guidelines](https://consensus.app/papers/details/w:c7f785f1-bd5d-4f22-867f-bd3d820eb22e/?utm_source=claude_desktop). JAMIA.
8. Kresevic et al., 2024. [Optimization of hepatological clinical guidelines interpretation by large language models: a retrieval augmented generation-based framework](https://consensus.app/papers/details/w:0b9725f2-819f-4799-9f1b-169ff0353f76/?utm_source=claude_desktop). npj Digital Medicine.
9. Masanneck et al., 2025. [Evaluating base and retrieval augmented LLMs with document or online support for evidence based neurology](https://consensus.app/papers/details/w:c04aa5ba-6370-48b7-8f07-6c85162d61d5/?utm_source=claude_desktop). npj Digital Medicine.
10. Lewis, Thio et al., 2025. [Grounding Large Language Models in Clinical Evidence: A RAG System for Querying UK NICE Clinical Guidelines](https://consensus.app/papers/details/w:86dd9c79-810c-4674-ba0b-64fdf5cb125c/?utm_source=claude_desktop). arXiv preprint.
11. Vollmer et al., 2026. [A Self-Controlled Benchmark of Retrieval-Augmented Generation for Large Language Models on Clinical Guideline Questions](https://consensus.app/papers/details/w:b0f38f30-e11b-4d4b-a9c1-df643e29c45b/?utm_source=claude_desktop). Diagnostics.
12. Ke et al., 2025. [Retrieval augmented generation for 10 large language models and its generalizability in assessing medical fitness](https://consensus.app/papers/details/w:d6857f7c-c63a-4c34-a44f-6203a24e278a/?utm_source=claude_desktop). npj Digital Medicine.
13. Sesen, Au Yeung and Asgari, 2026. [Development and evaluation of RAG and GraphRAG for guideline-based clinical decision support in chronic kidney disease](https://consensus.app/papers/details/w:23ff9462-5dfb-49e4-a72e-5d010c4a80c2/?utm_source=claude_desktop). BMJ Digital Health & AI.
14. Cardenal et al., 2026. [Benchmarking large language models for HIV medical decision support](https://consensus.app/papers/details/w:07263052-f5fa-4274-92fa-69d8d93624d3/?utm_source=claude_desktop). Communications Medicine.
15. Tarhan and Şahin Özdemir, 2025. [Comparison of the accuracy and reliability of ChatGPT-4o and Gemini in answering HIV-related questions](https://consensus.app/papers/details/w:95b993c9-afc3-4030-8e9e-5f510b7d26a7/?utm_source=claude_desktop). BMC Infectious Diseases.
16. Akarsu, Karaman and Mierbach, 2026. [From BM25 to Corrective RAG: Benchmarking Retrieval Strategies for Text-and-Table Documents](https://consensus.app/papers/details/w:d873d701-75c7-4645-b6b5-8c73ec08ac10/?utm_source=claude_desktop). arXiv preprint.
17. Bal and Puhan, 2026. [Benchmarking Retrieval Strategies for Biomedical Retrieval-Augmented Generation: A Controlled Empirical Study](https://consensus.app/papers/details/w:7b1d6e43-b76f-4b71-925e-595a42b56470/?utm_source=claude_desktop). arXiv preprint.
18. Stuhlmann, Saxer and Fürst, 2025. [Efficient and Reproducible Biomedical Question Answering Using Retrieval Augmented Generation](https://consensus.app/papers/details/w:d2b0e6ba-e745-48b0-a856-49f2ab650625/?utm_source=claude_desktop). IEEE SDS.
19. Jin et al., 2023. [MedCPT: Contrastive Pre-trained Transformers with large-scale PubMed search logs for zero-shot biomedical information retrieval](https://consensus.app/papers/details/w:86e50026-5823-4bf5-93bc-aa2c511c313e/?utm_source=claude_desktop). Bioinformatics.
20. Gao et al., 2023. [Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE)](https://consensus.app/papers/details/w:99f7a827-55a0-4512-98e1-ba97167ab9e0/?utm_source=claude_desktop). ACL.
21. Shaukat, Adnan and Kuhn, 2026. [A Systematic Investigation of Document Chunking Strategies and Embedding Sensitivity](https://consensus.app/papers/details/w:fe6efa1f-8031-412e-b889-33ec5564f337/?utm_source=claude_desktop). arXiv preprint.
22. Yang, 2026. [Structure-Aware Semantic Chunking with Title-Chain Prefixes](https://consensus.app/papers/details/w:f08b1621-cfcd-4af1-87f7-f9498fd91ceb/?utm_source=claude_desktop). arXiv preprint.
23. Asai et al., 2023. [Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection](https://consensus.app/papers/details/w:2e0a328a-4ddb-4623-8a12-63127ce9a884/?utm_source=claude_desktop). arXiv.
24. Yan et al., 2026. [Corrective Retrieval Augmented Generation](https://consensus.app/papers/details/w:64ffc79b-19c3-4625-9e27-111892a0809e/?utm_source=claude_desktop). Findings of IJCNLP-AACL.
25. Li et al., 2024. [Retrieval Augmented Generation or Long-Context LLMs? A Comprehensive Study and Hybrid Approach](https://consensus.app/papers/details/w:cf456c67-19f9-417f-8a35-19c51db67764/?utm_source=claude_desktop). EMNLP Industry.
26. Laitenberger, Manning and Liu, 2025. [Stronger Baselines for Retrieval-Augmented Generation with Long-Context Language Models](https://consensus.app/papers/details/w:91e4f24a-5f50-4d3c-8b85-939e1f28021b/?utm_source=claude_desktop). EMNLP.
27. Liu et al., 2024. [Lost in the Middle: How Language Models Use Long Contexts](https://consensus.app/papers/details/w:710471c2-98ae-4b94-a257-f0edd90c63e7/?utm_source=claude_desktop). TACL.
28. Peng et al., 2025. [Graph Retrieval-Augmented Generation: A Survey](https://consensus.app/papers/details/w:d537b2d3-3fa9-4e3d-8b82-85240589581d/?utm_source=claude_desktop). ACM TOIS.
29. Wu et al., 2025. [Medical Graph RAG: Evidence-based Medical Large Language Model via Graph Retrieval-Augmented Generation](https://consensus.app/papers/details/w:836f968a-6ecd-4b7f-a461-6c547cba20f5/?utm_source=claude_desktop). ACL.
30. Es et al., 2023. [Ragas: Automated Evaluation of Retrieval Augmented Generation](https://consensus.app/papers/details/w:00a55b26-031f-4580-9dfa-10c16ee8e8ab/?utm_source=claude_desktop). arXiv.
31. Salemi and Zamani, 2024. [Evaluating Retrieval Quality in Retrieval-Augmented Generation](https://consensus.app/papers/details/w:d054abcc-e498-4c91-8b3a-639751413f1b/?utm_source=claude_desktop). SIGIR.
32. Wang and Chen, 2026. [Evaluating large language models for evidence-based clinical question answering](https://consensus.app/papers/details/w:1737531a-c5dd-4367-b927-19b19a5df8e4/?utm_source=claude_desktop). Patterns.
33. Anthropic, 2024. [Introducing Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval). Web.
34. Hugging Face. [sentence-transformers/all-MiniLM-L6-v2 model card](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2). Web.
35. Ragas docs. [Context Recall (including ID-based)](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/context_recall/). Web.
36. vLLM docs. [Pooling models: scoring and reranking](https://docs.vllm.ai/en/stable/models/pooling_models/scoring/). Web.
37. Zhang et al. (Qwen team), 2025. [Qwen3 Embedding: Advancing Text Embedding and Reranking Through Foundation Models](https://arxiv.org/html/2506.05176v3). arXiv preprint (web).
38. Hong, Troynikov and Huber (Chroma), 2025. [Context Rot: How Increasing Input Tokens Impacts LLM Performance](https://research.trychroma.com/context-rot). Web.
39. Microsoft. [GraphRAG indexing methods and costs](https://microsoft.github.io/graphrag/index/methods). Web.
40. Li et al., 2025. [LaRA: Benchmarking RAG and Long-Context LLMs, No Silver Bullet for LC or RAG Routing](https://consensus.app/papers/details/w:894136f7-fcb1-425f-a51f-32ce6b34986e/?utm_source=claude_desktop). arXiv preprint.
