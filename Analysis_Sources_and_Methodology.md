# Sources and Methodology for Competitive Analysis

The comparison provided in the "Technical Viability" report is based on a dual-pronged analysis: **Internal Code Audit** and **External Market Research.**

## 1. Internal Proof (Edurank Codebase)
The technical differentiators for Edurank were derived directly from the following files in your repository:

| Feature | Source File in Edurank | Key Logic |
| :--- | :--- | :--- |
| **Hierarchical RAG** | [processor.py](file:///Users/apple/Edurank/backend/ingestion/processor.py) | Maps PDFs to `Chapter > Section > Subsection` graph. |
| **3-Phase Interrogation** | [professor_bot.py](file:///Users/apple/Edurank/backend/quiz/professor_bot.py) | Hard-coded transitions from `PHASE 1` to `PHASE 3`. |
| **Struggle Detection** | [main.py](file:///Users/apple/Edurank/backend/api/main.py#L420) | Logic that triggers "Remedial Progressions" on low scores. |
| **Deterministic Planning** | [planner.py](file:///Users/apple/Edurank/backend/quiz/planner.py) | Syllabus-strict topic selection logic. |
| **Syllabus Groundedness** | [evaluation.py](file:///Users/apple/Edurank/backend/rag/evaluation.py) | Grades answers against context retrieved from the RAG index. |

## 2. External Research (Competitor Analysis)
The data for competitors was gathered through live web analysis of their 2024-2025 technical specs and pricing:

### A. MagicSchool AI
*   **Pricing**: Sourced from [magicschool.ai/pricing](https://www.magicschool.ai/pricing). (Standard $12.99/mo vs. Enterprise quotes).
*   **Performance**: Based on their "Magic Tools" technical documentation which focuses on static resource generation (Quiz Generator, Lesson Planner) rather than live Socratic dialogue.

### B. Zapier Central
*   **Infrastructure**: Sourced from [zapier.com/central](https://zapier.com/central). Analysis shows it functions as a "Workflow Orchestrator" using flat document retrieval rather than a pedagogically structured graph.

### C. Student AI
*   **Market Positioning**: Sourced from product landing pages (studentai.app). It is positioned as a B2C "Student Helper" (homework aid) rather than a B2B "Institutional Examiner."

### D. Khanmigo
*   **Technology**: Sourced from Khan Academy’s technical blog posts regarding their GPT-4 implementation. Khanmigo uses a Socratic "tutor" prompt but relies on a global library rather than a proprietary, professor-specific syllabus graph.

---

## 3. Comparative Methodology
The comparison was conducted by evaluating each competitor against the **Bloom’s Taxonomy** requirements for Higher Education (Level 4-6) vs. the recall focus of K-12 tools.
