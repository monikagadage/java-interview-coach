"""Keyword-map a question to one of the 10 canonical topics.

A heuristic, not a classifier — explicitly labelled as such, like
``graph/selection.py``'s difficulty estimate. Each topic has an ordered
list of regex patterns; the first topic with a match wins, ties broken by
the order in ``TOPICS``. Anything unmatched falls back to ``Java Core``.
"""
from __future__ import annotations

import re

from topics import TOPICS

# Ordered most-specific first so e.g. "concurrent collection" lands in
# Multithreading, not Java Collections.
_RULES: list[tuple[str, list[str]]] = [
    ("Multithreading", [
        r"\bthread", r"\bconcurren", r"\bsynchroni[sz]", r"\bvolatile\b",
        r"\bexecutor", r"\block\b", r"\bdeadlock", r"\bsemaphore", r"\bfork/?join",
        r"\bcompletablefuture", r"\bcountdownlatch", r"\brace condition", r"\batomic",
    ]),
    ("Spring", [
        r"\bspring\b", r"\bspring boot", r"\b@component|@bean|@autowired|@controller",
        r"\bdependency injection", r"\bioc\b", r"\bhibernate\b", r"\bjpa\b",
        r"\bbean\b", r"\brest controller", r"\bactuator",
    ]),
    ("JVM", [
        r"\bjvm\b", r"\bclassloader", r"\bgarbage colle", r"\bheap\b", r"\bstack\b",
        r"\bbytecode", r"\bjit\b", r"\bpermgen|metaspace", r"\bmemory (?:area|model|leak)",
        r"\bjava memory model", r"\bfinaliz", r"\bescape analysis",
    ]),
    ("Java 8", [
        r"\bstreams?\b", r"\bflat ?map\b", r"\blambda", r"\bfunctional interface",
        r"\boptional\b", r"\bmethod reference", r"\bdefault method", r"\bjava 8",
        r"\bcollectors?\b", r"\bpredicate|supplier|consumer|function<",
        r"\bdate ?and ?time api", r"\breduce\b|\bmapToObj\b|\bcollect\b",
    ]),
    ("Java Collections", [
        r"\bcollection", r"\bhashmap|hashtable|hashset|linkedhashmap|treemap|treeset",
        r"\barraylist|linkedlist|vector\b", r"\biterator|iterable", r"\bcomparator|comparable",
        r"\bqueue|deque|priorityqueue", r"\bfail-?fast|fail-?safe", r"\bload factor",
    ]),
    ("Databases", [
        r"\bsql\b", r"\bjdbc\b", r"\btransaction", r"\bacid\b", r"\bindex(?:es|ing)?\b",
        r"\bnormali[sz]ation", r"\bjoin\b", r"\bisolation level", r"\bdatabase|rdbms",
        r"\bconnection pool", r"\bn\+1\b",
    ]),
    ("Testing", [
        r"\bjunit", r"\bmockito|mock\b", r"\bunit test|integration test", r"\btdd\b",
        r"\bassert", r"\btest(?:ing)? (?:framework|pyramid|double)", r"\bstub\b",
        r"\bcode coverage",
    ]),
    ("Patterns", [
        r"\bdesign pattern", r"\bsingleton|factory|builder|prototype|adapter|decorator",
        r"\bobserver|strategy|facade|proxy pattern|command pattern", r"\bsolid\b",
        r"\bdependency inversion", r"\bopen/?closed", r"\bmvc\b",
    ]),
    ("OOP", [
        r"\bencapsulat", r"\binherit", r"\bpolymorph", r"\babstraction",
        r"\binterface\b", r"\babstract class", r"\boverload|overrid", r"\bconstructor",
        r"\bcompos(?:e|ition) over inheritance", r"\bis-a|has-a", r"\baccess (?:modifier|specifier)",
        r"\bobject-?oriented",
    ]),
    ("Java Core", [
        r"\bstring\b|stringbuilder|stringbuffer", r"\bexception|throwable|try-?with-?resources",
        r"\bgeneric", r"\benum\b", r"\bautobox", r"\bequals\(\)|hashcode", r"\bimmutab",
        r"\bfinal\b|finally|finalize", r"\bprimitive|wrapper", r"\bserializ", r"\bannotation",
        r"\breflection", r"\bvarargs", r"\bstatic\b", r"\bpass by (?:value|reference)",
    ]),
]

_COMPILED = [(t, [re.compile(p, re.I) for p in pats]) for t, pats in _RULES]
_FALLBACK = "Java Core"


def classify(question: str) -> str:
    best_topic, best_hits = _FALLBACK, 0
    for topic, patterns in _COMPILED:
        hits = sum(1 for p in patterns if p.search(question))
        if hits > best_hits:
            best_topic, best_hits = topic, hits
    return best_topic if best_topic in TOPICS else _FALLBACK
