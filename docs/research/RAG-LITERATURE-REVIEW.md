# What researchers have tried: a ranked literature review for the HIV visit-audit RAG

*Literature review, 18 November 2026. Companion to `RAG-OPTIONS.md`, which explains the basic techniques and the problems in the current code. This file does not repeat that material. It ranks what other teams have actually built and measured, so the owner can pick an approach to copy, beat or improve on. Sources marked "(preprint)" have not yet been peer reviewed. Numbers in square brackets point to the source list in section 7.*

**Terms used throughout.** *RAG* (retrieval-augmented generation): look up passages from your own documents and paste them into the prompt. *Retriever*: the search step. *Embedding search* (or *dense* search): find passages whose meaning is close to the query, using vectors of numbers. *BM25*: classic keyword search that rewards exact rare words such as "TDF" or "creatinine". *Hybrid search*: run both and merge the two ranked lists. *Reranker*: a second, slower model that reads the query and each candidate passage together and re-orders the top hits. *Recall@10*: share of test questions where a correct passage appears in the top 10. *F1*: one number that balances "how many real problems were caught" against "how many flags were false". *LLM-as-judge*: using a model to grade another model's answers.

---

## 1. Short answer

For a task shaped like ours (read one patient visit, check it against a national guideline, flag what is wrong or missing), the literature points to four things, in this order of evidence:

1. **Give the model clean, well-structured guideline text, in whole sections.** Rewriting a hepatitis C guideline into coherent text (tables turned into sentences) raised GPT-4's accuracy from 43% to 99% [12]. Models score about 90% on structured guidelines, 70% on narrative text [20].
2. **Use hybrid keyword-plus-embedding search over heading-based sections, not embeddings alone.** Hybrid search beat embedding-only search in almost every medical comparison found [17][18][44][47], and a hybrid system over 300 NICE guidelines reached 99.1% recall@10 [19] (preprint).
3. **Turn the hard rules (monitoring intervals, toxicity thresholds, interaction pairs) into explicit checks.** Forcing the model through a fixed rule procedure raised protocol adherence from 32% to 100% [27]. In 847,000 real medication orders, rules plus a model missed far fewer dangerous orders than rules alone (3.2 to 4.8 vs 9.4 misses per 1,000) [7].
4. **Fire alerts only when needed, with severity levels, inside the clinician's workflow.** This is the only design shown to cut real clinical errors in African primary care: 16% fewer diagnostic and 13% fewer treatment errors over 39,849 visits in Nairobi [1] (preprint). A separate Kenyan randomized trial found it safe but saw no change in 14-day treatment failure [2].

Agentic loops (the model searches several times and checks itself) and GraphRAG (retrieval over a knowledge graph) give small or no gains on guideline tasks, at much higher cost [14][39][55]. Nobody has published HIV-guideline RAG checked against real patient visits in Africa.

---

## 2. Ranked table of applications closest to ours

**Ranking rule.** Each study gets two scores and one adjustment:
- **Similarity (S, 0 to 3).** 3 = reads a patient record or prescription and checks it against guidelines or for medication problems (our task). 2 = answers patient cases or vignettes from guidelines. 1 = answers guideline questions with no patient. 
- **Evidence (E, 1 to 4).** 4 = randomized trial or real-world deployment with patient-level outcomes. 3 = real patient records (retrospective or prospective). 2 = clinician-graded vignettes. 1 = automated benchmark only. A preprint loses 0.5.
- **Benefit.** Multiply by 1.0 if the paper shows a clear gain, 0.75 if the result is mixed or null.

Rank = S × E × benefit, highest first. Ties go to the stronger study design. A vignette is a short written patient case.

| # | Paper | Year | Setting | Task | RAG / method | Model | Data & size | Key result | Evidence (S×E×benefit) | What we could borrow |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | AI Consult, Penda Health [1] | 2025 | Kenya, 15 primary care clinics | Safety net that flags documentation, diagnosis and treatment errors during the visit | LLM checks the visit at decision points; fires only when needed; guideline context | OpenAI model (abstract does not name the version) | 39,849 real visits, rated by independent physicians | 16% fewer diagnostic errors, 13% fewer treatment errors; all surveyed clinicians said care improved | Real-world field study, preprint (3×3.5×1 = 10.5) | The whole product shape: in-workflow trigger, severity tiers, "only when needed", active rollout |
| 2 | Kenyan cluster RCT of LLM CDS [2] | 2026 | Kenya, 16 primary care facilities | EMR-embedded LLM assistance vs none | LLM CDS in the EMR | Not stated in abstract | 9,691 patients, 103 clinical officers | Treatment failure 2.2% vs 2.0% (aOR 0.77, 95% CI 0.55 to 1.08); no safety signal | RCT, peer-reviewed (3×4×0.75 = 9) | Honest outcome: alerts alone may not change 14-day outcomes; design a process measure we can move |
| 3 | ClinicalGPT order-time medication audit [7] | 2026 | 7 health systems | Flag high-risk medication orders using labs and medication history | Compared rules only, LLM, RAG + LLM + rules, and a model with hard rule constraints | Custom EHR foundation model vs LLM comparators | 847,000 real orders | Misses per 1,000: 3.2 (model + hard constraints), 4.8 (RAG + LLM + rules), 6.1 (generic LLM), 9.4 (rules only) | Retrospective, real records, peer-reviewed (3×3×1 = 9) | Layer rules and LLM; report misses and false alerts per 1,000 visits |
| 4 | LLM measuring ADHD side-effect monitoring [31] | 2024 | US primary care network | Did the clinician do the guideline-required monitoring? | Fine-tuned open model classifying notes | LLaMA | 1,201 children, 15,628 notes | Sensitivity 87.2%, specificity 86.3%, AUC 0.93 | Retrospective, real records, peer-reviewed (3×3×1 = 9) | Closest published analogue to our "missed monitoring" alert; per-note yes/no framing |
| 5 | Heart failure medication guideline adherence [65] | 2025 | Hospital EHR data | Do discharge medicines and doses follow the ESC guideline? | Prompting (zero-shot, few-shot, chain-of-thought) vs fine-tuning on synthetic preference data | 6 open 7–9B models | 1,141 patients | Prompting F1 < 0.40; after fine-tuning four models F1 ≥ 0.90 | Retrospective, real records, peer-reviewed (3×3×1 = 9) | Warning that small models cannot audit adherence by prompting alone; a 70B may, but must be measured |
| 6 | Medication-safety RAG co-pilot [5] | 2025 | Singapore, 16 specialties | Detect prescribing errors in medication charts | RAG framework, 5 LLMs; LLM alone vs pharmacist + LLM vs pharmacist alone | 5 LLMs (best one used for the arms) | 91 error scenarios in 40 vignettes | Co-pilot best: accuracy 61%, F1 0.59; 1.5× pharmacist accuracy on serious-harm errors | Prospective crossover, peer-reviewed (3×2.5×1 = 7.5) | Error taxonomy, co-pilot evaluation design, scoring serious-harm errors separately |
| 7 | Safety review of a Kenyan LLM CDS [3] | 2026 | Kenya, 16 primary care clinics | Physician review of deployed LLM advice | EMR-embedded LLM CDS | Not stated in abstract | 1,469 records | Hallucinations 3.4%; 99% aligned with local guidelines; harmful advice in 7.8%, and 67 of 115 harmful items reached the final notes; risk in the clinician's note fully fixed in 8.0% | Retrospective, real records, peer-reviewed (3×3×0.75 = 6.75) | Clinicians adopt harmful and helpful advice unevenly; audit our own harmful-advice rate |
| 8 | HemaGuide tumour-board agent [30] | 2026 | Academic haematology centres | Patient documents to treatment recommendation | Converts notes to a structured case, routes to decision modes, grounds in guideline flowcharts plus a memory of >2,000 past cases | Six foundation models, locally deployable | 45 complex cases; external validation on 555 | Better concordance with tumour board; 39 s median; no single component sufficient | Expert-blinded plus external validation, peer-reviewed (2.5×2.5×1 = 6.25) | Structure the patient first, then route by case type |
| 9 | RAG vs long context over EHR notes [13] | 2026 | US academic hospital | Extract and reason over real inpatient notes | Targeted retrieval vs most recent notes vs long context | GPT-5.4-mini, Mistral Medium 3, DeepSeek V3.1 | Real inpatient notes, 3 tasks | Under 8K retrieved tokens matched or beat long context (+0.17 to +9.83 F1 on imaging) | Retrospective, real records, peer-reviewed (2×3×1 = 6) | Retrieve from the patient history too, not only from guidelines |
| 10 | GPT-4 help for management reasoning [32] | 2025 | US, 92 physicians | Management plans for real-case vignettes | Plain GPT-4 access vs usual resources | GPT-4 | 92 physicians, 5 cases | +6.5 points with LLM; LLM alone equal to LLM + physician | RCT on vignettes, peer-reviewed (2×3×1 = 6) | A management-plan rubric we could reuse for our "suggested plan" output |
| 11 | LLM medication safety reviews, NHS [6] | 2025 | UK primary care | Find medication safety issues in real records | LLM review system, several models | Several state-of-the-art models | 277 patients from 2.1M-adult EHR | Sensitivity 100%, specificity 83.1%, but all issues and actions right in only 46.9% | Retrospective, real records, preprint (3×2.5×0.75 = 5.6) | Their 5 failure patterns, including "applying standard guidelines without adjusting for patient context"; 45 public failure vignettes |
| 12 | LLM help for physicians in Pakistan [33] | 2026 | Pakistan (LMIC), 60 physicians | Diagnostic reasoning on vignettes | LLM access after 20-hour AI-literacy course | Not stated in abstract | 58 physicians | 71.4% vs 42.6% (+27.5 points); LLM alone beat LLM + physician | RCT on vignettes, peer-reviewed (1.5×3×1 = 4.5) | Train users; show model reasoning in a way clinicians can check |
| 13 | Local-guideline antibiotic chatbot [8] | 2026 | UK hospital | Answer infection questions from local guidelines | Keyword match + medical embedding to find guideline sections; single- vs multi-stage | gpt-oss-20b, run locally | 200 simulated + 66 human questions | 87% fully correct; 81% on human questions; same model without RAG 11%, frontier model without RAG 46% | Specialist-graded vignettes, peer-reviewed (2×2×1 = 4) | Section-level hybrid retrieval, local model, out-of-scope test questions |
| 14 | AnemiaCare deterministic prompting [27] | 2025 | Haemodialysis | Dose decisions from 6 lab inputs | Fixed rule logic written into the prompt vs loose prompt | Not stated in abstract | 600 simulated scenarios | Protocol adherence 32% (loose) vs 100% (deterministic) | Nephrologist-graded simulation, peer-reviewed (2×2×1 = 4) | Write the HIV monitoring and toxicity rules as an explicit step list |
| 15 | PSA testing RAG vs junior doctors [9] | 2025 | Singapore | Guideline-concordant testing advice for cases | RAG over society guidelines | Not stated in abstract | 220 case scenarios | 95.5% vs 62.3% (closed book) and 74.1% (open book) for junior clinicians | Vignettes vs clinicians, peer-reviewed (2×2×1 = 4) | Compare against clinicians with and without the guideline open |
| 16 | Canadian radiology guideline RAG [10] | 2025 | Canada | Follow-up advice for incidental findings | Custom RAG | GPT-4o, o1-mini | 319 cases | 81.7% → 97.2% (GPT-4o); 79.3% → 95.1% (o1-mini) | Vignettes, peer-reviewed (2×2×1 = 4) | Simple RAG gives large gains when the guideline is narrow and well indexed |
| 17 | Perioperative fitness RAG, 10 LLMs [11] | 2025 | Singapore | Surgical fitness and instructions from 58 guidelines | RAG with local and international guidelines | 10 LLMs incl. Llama 3 | 14 scenarios, 3,234 answers | GPT-4 + RAG 96.4% vs human answers 86.6% | Vignettes, peer-reviewed (2×2×1 = 4) | Which guideline set is indexed changes results (GPT-4 did best with international guidelines) |
| 18 | Kenyan primary care vignettes [16] | 2026 | Kenya | Open-ended primary care questions | No RAG; LLMs vs Kenyan clinicians | GPT-4.1, Gemini 2.5 Flash, DeepSeek-R1, MedGemma, o3 | 507 of 5,107 local vignettes | LLMs beat clinicians in 9 of 11 domains (guideline alignment 4.25–4.72 vs 2.86 of 5) | Blinded physician panel, peer-reviewed (2×2×1 = 4) | Local vignette bank and an 11-domain rubric; strong African baseline |
| 19 | CKD: RAG vs GraphRAG [14] | 2026 | UK | Guideline answers for synthetic CKD patients | Vector RAG vs GraphRAG | GPT-4o | 70 patients × 9 questions | Correctness 70.8% (none), 76.6% (RAG), 75.6% (GraphRAG); GraphRAG longer and less clear | Clinician-rated, peer-reviewed (2×2×0.75 = 3) | Skip GraphRAG for now |
| 20 | Hepatitis C guideline formatting [12] | 2024 | Italy | Guideline questions | Guideline in context; reformatting; few-shot | GPT-4 Turbo | Expert-written questions | 43% → 99% when guideline given as coherent text with tables converted | Expert review, peer-reviewed (1.5×2×1 = 3) | Convert our Markdown tables into plain sentences |
| 21 | HIVMedQA [15] | 2026 | Switzerland | HIV QA incl. complex vignettes | No RAG; 10 LLMs | Gemini 2.5 Pro best, then Claude 3.5 Sonnet, MedGemma-27B | Clinician-curated HIV set | Medical models not consistently better; reasoning weaker than recall; LLM judge tracks clinicians better than word-overlap scores | Benchmark + physicians, peer-reviewed (2×1.5×1 = 3) | A ready HIV test set and judge rubric |
| 22 | CoMed drug-combination alerts [25] | 2026 | China | Flag risky drug pairs | RAG + expert reasoning steps + multi-agent report | Qwen2.5-Max with chain-of-thought | Benchmark of drug pairs | F1 0.971, AUC 0.982 | Benchmark, peer-reviewed (2×1×1 = 2) | Pair a drug-interaction source with step-by-step reasoning |
| 23 | CPGPrompt [26] | 2026 | US | Walk a patient vignette through a guideline decision tree | Guideline turned into a decision tree the LLM navigates | Not stated in abstract | Synthetic vignettes, 3 domains | Referral yes/no F1 0.85–1.00; fine pathway F1 0.47–0.77 | Benchmark, peer-reviewed (2×1×1 = 2) | Decision trees work for yes/no, less for fine-grained choices |
| 24 | German neurovascular guidelines [17] | 2025 | Germany | Guideline QA | RAG; compared BM25 and dense retrievers | Claude 3.5 Sonnet, Llama 3.1 405B, others | 2 guidelines | 80% of wrong answers came from retrieval; BM25 82.0% > bge-m3 78.4% | Expert-graded, peer-reviewed (1×2×1 = 2) | Fix retrieval first; keyword search is strong on guidelines |
| 25 | Expert evaluation of medical RAG [21] | 2025 | Multi-country | Real patient and exam queries | Standard RAG pipeline, decomposed | GPT-4o, Llama-3.1-8B | 200 queries, 80,502 expert annotations | Only 22% of top-16 passages relevant; RAG lowered factuality by up to 6% | Expert-annotated, preprint (1.5×1.5×0.75 = 1.7) | Score retrieval, evidence use and answer separately |
| 26 | NICE guideline RAG [19] | 2025 | UK | Guideline lookup | Hybrid embedding retrieval | O4-Mini, GPT-4.1 | 300 guidelines, 10,195 chunks, 7,901 queries | MRR 0.814, recall@10 99.1%; faithfulness 99.5% | Benchmark + 7 experts, preprint (1×1.5×1 = 1.5) | Target numbers for our retrieval test |
| 27 | Sleep-medicine RAG design [18] | 2026 | US | MCQ and case vignettes | Raw vs table-of-contents-aligned corpus; dense vs hybrid | Llama-3 8B/70B, Qwen 2.5 | 5 textbooks | Hybrid > dense always; structured corpus +6.1% diagnosis; Llama-8B lost 7.1% with raw text + dense | Benchmark, peer-reviewed (1.5×1×1 = 1.5) | Structure-aligned sections plus hybrid search, cheaply |
| 28 | Structured patient data vs RAG [28] | 2026 | Synthetic | Grounded claims about a patient | RAG over raw notes vs structured patient "artifacts" | GPT-4o-mini | 100 vignettes × 3 seeds | Unsupported claims 5.0% (none) → 43.6% (RAG over raw text) → 8.4% (structured) | Benchmark, preprint (2×0.5×1 = 1) | Build a structured patient summary (regimen, dates, labs) before retrieval |

---

## 3. Best-in-class deep dives

### 3.1 Penda Health "AI Consult" (Kenya) [1][2][3][4]

**What they built.** An LLM tool inside the clinic's electronic record that reviews the visit at key points and flags possible documentation, diagnosis and treatment errors. The abstract stresses that it "activates only when needed" and leaves the decision with the clinician [1]. From our reading of the full preprint (verify before quoting): it shows a traffic-light result (green, yellow, red), and red items need the clinician's attention before moving on. Rollout was active: peer champions and coaching, not just switching it on.

**Numbers.** In 39,849 visits rated by independent physicians, clinics with the tool had 16% fewer diagnostic errors and 13% fewer treatment errors [1]. Uptake grew from 4% to 47% of visits over eight months, and 99.5% of clinician feedback was positive [4]. A separate physician review of 1,469 records found 3.4% hallucinations and 99% guideline alignment, but harmful advice in 7.8% of visits; 67 of those 115 harmful items made it into the final notes [3]. The cluster RCT with 9,691 patients found no difference in 14-day treatment failure (2.2% vs 2.0%) and no safety signal [2].

**Match, beat or adapt?** Adapt. Our use case is the same shape (audit one visit against national guidelines in East African primary care). We cannot match their scale, but we can copy the alert design (severity levels, fire only on real issues), and we can do something none of them report: score every alert against a named guideline section. Their weak spot is uneven adoption of harmful advice [3]. A citation check per alert (section 4.11) is a direct answer to that.

### 3.2 Rules plus model for medication safety [7][27][5]

**What they built.** ClinicalGPT [7] encodes medication orders, labs and their timing, then adds hard rule constraints on top of the model. The comparators included "rules only" and "RAG + LLM + rules". AnemiaCare [27] wrote the dosing protocol into the prompt as a fixed sequence of steps with mandatory safety alerts. The Singapore co-pilot [5] used RAG to support pharmacists reviewing charts.

**Numbers.** Misses per 1,000 high-risk orders: 9.4 for rules only, 6.1 for a generic LLM, 4.8 for RAG + LLM + rules, 3.2 for the constrained model, with fewer false alerts than rules alone (33.9 vs 38.7 per 1,000) [7]. Protocol adherence jumped from 32% to 100% with deterministic prompting [27]. Pharmacist + LLM caught serious-harm errors 1.5 times as often as pharmacists alone, though overall accuracy was only 61% [5].

**Match, beat or adapt?** Match, cheaply. The HIV monitoring rules are short and well defined (viral load timing, creatinine on TDF, interactions with dolutegravir or rifampicin). A reviewed rule table plus the 70B model explaining and catching what the table misses is the "RAG + LLM + rules" arm of [7], which beat both rules alone and a plain LLM. We would not build our own foundation model.

### 3.3 Local-guideline antibiotic chatbot (Oxford) [8]

**What they built.** Guideline sections found by combining keyword matching with a medical embedding model; a small open model (gpt-oss-20b) run locally; single-stage and multi-stage versions; test sets of 200 simulated questions (LLM judge) plus 66 human-written questions reviewed by at least two infection specialists, including out-of-scope questions.

**Numbers.** 87% fully correct on simulated questions; 81% fully and 18% partly correct on human questions; multi-stage 84%. Without the local guideline, the same model got 11% fully correct and a frontier model 46%. It recognised only 5 of 9 out-of-scope questions. Errors clustered in complex cases such as renal impairment.

**Match, beat or adapt?** Match, and probably beat. Their setup is the closest to ours technically: local model, local guideline, section-level hybrid retrieval, one GPU. Our model is larger (70B vs 20B). Their test design (simulated plus clinician-written questions, plus deliberate out-of-scope cases) is the one to copy for our small labelled set. Renal impairment is exactly where TDF alerts live, so their weak spot is our main test.

### 3.4 Clean guideline text, in whole sections [12][20][18][13]

**What they built.** Kresevic et al. [12] compared GPT-4 with no guideline, the guideline in context, the guideline reformatted (tables turned into text), and few-shot examples. Li et al. [18] compared raw textbook text with chunks aligned to the table of contents. Myers et al. [13] compared targeted retrieval against stuffing long patient histories into the prompt.

**Numbers.** 43% to 99% accuracy once the guideline was coherent text with tables converted [12]. Accuracy around 90% on structured guidelines vs 70% on narrative sources [20]. Structured corpus +6.1% on diagnosis, and hybrid search better than dense in every configuration [18]. Under 8,000 retrieved tokens matched long-context performance on real notes [13].

**Match, beat or adapt?** Match. The Uganda ART extract is small enough (about 32,000 tokens, per `RAG-OPTIONS.md`) to pass two to six whole sections per call on our 65k context. This is cheap and has the biggest single effect size in the literature.

### 3.5 Hybrid retrieval with a measured gold set [19][17][47]

**What they built.** The NICE system [19] used hybrid embedding retrieval over 10,195 chunks from 300 guidelines and tested retrieval on 7,901 queries before testing answers. The German study [17] traced 80% of wrong answers back to retrieval and found BM25 beat a strong embedding model on guideline text. PubHealthBench [47] (preprint) found hybrid search improved recall and ranking on government health guidance.

**Numbers.** Recall@10 99.1%, MRR 0.814, faithfulness 99.5% [19]. BM25 82.0% vs bge-m3 78.4% [17].

**Match, beat or adapt?** Match. Our corpus is a few thousand chunks, not ten thousand. The same evaluation discipline (retrieval scored first, on a gold set) is what `RAG-OPTIONS.md` section 3 already proposes.

---

## 4. Method-by-method evidence

**Overall effect of RAG.** A meta-analysis of 20 studies found RAG raised the odds of a correct answer 1.35 times [34]. Gains were largest for weaker open-weight models [35][91]; after RAG, open models such as Mistral Large 2 matched GPT-4o on cardiology questions [91]. RAG did worse on case-based than on knowledge questions in neurology [36]. In infectious diseases, retrieval raised specificity from 35% to 75%, yet 90% of studies reported safety problems [84]. Only 29.9% of 157 medical RAG studies scored retrieval on its own, and 10.8% tested in real workflows [94].

### 4.1 Hybrid search (keyword + embedding)
Mostly positive. Hybrid beat dense-only in sleep medicine (every configuration) [18], on BioASQ (faithfulness +50%, context recall +85% over dense) [44], on UK public-health guidance [47] (preprint), and on 250 de-identified patient vignettes (best precision@5 ≥ 0.68 with BM25 + dense + reranker) [43]. On German guidelines, plain BM25 beat a strong embedding model [17]. **Conflict:** a 40-configuration study on exam questions found plain dense retrieval with query rewriting and reranking best, and simpler dense set-ups nearly as good at lower cost [46] (preprint). That test used textbook passages and exam questions, not guidelines.

### 4.2 Rerankers
Helpful for retrieval, smaller effect on answers. On 1,000 questions over real longitudinal notes, a MedCPT reranker raised Hit@10 from 46.6% to 60.6%, but answer correctness only from 44.8% to 48.6% [45] (preprint). Reranking was part of the best configuration in [43] and [46]. MedCPT itself (a retriever and reranker trained on 255 million PubMed clicks) set the state of the art on biomedical search [52], but on literature, not guidelines.

### 4.3 Structure-aware chunking
Positive in clinical tests, but one large study disagrees. Chunking along topic boundaries raised answer accuracy from 50% to 87% and retrieval F1 from 0.24 to 0.64 on 30 surgical questions [24]. Table-of-contents-aligned chunks helped in sleep medicine [18]. **Conflict:** across 288 conditions on three clinical corpora, the choice of chunking explained almost none of the variation in retrieval quality (η² = 0.002), while the embedding model explained 40.8% [48]. That study used short clinical notes and case reports, where structure matters less than in a long guideline. For us, heading-based sections are mainly about keeping a rule and its heading together, which [24] supports.

### 4.4 Query rewriting and decomposition
Strong on our kind of problem, with a precision cost for HyDE. Restructuring clinical questions with PICO-style templates and repeated refinement raised accuracy from 50% to 87% and recall from 0.39 to 1.00 [23]. Writing a fake answer and searching with it (HyDE) raised faithfulness 14% but cut context precision 52% [44]. The key finding for us is R2MED: when the query is a patient case and the evidence is about an inferred problem, even the best retrievers score only 31.4 nDCG@10, rising to 41.4 when a reasoning model first works out what to look for [54]. A patient note does not look like the guideline text it needs. So generate short, targeted queries ("tenofovir renal monitoring creatinine clearance") from a structured summary of the visit; do not embed the notes.

### 4.5 Agentic and iterative retrieval
Small gains, high cost, mixed reliability. i-MedRAG (the model asks follow-up questions over several rounds) beat one-shot RAG on complex exam vignettes, reaching 69.7% on MedQA with GPT-3.5 [37]. A multi-round agentic method added 6.8 points on average across 7 benchmarks [38] (preprint). In the antibiotic study, multi-stage added 3 points (81% to 84%) [8]. On ACL-injury questions the best agent-plus-RAG set-up scored 95% against 94% for the best RAG-only set-up [42]. **Against:** a LangGraph "agentic Self-RAG" on 30 expert-verified clinical cases improved precision 12.9% on simple queries but cut recall 10.3% on multi-step ones and ran 5.2 times slower; its document grader wrongly rejected relevant passages that lacked exact keywords [39]. Self-correction by re-prompting did not consistently improve medical QA [41]. HemaGuide found routing by case type mattered and no single component was enough [30].

### 4.6 Corrective and self-reflective RAG
Moderate. Self-BioRAG, trained to judge its own evidence, gained 7.2% on medical QA [40]. A self-reflective pipeline had the lowest hallucination rate (5.8%) among 12 RAG variants on patient vignettes [43]. A verification-heavy agent had the lowest missed-contraindication rate (0.04) but more unsupported claims (21.1%) than a simpler structured approach (8.4%) [28] (preprint). These need training data or careful graders; a zero-shot grader is the weak point [39].

### 4.7 GraphRAG and knowledge graphs
No gain for guideline correctness in the closest test. In chronic kidney disease, GraphRAG matched plain RAG (75.6% vs 76.6%) and produced longer, less clear answers [14]. On post-operative questions, GraphRAG 96.8% vs RAG 94.8% (overlapping confidence intervals) [58]. A graph built only from ophthalmology guidelines outperformed both plain models and standard RAG, with hallucinations at 3.3% vs 30% at baseline [57]. Large general benchmarks find GraphRAG often loses to plain RAG on many tasks [55][56] and that agentic search can stand in for an explicit graph [59] (preprint).

### 4.8 Long context vs retrieval
Both work if the text is clean. Whole, well-formatted guideline in context gave 99% accuracy [12]. Retrieval of under 8,000 tokens matched long context on real notes [13]. The "lost in the middle" problem (models miss facts in the middle of long prompts) was confirmed in medical RAG, and a split-then-summarise method (BriefContext) reduced it [60]. For our 32,000-token guideline, passing a few whole sections is the middle ground.

### 4.9 Fine-tuning vs RAG
RAG first; fine-tuning for narrow, repeated judgements. RAG beat unsupervised fine-tuning for adding knowledge, both old and new [61]. RAG and fine-tuning + RAG beat fine-tuning alone across five small open models [62]. In post-operative support: fine-tuning 92.7%, RAG 91.3%, both 97.3% [63]. **Conflict:** at 4B parameters on exam questions, a medically fine-tuned model gained 6.8 points and RAG gave nothing [64] (preprint). For guideline-adherence auditing on real records, prompting failed (F1 < 0.40) and fine-tuning fixed it (F1 ≥ 0.90) [65], but those were 7 to 9B models. Medically fine-tuned models generally did not beat general models of the same size [66][15]. Fine-tuning needs labelled data we do not have yet; revisit once the clinician-labelled set grows.

### 4.10 Domain-specific embeddings
Model choice matters a lot; "medical" in the name does not. The embedding model explained 40.8% of retrieval variance across clinical corpora [48]. A small general model (BGE) beat medical-specific embedders on real EHR retrieval [49]. Generalist embedders beat specialised ones on short clinical search [50] (preprint). Larger embedders (over 7B) did best on long texts [51]. Fine-tuning an embedder on local data doubled mean average precision (0.27 vs 0.14 for multilingual-e5-large) [53]. MedCPT stays strong for biomedical literature [52][22]. Test two or three on our own gold set; do not pick by label.

### 4.11 Citation and claim verification
This is the weakest link in published systems. 50% to 90% of LLM answers were not fully supported by the sources they cited; even GPT-4o with web search left about 30% of statements unsupported [67]. In RAG over PubMed, only 27% to 41% of sentence-level citations were supported, and giving the model the perfect documents did not fix citation faithfulness [68]. Splitting answers into single facts and checking each against guidelines improved answers by up to 50% and caught 80% of hallucinations [69]. A new failure mode matters for HIV drugs: "deceptive grounding", where real evidence about drug Y is cited for drug X, ran 8% to 87% under stress and 7.8% in a deployed system; a check that the cited passage names the queried drug caught it with 97% precision [70] (preprint). TDF vs TAF and DTG vs EFV are exactly this risk. A multi-pass retrieve-then-cite method improved citation precision and recall in medical QA [71]. A source-attributing urology bot raised verifiable sources from 35% to 84% in a randomized clinician evaluation [89].

### 4.12 Detecting what is missing (gaps in the plan)
Directly relevant and under-studied. LLM judges can spot wrong content but are close to chance at spotting omissions (paired discrimination 0.50 to 0.63); restructuring the task as "list the required facts, then check each" recovered usable detection [29] (preprint). Diagnostic outputs omitted relevant guidelines up to 97% of the time for one model, and guideline citation varied with the patient's stated location [72]. This argues for a checklist of required actions per patient state (from the rule table), checked one item at a time, rather than "review this plan for gaps".

### 4.13 Consistency between runs
Our inconsistency is a known, measured problem. The same model gave different management choices across five runs of identical inpatient vignettes [73]. Antibiotic recommendations varied widely over 100 repeats per scenario [75]. Tightly constrained outputs (fixed labels) were highly reproducible (κ 0.94 to 1.00) [74]. Structured step-by-step prompts raised guideline adherence from 83% to 100% and removed unsafe advice in stroke vignettes [76] (preprint). Constrain the output format, lower the temperature, and run repeats in evaluation.

### 4.14 Alert design and alert fatigue
Classic decision-support alerts are overridden 46% to 96% of the time [87]; one drug-interaction system had 88.2% of severe alerts overridden [86]. LLMs catch most known interactions (95% to 99% of interaction cases in pharmacovigilance reports [93]) but flag far more than reference databases (Gemini 1,556 and ChatGPT 439 vs 204 in the reference set), with low precision [95]. Interaction design and role tailoring reduce fatigue [96]. Left unchecked, LLM medication plans can be dangerous: ICU clinicians found life-threatening recommendations in 16% to 57% of LLM-written regimens [83]. A meta-analysis of human + LLM teams found gains were real but uncertain, with factual error rates of 26% to 36% in documentation tasks [85]. Penda's "only when needed" design is the deployed answer [1][4].

---

## 5. Datasets and benchmarks we could test on

Access notes come from the abstracts; "check" means the abstract did not state the licence or how to get the data.

| Name | Where | Access / licence | What it contains | Fit to our task |
|---|---|---|---|---|
| HIVMedQA [15] | Communications Medicine 2026 | Check the paper's data statement | Clinician-curated open-ended HIV questions: knowledge, reasoning, complex vignettes, bias-modified versions; judge rubric | **High.** Only HIV-specific set found. Use the vignettes and the judge rubric |
| Kenyan primary care vignettes [16] | BMJ Digital Health & AI 2026 | Check | 5,107 locally written scenarios (507 evaluated), 12 nursing competency areas, 11-domain rubric | **High** for setting and rubric, not HIV-specific |
| NHS medication-safety failure vignettes [6] | arXiv 2025 (preprint) | Released with the paper (45 vignettes) | Cases covering every failure the system made on real records | **High** for medication-safety alerts and failure modes |
| Medication-error scenarios [5] | Cell Reports Medicine 2025 | Check the supplement | 91 error scenarios in 40 vignettes, 16 specialties | **Medium-high** for toxicity and interaction alerts |
| AMEGA [78] | npj Digital Medicine 2024 | Code public (per abstract) | 20 scenarios, 135 questions, 1,337 weighted scoring items on guideline adherence | **Medium.** Good scoring method; not HIV |
| NICE silver-standard set [80] | GitHub `julia-ive/guidelines_qa` | Public (per abstract) | Guideline-derived patient scenarios and questions, clinician-checked | **Medium.** Template for building our own Uganda set |
| MIMIC-CDM [77] | Nature Medicine 2024 | Built on MIMIC, so PhysioNet credentialed access is likely; check | 2,400 real cases, 4 abdominal conditions, simulated workflow | **Low-medium.** Real records, wrong disease area |
| MIRAGE / MedRAG toolkit [22] | Findings of ACL 2024 | Public toolkit | 7,663 questions from 5 medical QA sets; retriever comparisons | **Low-medium.** Sanity check for a retriever swap |
| R2MED [54] | EMNLP 2026 | Data released (per abstract) | 876 queries where patient cases must find evidence by reasoning | **Medium.** Tests case-to-evidence retrieval, our hardest step |
| PubHealthBench (RAG version) [47] | arXiv 2026 (preprint) | Check | 7,929 questions from UK government health guidance; retrieval and free-text rubric | **Medium.** Closest public test of retrieval over official guidance |
| MedGUIDE [79] | arXiv 2025 (preprint) | Check | 7,747 questions from 55 NCCN decision trees | **Low-medium.** Decision-tree following, oncology |
| RxBench [81] | arXiv 2025 (preprint) | Check | 2,259 pharmacist-reviewed items on 14 prescription error types | **Medium** for prescribing-error alerts |
| HealthBench Professional [82] | arXiv 2026 (preprint) | Open benchmark (per abstract) | Real clinician chats with rubrics | **Low-medium.** General clinical use |
| SourceCheckup data [67] | Nature Communications 2025 | Check | 800 questions, 58,000 statement-source pairs | **Medium** for testing a citation checker |
| hypMOOVE-PHC (added during spot-check) | [medRxiv 2026 protocol, preprint](https://consensus.app/papers/details/w:7cf9e7e7-9d4a-44f8-9509-ae251b109a4d/?utm_source=claude_desktop) | Not out yet; the protocol says de-identified benchmark data will be released under FAIR principles | 200 to 250 clinician-written vignettes per country (Kenya, Malawi, Tanzania) with human benchmark care plans | **High** for setting once released; worth watching |

The strongest test set will still be our own: the 7 patients in `Data/` plus 20 to 40 clinician-labelled visits, each with gold guideline sections and expected alerts.

---

## 6. Gaps: where this project could be first

1. **HIV guideline RAG on patient visits.** No published study retrieves from HIV treatment guidelines to audit real or realistic patient visits. HIVMedQA has no retrieval [15]. SmartHIVCare, a bilingual sub-Saharan African chatbot, supports patient education and adherence, not clinician decision support [88]. LLM causal reasoning about ART interactions was only partly consistent with experts and cited content it could not access [92].
2. **Several guidelines that disagree.** No study handles national vs WHO vs regional guidelines for one patient. Guideline citation already varies with patient location [72]. Routing to the patient's own country first, and showing when sources differ, is untested.
3. **Omissions in the clinician's plan.** Detecting what is missing is the weakest skill of LLM judges [29], and no clinical study tests "what did this plan leave out?" against a guideline checklist.
4. **Monitoring schedules over time.** Closest work measures one type of monitoring in ADHD notes [31]. Nobody has tested "viral load is overdue" or "creatinine not checked since starting TDF" with an LLM.
5. **Drug-name confusion in ART.** Deceptive grounding is untested on look-alike ARV names [70].
6. **Open 70B model on one GPU in Africa, with retrieval measured.** Local deployment has been tested in the UK (20B) [8] and radiology (11B) [90]; the Kenyan studies mainly used commercial cloud models [1][16].
7. **Alert design that reduces harmful adoption.** Clinicians accepted harmful advice at a high rate [3]. No study tests whether per-alert citations or confidence labels change that.

Any one of these, measured on a small clinician-labelled set, would be new.

---

## How this was researched

- **Consensus:** 20 searches, one at a time, page sizes 25 to 40, no filters. About 480 unique papers returned; 96 cited here. No sign-up or usage messages appeared.
- Abstracts only. Details marked "from our reading of the full preprint" in section 3.1 go beyond the abstract and should be verified.
- Access and licence notes in section 5 come from the abstracts; "check" means unknown.
- This review extends `RAG-OPTIONS.md` (same folder), which covers the basic technique history and the code-level problems; sources cited there (Self-RAG, CRAG, contextual retrieval, MedGraphRAG and others) are not repeated unless new numbers were found.

---

## 7. Sources

[1] [AI-based Clinical Decision Support for Primary Care: A Real-World Study](https://consensus.app/papers/details/w:7f687660-8715-4d1c-a0ef-d479ea44fc03/?utm_source=claude_desktop) (Robert Korom et al., 2025, arXiv (Cornell University) (preprint), 78 citations)

[2] [Generative AI-enabled clinical decision support system in primary care: a pragmatic, cluster-randomized trial](https://consensus.app/papers/details/w:ddc914b2-7374-4d9a-9f16-b797c37e8ff6/?utm_source=claude_desktop) (Ambrose Agweyu et al., 2026, Nature Medicine, 31 citations)

[3] [Safety of a large language model-based clinical decision support system in African primary healthcare](https://consensus.app/papers/details/w:c04a8e5a-f753-4754-8db3-95a935395ba4/?utm_source=claude_desktop) (Ambrose Agweyu et al., 2026, Nature Health, 32 citations)

[4] [Mixed-methods evaluation of clinician experiences and adoption patterns of an EHR-integrated generative AI-based clinical decision support uptake by clinicians in Kenya](https://consensus.app/papers/details/w:44ec8880-785f-4a22-a5c1-a8ea30d486f0/?utm_source=claude_desktop) (Christopher O. Obong’o et al., 2026, BMJ Digital Health & AI, 6 citations)

[5] [Large language model as clinical decision support system augments medication safety in 16 clinical specialties](https://consensus.app/papers/details/w:2d66af1a-1744-4691-a865-af9892fd7993/?utm_source=claude_desktop) (Jasmine Chiat Ling Ong et al., 2025, Cell Reports Medicine, 113 citations)

[6] [A Real-World Evaluation of LLM Medication Safety Reviews in NHS Primary Care](https://consensus.app/papers/details/w:a724ee80-93e2-4388-84a2-9f70e9f11b38/?utm_source=claude_desktop) (Oliver Normand et al., 2025, arXiv (Cornell University) (preprint), 9 citations)

[7] [An audit-ready EHR foundation model for order-time medication-safety auditing across health systems](https://consensus.app/papers/details/w:b4590ac5-08d2-4d92-8ff9-eb325f41b7cc/?utm_source=claude_desktop) (Shuang Cao et al., 2026, npj Digital Medicine, 0 citations)

[8] [An antibiotic chatbot: Evaluation of a retrieval-augmented generation approach for providing guideline-based antimicrobial advice](https://consensus.app/papers/details/w:347d1c55-c1f6-4a52-ab16-0ae7624a08aa/?utm_source=claude_desktop) (David W. Eyre et al., 2026, Journal of Infection, 3 citations)

[9] [Performance of Retrieval-Augmented Generation Large Language Models in Guideline-Concordant Prostate-Specific Antigen Testing: Comparative Study With Junior Clinicians](https://consensus.app/papers/details/w:f48c4c1a-974e-46f3-bdb1-367f06dae5ca/?utm_source=claude_desktop) (Joshua Yi Min Tung et al., 2025, Journal of Medical Internet Research, 19 citations)

[10] [Evaluating Adherence to Canadian Radiology Guidelines for Incidental Hepatobiliary Findings Using RAG-Enabled LLMs](https://consensus.app/papers/details/w:c04002a4-e8a2-4422-933f-154912cd4468/?utm_source=claude_desktop) (Nicholas T. Dietrich et al., 2025, Canadian Association of Radiologists Journal, 23 citations)

[11] [Retrieval augmented generation for 10 large language models and its generalizability in assessing medical fitness](https://consensus.app/papers/details/w:d6857f7c-c63a-4c34-a44f-6203a24e278a/?utm_source=claude_desktop) (Yu He Ke et al., 2025, npj Digital Medicine, 241 citations)

[12] [Optimization of hepatological clinical guidelines interpretation by large language models: a retrieval augmented generation-based framework](https://consensus.app/papers/details/w:0b9725f2-819f-4799-9f1b-169ff0353f76/?utm_source=claude_desktop) (Simone Kresevic et al., 2024, npj Digital Medicine, 275 citations)

[13] [Evaluating retrieval-augmented generation versus long-context input for clinical reasoning over electronic health records](https://consensus.app/papers/details/w:3c8c27f6-8548-4ed2-b443-988d5915ac52/?utm_source=claude_desktop) (Skatje Myers et al., 2026, Journal of the American Medical Informatics Association, 10 citations)

[14] [Development and evaluation of Retrieval-Augmented Generation (RAG) and GraphRAG for guideline-based clinical decision support in chronic kidney disease](https://consensus.app/papers/details/w:23ff9462-5dfb-49e4-a72e-5d010c4a80c2/?utm_source=claude_desktop) (M. Berkan Sesen et al., 2026, BMJ Digital Health & AI, 4 citations)

[15] [Benchmarking large language models for HIV medical decision support](https://consensus.app/papers/details/w:07263052-f5fa-4274-92fa-69d8d93624d3/?utm_source=claude_desktop) (Gonzalo Cardenal et al., 2026, Communications Medicine, 2 citations)

[16] [Benchmarking large language models and clinicians using locally generated primary healthcare vignettes in Kenya](https://consensus.app/papers/details/w:cd0010bc-18b9-4f4b-8028-80d4a81473e4/?utm_source=claude_desktop) (Paul Mwaniki et al., 2026, BMJ Digital Health & AI, 5 citations)

[17] [Evaluating Retrieval Augmented Generation-enhanced Large Language Models for Question Answering On German Neurovascular Guidelines](https://consensus.app/papers/details/w:1b875737-9a3e-4261-9350-e0adfa0bbc7d/?utm_source=claude_desktop) (Marius Vach et al., 2025, Clinical Neuroradiology, 13 citations)

[18] [Optimizing Retrieval-Augmented Generation (RAG) in clinical medicine: methods and performance evaluation](https://consensus.app/papers/details/w:90d2e8ca-5ff9-490e-8ba5-b90917d286c4/?utm_source=claude_desktop) (Pengze Li et al., 2026, Journal of the American Medical Informatics Association, 4 citations)

[19] [Grounding Large Language Models in Clinical Evidence: A Retrieval-Augmented Generation System for Querying UK NICE Clinical Guidelines](https://consensus.app/papers/details/w:86dd9c79-810c-4674-ba0b-64fdf5cb125c/?utm_source=claude_desktop) (Lewis et al., 2025, arXiv (Cornell University) (preprint), 16 citations)

[20] [Evaluating large language models for evidence-based clinical question answering](https://consensus.app/papers/details/w:1737531a-c5dd-4367-b927-19b19a5df8e4/?utm_source=claude_desktop) (Can Wang et al., 2026, Patterns, 13 citations)

[21] [Rethinking Retrieval-Augmented Generation for Medicine: A Large-Scale, Systematic Expert Evaluation and Practical Insights](https://consensus.app/papers/details/w:738cfd47-5b29-4e83-aeaa-0e1d416e06ca/?utm_source=claude_desktop) (Hyunjae Kim et al., 2025, arXiv (Cornell University) (preprint), 34 citations)

[22] [Benchmarking Retrieval-Augmented Generation for Medicine](https://consensus.app/papers/details/w:0a7560d7-8d75-42ee-a901-86831c222780/?utm_source=claude_desktop) (Guangzhi Xiong et al., 2024, Findings of the Association for Computational Linguistics: ACL (Findings of ACL), 881 citations)

[23] [Enhancing Clinical Decision Support with Adaptive Iterative Self-Query Retrieval for Retrieval-Augmented Large Language Models](https://consensus.app/papers/details/w:ba95be14-037e-4b4f-8949-c438f4bfdc1c/?utm_source=claude_desktop) (Srinivasagam Prabha et al., 2025, Bioengineering, 14 citations)

[24] [Comparative Evaluation of Advanced Chunking for Retrieval-Augmented Generation in Large Language Models for Clinical Decision Support](https://consensus.app/papers/details/w:35efac0c-c4b8-44ef-9920-32660d8b071a/?utm_source=claude_desktop) (Cesar Abraham Gomez-Cabello et al., 2025, Bioengineering, 37 citations)

[25] [Benchmarking Large Language Models for Drug Combination Alerts: Achieving Expert-Level Reliability via Knowledge Grounding and Contextual Reasoning](https://consensus.app/papers/details/w:6601706d-a769-441a-88de-23c5391e5600/?utm_source=claude_desktop) (Huan Hu et al., 2026, Journal of Medicinal Chemistry, 5 citations)

[26] [CPGPrompt: translating clinical guidelines into large language model-executable decision support](https://consensus.app/papers/details/w:dff3fea7-3749-4c88-b87e-00ebe051455e/?utm_source=claude_desktop) (Ruiqi Deng et al., 2026, Journal of the American Medical Informatics Association, 20 citations)

[27] [A deterministic large language model (LLM) framework for safe, protocol-adherent clinical decision support: application in hemodialysis anemia management (AnemiaCare HDs)](https://consensus.app/papers/details/w:f008fcd9-e08d-4ea5-b87c-a20fce38aabf/?utm_source=claude_desktop) (Jose Arriola‐Montenegro et al., 2025, Frontiers in Artificial Intelligence, 6 citations)

[28] [Representation Before Retrieval: Structured Patient Artifacts Reduce Hallucination in Clinical AI Systems](https://consensus.app/papers/details/w:115c613f-7e94-41ae-8b6e-2ef54f2e96c9/?utm_source=claude_desktop) (Joe Scanlin et al., 2026, medRxiv (preprint), 4 citations)

[29] [LLM Judges Verify Presence, Not Absence: Omission Blindness in AI Clinical Notes and What Recovers It](https://consensus.app/papers/details/w:0a896736-21bc-4b26-90f1-38a40f412430/?utm_source=claude_desktop) (Sebastian Fox et al., 2026, arXiv (Cornell University) (preprint), 5 citations)

[30] [Clinical decision support in hematological malignancies using a case-grounded AI agent](https://consensus.app/papers/details/w:3e55299c-eab3-4b59-b9e9-30f651fb1164/?utm_source=claude_desktop) (Julian Zoller et al., 2026, Nature Medicine, 9 citations)

[31] [Applying Large Language Models to Assess Quality of Care: Monitoring ADHD Medication Side Effects](https://consensus.app/papers/details/w:7b542885-865e-441a-9a91-a10504e297f0/?utm_source=claude_desktop) (Yair Bannett et al., 2024, PEDIATRICS, 21 citations)

[32] [GPT-4 assistance for improvement of physician performance on patient care tasks: a randomized controlled trial](https://consensus.app/papers/details/w:747c819e-f786-4429-b686-28d73999232e/?utm_source=claude_desktop) (Ethan Goh et al., 2025, Nature Medicine, 276 citations)

[33] [Large language model diagnostic assistance for physicians in a lower-middle-income country: a randomized controlled trial](https://consensus.app/papers/details/w:3ab7521c-95f4-4e9a-b6ca-5fbcfde87ddc/?utm_source=claude_desktop) (Ihsan Ayyub Qazi et al., 2026, Nature Health, 36 citations)

[34] [Improving large language model applications in biomedicine with retrieval-augmented generation: a systematic review, meta-analysis, and clinical development guidelines](https://consensus.app/papers/details/w:c7f785f1-bd5d-4f22-867f-bd3d820eb22e/?utm_source=claude_desktop) (Siru Liu et al., 2025, Journal of the American Medical Informatics Association, 329 citations)

[35] [A Self-Controlled Benchmark of Retrieval-Augmented Generation for Large Language Models on Clinical Guideline Questions](https://consensus.app/papers/details/w:b0f38f30-e11b-4d4b-a9c1-df643e29c45b/?utm_source=claude_desktop) (Andreas Vollmer et al., 2026, Diagnostics, 2 citations)

[36] [Evaluating base and retrieval augmented LLMs with document or online support for evidence based neurology](https://consensus.app/papers/details/w:c04aa5ba-6370-48b7-8f07-6c85162d61d5/?utm_source=claude_desktop) (Lars Masanneck et al., 2025, npj Digital Medicine, 70 citations)

[37] [Improving Retrieval-Augmented Generation in Medicine with Iterative Follow-up Questions](https://consensus.app/papers/details/w:ba5e9da0-29c7-4632-bb6c-3508385d43cf/?utm_source=claude_desktop) (Guangzhi Xiong et al., 2024, Pacific Symposium on Biocomputing (PSB), 167 citations)

[38] [From Conflict to Consensus: Boosting Medical Reasoning via Multi-Round Agentic RAG](https://consensus.app/papers/details/w:220fbdb0-cf58-4470-9507-3dd0a1bc963e/?utm_source=claude_desktop) (Wenhao Wu et al., 2026, arXiv (Cornell University) (preprint), 11 citations)

[39] [Agentic Self-RAG: An Ablation Study for Zero-Shot Biomedical Question Answering](https://consensus.app/papers/details/w:ff359892-7a18-4a9f-a800-2c99ae7fae7d/?utm_source=claude_desktop) (Rendi Prayata Wibawa et al., 2026, IEEE International Conference on Industry 4.0, Artificial Intelligence, and Communications Technology (IAICT), 0 citations)

[40] [Improving medical reasoning through retrieval and self-reflection with retrieval-augmented large language models](https://consensus.app/papers/details/w:c2b46556-403e-4027-bc5f-a526542a0e82/?utm_source=claude_desktop) (Minbyul Jeong et al., 2024, Bioinformatics, 246 citations)

[41] [Can Large Language Models Self-Correct in Medical Question Answering? An Exploratory Study](https://consensus.app/papers/details/w:8a995b3c-c115-4537-9fe2-1c78587781a3/?utm_source=claude_desktop) (Zaifu Zhan et al., 2026, IEEE International Conference on Healthcare Informatics (ICHI), 3 citations)

[42] [Custom Large Language Models Improve Accuracy: Comparing Retrieval Augmented Generation and Artificial Intelligence Agents to Noncustom Models for Evidence‐Based Medicine](https://consensus.app/papers/details/w:1fcd2dff-0fa0-4f9b-9032-02ecb5878f6a/?utm_source=claude_desktop) (Joshua J. Woo et al., 2024, Arthroscopy The Journal of Arthroscopic and Related Surgery, 76 citations)

[43] [Evaluating Retrieval-Augmented Generation Variants for Clinical Decision Support: Hallucination Mitigation and Secure On-Premises Deployment](https://consensus.app/papers/details/w:fd0e1697-84aa-4539-a891-4b16bac918bf/?utm_source=claude_desktop) (Krzysztof Wołk, 2025, Electronics, 26 citations)

[44] [BioRAG: A Systematic Ablation Study of Retrieval Strategies for Biomedical Question Answering](https://consensus.app/papers/details/w:3bbebca3-479f-4d8d-a3db-d559693d40a4/?utm_source=claude_desktop) (Krushil Bhojani et al., 2026, BioNLP 2026, 1 citations)

[45] [Evaluating Biomedical Reranking for LLM-Based Question Answering over Longitudinal Clinical Notes](https://consensus.app/papers/details/w:ffff9806-8391-4d4c-82dd-dd805141f12d/?utm_source=claude_desktop) (Maryam Shahbaz Ali et al., 2026, arXiv (Cornell University) (preprint), 0 citations)

[46] [A Systematic Study of Retrieval Pipeline Design for Retrieval-Augmented Medical Question Answering](https://consensus.app/papers/details/w:f70c02a4-c651-432e-ae99-c1edce0f2862/?utm_source=claude_desktop) (Nusrat Sultana et al., 2026, arXiv (Cornell University) (preprint), 0 citations)

[47] [Healthier LLMs: Retrieval-Augmented Generation for Public Health Question Answering](https://consensus.app/papers/details/w:8120e1e8-7878-4c64-a0d2-2f1eff0e53d8/?utm_source=claude_desktop) (Felix Feldman et al., 2026, arXiv (Cornell University) (preprint), 1 citations)

[48] [Clinical Context Variables Collectively Rival Model Choice in Embedding-Based Retrieval: Multi-Corpus Benchmark Study](https://consensus.app/papers/details/w:75965543-1c67-4443-941a-3f83cae1c397/?utm_source=claude_desktop) (Yngve Mikkelsen, 2026, JMIR Medical Informatics, 8 citations)

[49] [Lessons learned on information retrieval in electronic health records: a comparison of embedding models and pooling strategies](https://consensus.app/papers/details/w:2ecf6b1b-ea90-45f7-8e23-2fada83492a9/?utm_source=claude_desktop) (Skatje Myers et al., 2024, Journal of the American Medical Informatics Association, 32 citations)

[50] [Generalist embedding models are better at short-context clinical semantic search than specialized embedding models](https://consensus.app/papers/details/w:12b8e777-f1ea-4819-9431-61e821d6b6ac/?utm_source=claude_desktop) (Jean-Baptiste Excoffier et al., 2024, arXiv (Cornell University) (preprint), 29 citations)

[51] [A scalable framework for benchmark embedding models in semantic health-care tasks](https://consensus.app/papers/details/w:c0bcf228-2e89-42ec-9465-a45ba5f758d1/?utm_source=claude_desktop) (Shelly Soffer et al., 2025, Journal of the American Medical Informatics Association, 9 citations)

[52] [MedCPT: Contrastive Pre-trained Transformers with large-scale PubMed search logs for zero-shot biomedical information retrieval](https://consensus.app/papers/details/w:86e50026-5823-4bf5-93bc-aa2c511c313e/?utm_source=claude_desktop) (Qiao Jin et al., 2023, Bioinformatics, 425 citations)

[53] [Improving Retrieval Augmented Generation for Health Care by Fine-Tuning Clinical Embedding Models: Development and Evaluation Study](https://consensus.app/papers/details/w:a9b4c2e7-5e2d-42d4-9575-63af72a58f34/?utm_source=claude_desktop) (Kamyar Arzideh et al., 2026, Journal of Medical Internet Research, 11 citations)

[54] [R2MED: A Benchmark for Reasoning-Driven Medical Retrieval](https://consensus.app/papers/details/w:14a8d296-08f1-4497-b3ee-2ef7052bc1d4/?utm_source=claude_desktop) (Xiangxu Zhang et al., 2026, Conference on Empirical Methods in Natural Language Processing (EMNLP), 31 citations)

[55] [RAG vs. GraphRAG: A Systematic Evaluation and Key Insights](https://consensus.app/papers/details/w:be17f365-b633-4d04-a18c-24d745cb7733/?utm_source=claude_desktop) (Haoyu Han et al., 2026, ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD), 141 citations)

[56] [When to use Graphs in RAG: A Comprehensive Analysis for Graph Retrieval-Augmented Generation](https://consensus.app/papers/details/w:0c3063f6-1af4-4b2d-9680-2fadd21e73f9/?utm_source=claude_desktop) (Zhiyi Xiang et al., 2025, arXiv (Cornell University) (preprint), 133 citations)

[57] [EyeRAG: graph retrieval-augmented generation for safe and accurate clinical dialogue in ophthalmology](https://consensus.app/papers/details/w:96a263be-5ef6-42da-9389-7f7513a3c299/?utm_source=claude_desktop) (Kaikai Zhao et al., 2026, npj Digital Medicine, 3 citations)

[58] [Graph-Enhanced Retrieval-Augmented Generation for Postoperative Patient Question Answering: A Comparative Evaluation of Knowledge Graph, Retrieval-Augmented Generation, and Hybrid GraphRAG Approaches](https://consensus.app/papers/details/w:3bdefca5-3215-41e2-8685-a6269721a389/?utm_source=claude_desktop) (Srinivasagam Prabha et al., 2026, Bioengineering, 0 citations)

[59] [Do We Still Need GraphRAG? Benchmarking RAG and GraphRAG for Agentic Search Systems](https://consensus.app/papers/details/w:6ef012a8-df5e-4092-aeb8-0a3ce64e5da3/?utm_source=claude_desktop) (Dongzhe Fan et al., 2026, arXiv (Cornell University) (preprint), 5 citations)

[60] [Leveraging long context in retrieval augmented language models for medical question answering](https://consensus.app/papers/details/w:b255499e-3df7-4a6e-84d8-88f210e57edf/?utm_source=claude_desktop) (Gongbo Zhang et al., 2025, npj Digital Medicine, 127 citations)

[61] [Fine-Tuning or Retrieval? Comparing Knowledge Injection in LLMs](https://consensus.app/papers/details/w:e15d32c6-1ae2-4c6c-91f9-91b7b3f7b4e0/?utm_source=claude_desktop) (Oded Ovadia et al., 2024, Conference on Empirical Methods in Natural Language Processing (EMNLP), 441 citations)

[62] [Medical LLMs: Fine-Tuning vs. Retrieval-Augmented Generation](https://consensus.app/papers/details/w:712451ed-7511-4788-9124-92de963727c1/?utm_source=claude_desktop) (Bhagyajit Pingua et al., 2025, Bioengineering, 52 citations)

[63] [Fine-Tuning, Retrieval-Augmented Generation, and Hybrid Large Language Models for Postoperative Decision Support: Comparative Analysis](https://consensus.app/papers/details/w:066e67e1-a093-4b83-b21e-a2c13beec3ff/?utm_source=claude_desktop) (Srinivasagam Prabha et al., 2026, Journal of Medical Internet Research, 1 citations)

[64] [Domain Fine-Tuning vs. Retrieval-Augmented Generation for Medical Multiple-Choice Question Answering: A Controlled Comparison at the 4B-Parameter Scale](https://consensus.app/papers/details/w:0d96ea83-199c-40cd-83d6-e65c7ba26bec/?utm_source=claude_desktop) (Avi-ad Avraam Buskila, 2026, arXiv (Cornell University) (preprint), 2 citations)

[65] [Exploring the potential of large language models for assessing medication adherence to the ESC heart failure guidelines](https://consensus.app/papers/details/w:b5f22c5d-40b7-429b-a0e2-584e4d499dc7/?utm_source=claude_desktop) (Noman Dormosh et al., 2025, JAMIA Open, 1 citations)

[66] [Evaluating the effectiveness of biomedical fine-tuning for large language models on clinical tasks](https://consensus.app/papers/details/w:8fd6c9eb-f0ca-4b60-9cfd-2f9f90afc765/?utm_source=claude_desktop) (Felix J. Dorfner et al., 2025, Journal of the American Medical Informatics Association, 112 citations)

[67] [An automated framework for assessing how well LLMs cite relevant medical references](https://consensus.app/papers/details/w:e740733b-b610-45ab-acf4-bc296381a967/?utm_source=claude_desktop) (Kevin Wu et al., 2025, Nature Communications, 255 citations)

[68] [VERICITE: Evaluating Sentence-Level Citation Faithfulness in Retrieval-Augmented Medical Question Answering](https://consensus.app/papers/details/w:c6d71123-8a27-49a5-8edf-b5a1dbb5e4df/?utm_source=claude_desktop) (Yixian Ma et al., 2026, BioNLP 2026, 3 citations)

[69] [Improving Reliability and Explainability of Medical Question Answering Through Atomic Fact-Checking in Retrieval-Augmented Large Language Models: Creation and Validation Study](https://consensus.app/papers/details/w:f9dbf862-8bda-43b1-9bc7-62dd9dc9b5f4/?utm_source=claude_desktop) (Juraj Vladika et al., 2026, Journal of Medical Internet Research, 10 citations)

[70] [Deceptive Grounding: Entity Attribution Failure in Clinical Retrieval-Augmented Generation](https://consensus.app/papers/details/w:50528a1b-a242-4f84-92b2-167486e69b84/?utm_source=claude_desktop) (Cedric Caruzzo et al., 2026, arXiv (Cornell University) (preprint), 0 citations)

[71] [MedCite: Can Language Models Generate Verifiable Text for Medicine?](https://consensus.app/papers/details/w:cfda40b0-d0db-47e1-b3e7-a1e1733e55b9/?utm_source=claude_desktop) (Xiao Wang et al., 2025, Findings of the Association for Computational Linguistics: ACL (Findings of ACL), 23 citations)

[72] [Omission and hallucination prevalence of clinical guidelines in diagnostic large language model outputs](https://consensus.app/papers/details/w:bdfb66c3-1a87-4845-bcbe-7c9be5787770/?utm_source=claude_desktop) (Robin van Kessel et al., 2026, BMJ Health & Care Informatics, 20 citations)

[73] [Variation in Large Language Model Recommendations in Challenging Inpatient Management Scenarios](https://consensus.app/papers/details/w:e24e8aa0-79e9-44e6-bed3-60674e4cdaf6/?utm_source=claude_desktop) (Susan N. Landon et al., 2025, Journal of General Internal Medicine, 29 citations)

[74] [Is one run enough? Reproducibility of flagship large language models across temperature and reasoning settings in biomedical text processing](https://consensus.app/papers/details/w:ff7ce64a-0ed6-4705-8415-1ba52dcab698/?utm_source=claude_desktop) (Paul Y. Windisch et al., 2026, Journal of the American Medical Informatics Association, 9 citations)

[75] [Reproducibility of AI-generated antibiotic recommendations in standardised clinical scenarios: A proof-of-concept experimental study](https://consensus.app/papers/details/w:7300158e-1d4f-40c0-9f8e-14efb6ce5851/?utm_source=claude_desktop) (Andrea DE VITO et al., 2026, International Journal of Antimicrobial Agents, 4 citations)

[76] [Prompting is All You Need: How to Make LLMs More Helpful for Clinical Decision Support](https://consensus.app/papers/details/w:ce0d2fce-01b6-42e7-9dfb-60fa82dbbd89/?utm_source=claude_desktop) (Braydon Dymm et al., 2026, medRxiv (preprint), 4 citations)

[77] [Evaluation and mitigation of the limitations of large language models in clinical decision-making](https://consensus.app/papers/details/w:eb873c63-4386-4474-8ba1-63201ee27e68/?utm_source=claude_desktop) (Paul Hager et al., 2024, Nature Medicine, 1298 citations)

[78] [Autonomous medical evaluation for guideline adherence of large language models](https://consensus.app/papers/details/w:f99a9512-850b-443a-8713-682ab230411f/?utm_source=claude_desktop) (Dennis Fast et al., 2024, npj Digital Medicine, 93 citations)

[79] [MedGUIDE: Benchmarking Clinical Decision-Making in Large Language Models](https://consensus.app/papers/details/w:528b829a-4306-4cdb-b77e-37f7d618dec2/?utm_source=claude_desktop) (Xiaomin Li et al., 2025, arXiv (Cornell University) (preprint), 30 citations)

[80] [Building a Silver-Standard Dataset from NICE Guidelines for Clinical LLMs](https://consensus.app/papers/details/w:67d947bf-6e63-4f6e-baa9-18e44f103c19/?utm_source=claude_desktop) (Qing Ding et al., 2026, Studies in health technology and informatics, 2 citations)

[81] [Human-Level and Beyond: Benchmarking Large Language Models Against Clinical Pharmacists in Prescription Review](https://consensus.app/papers/details/w:738eb129-2a13-47b5-bfa1-f3a101767905/?utm_source=claude_desktop) (Yan Yang et al., 2025, arXiv (Cornell University) (preprint), 2 citations)

[82] [HealthBench Professional: Evaluating Large Language Models on Real Clinician Chats](https://consensus.app/papers/details/w:88958026-2d74-486e-8d65-94eb0f7e3cdc/?utm_source=claude_desktop) (Rebecca Soskin Hicks et al., 2026, arXiv (Cornell University) (preprint), 44 citations)

[83] [Large language models management of complex medication regimens: a case-based evaluation](https://consensus.app/papers/details/w:7480bfc9-189e-4b7a-b65f-ad25bf062d1b/?utm_source=claude_desktop) (Aaron M. Chase et al., 2025, Frontiers in Pharmacology, 21 citations)

[84] [Large Language Models in Infectious Diseases: A Systemic Review](https://consensus.app/papers/details/w:82e311a1-f521-4b17-9554-4b04e8bb6c5f/?utm_source=claude_desktop) (Alon Gorenshtein et al., 2026, Research Square (preprint), 2 citations)

[85] [Human–large language model collaboration in clinical medicine: a systematic review and meta-analysis](https://consensus.app/papers/details/w:8a22c1c6-9fa8-46a3-b618-2f8038193914/?utm_source=claude_desktop) (Guoyong Wang et al., 2026, npj Digital Medicine, 65 citations)

[86] [Overall performance of a drug–drug interaction clinical decision support system: quantitative evaluation and end-user survey](https://consensus.app/papers/details/w:3fd455e1-f7d4-46c7-967a-21bf0544903e/?utm_source=claude_desktop) (Greet Van De Sijpe et al., 2022, BMC Medical Informatics and Decision Making, 68 citations)

[87] [Appropriateness of Overridden Alerts in Computerized Physician Order Entry: Systematic Review](https://consensus.app/papers/details/w:a907c94e-d3bf-4693-9b08-d7b6a7905aaf/?utm_source=claude_desktop) (Tahmina Nasrin Poly et al., 2020, JMIR Medical Informatics, 138 citations)

[88] [SmartHIVCare: A Bilingual Retrieval-Augmented Multimodal Chatbot for ART Education and Adherence Support in Low-Resource Settings](https://consensus.app/papers/details/w:4f8cf599-c3cc-4ebd-b6ee-f90f755d5b77/?utm_source=claude_desktop) (Belayneh Endalamaw Dejene et al., 2026, Technologies, 0 citations)

[89] [Enhancing clinicians’ trust in large language models via transparent source attribution: A randomized controlled evaluation in uro-oncology](https://consensus.app/papers/details/w:45a431c0-43b9-4592-bd90-931f9e3f6cf2/?utm_source=claude_desktop) (Nicolas Carl et al., 2025, European Journal of Cancer, 15 citations)

[90] [Retrieval-augmented generation elevates local LLM quality in radiology contrast media consultation](https://consensus.app/papers/details/w:62a2ce55-3972-4037-92ea-2fa654705d0c/?utm_source=claude_desktop) (Akihiko Wada et al., 2025, npj Digital Medicine, 92 citations)

[91] [Cardiology knowledge assessment of retrieval-augmented open versus proprietary large language models](https://consensus.app/papers/details/w:f0e12095-a186-405d-bbd4-c63a52c2a1cb/?utm_source=claude_desktop) (Constantine Tarabanis et al., 2026, PLOS Digital Health, 6 citations)

[92] [Consistency in causal reasoning for large language models in scenarios of HIV antiretroviral treatment, drug interactions, and side effects](https://consensus.app/papers/details/w:fe554bca-22ff-48e1-ad4a-bb119fd3ee98/?utm_source=claude_desktop) (Mattia Prosperi et al., 2026, npj Digital Medicine, 0 citations)

[93] [Can large language models detect drug–drug interactions leading to adverse drug reactions?](https://consensus.app/papers/details/w:8a6a6d14-7ae8-4da5-8100-c25766b7dfb5/?utm_source=claude_desktop) (Justine Sicard et al., 2025, Therapeutic Advances in Drug Safety, 38 citations)

[94] [Evaluation Methods for Inference-Time Retrieval-Augmented and Graph Retrieval-Augmented Large Language Models in Health Care: Scoping Review](https://consensus.app/papers/details/w:b0f1ca9d-fcce-45bc-8aa2-61307d629829/?utm_source=claude_desktop) (Yuhan Zhao et al., 2026, Journal of Medical Internet Research, 2 citations)

[95] [Comparative evaluation of artificial intelligence platforms and drug interaction screening databases using real-world patient data](https://consensus.app/papers/details/w:88e345be-c4c3-4617-bbef-9dd9ee23ee9d/?utm_source=claude_desktop) (Bálint Márk Domián et al., 2025, Exploratory Research in Clinical and Social Pharmacy, 12 citations)

[96] [Medication safety alert fatigue may be reduced via interaction design and clinical role tailoring: a systematic review](https://consensus.app/papers/details/w:2817fc43-d796-4854-a825-a0139d453401/?utm_source=claude_desktop) (Mustafa Hussain et al., 2019, Journal of the American Medical Informatics Association, 160 citations)

