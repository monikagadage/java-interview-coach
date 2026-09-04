# Question sources

`questions_db.json` is built by `python -m qbank.build` from three inputs:

## 1. Curated questions (`qbank/curated/*.txt`)

~1,700 questions hand-written for this project, one per line, filed under
the topic in the file name (`OOP.txt`, `OOP.2.txt`, … → topic `OOP`). These
give every topic solid baseline coverage and serve as a checked-in sample
of what `--expand` produces at larger scale.

## 2. Public GitHub lists (scraped, normalized, re-classified)

Fetched at build time and cached under `qbank/.cache/` (gitignored). Only
the question *text* is used; each question is re-normalized, routed to a
canonical topic, and de-duplicated against everything else. Rows a source
labels with a topic we don't recognize, or can't be classified by keyword,
are dropped as noise.

| Source | What we take | License |
|---|---|---|
| [teamlead/java-interview-questions](https://github.com/teamlead/java-interview-questions) | `\| question \| category \|` table rows | No license file — treated as unlicensed; used as a question *seed* only, heavily transformed, with attribution here. |
| [learning-zone/java-interview-questions](https://github.com/learning-zone/java-interview-questions) | `## Q. …` headings | No license file — same treatment. |
| [Devinterview-io/java-interview-questions](https://github.com/Devinterview-io/java-interview-questions) | `## N. …` numbered headings | No license file — same treatment. |
| [sudheerj/java-interview-questions](https://github.com/sudheerj/java-interview-questions) | table-of-contents question links | No license file — same treatment. |

If you fork this and care about redistribution, the safe move is to keep
only `qbank/curated/` + `--expand` output and drop the scraped sources
(remove entries from `qbank/sources.py`); the build still works.

## 3. LLM expansion (`python -m qbank.build --expand`, opt-in)

For each `(topic, subtopic)` in `qbank/taxonomy.py`, asks a model (Groq
`llama-3.3-70b` by default) for N questions, normalizes them, and dedupes
against the rest. Results are cached per subtopic under
`qbank/.cache/expand/` so a run resumes and re-runs are free. Needs
`GROQ_API_KEY`. This is what takes the bank from ~2.5k to 10k+.
