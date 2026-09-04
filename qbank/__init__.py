"""Question-bank build pipeline.

Turns a set of public sources + optional LLM expansion into
``questions_db.json`` (``{topic: [question, ...]}``), the corpus every
front-end retrieves from.

    python -m qbank.build              # scrape + normalize + dedup + classify
    python -m qbank.build --expand     # + LLM expansion across the taxonomy
    python -m qbank.build --stats      # just print what's in questions_db.json

Stages (each a small, separately-testable module):

    sources.py    where questions come from + per-format parsers
    fetch.py      download with an on-disk cache
    normalize.py  clean one raw string; reject non-questions
    classify.py   keyword-map a question to one of the 10 canonical topics
    dedup.py      exact + blocked-fuzzy de-duplication
    taxonomy.py   topic -> subtopics tree, for LLM expansion
    expand.py     ask an LLM for more questions per (topic, subtopic)
    build.py      orchestrate the above -> questions_db.json
"""
