"""De-duplicate a list of normalized questions.

Two passes:

1. **Exact** on ``normalize.dedupe_key`` (case/punctuation-insensitive).
2. **Fuzzy**, blocked so it stays roughly linear: bucket questions by a
   signature (their 3 rarest words), and within each small bucket drop any
   question whose token-set Jaccard with an already-kept one is >= a
   threshold. Catches "What is the difference between X and Y" vs "Difference
   between X and Y in Java" without an O(n^2) all-pairs comparison.
"""
from __future__ import annotations

import re
from collections import Counter

from qbank.normalize import dedupe_key

_WORD = re.compile(r"[a-z0-9]+")
# Very common, non-distinctive words in interview-question phrasing — drop
# them so "difference between X and Y" and "X vs Y in Java" collide.
_STOP = frozenset(
    "the a an of in on to is are was were what how why when which do does did "
    "you your and or for with as it its be been being can could would should "
    "we i me my our us java difference between vs versus explain describe "
    "define name list give tell about into over".split()
)
_JACCARD_THRESHOLD = 0.85


def _tokens(q: str) -> set[str]:
    return {w for w in _WORD.findall(q.lower()) if w not in _STOP and len(w) > 2}


def _signature(tokens: set[str], df: Counter) -> tuple[str, ...]:
    # The rarest (most distinctive) words -> questions about the same thing
    # land in the same bucket.
    return tuple(sorted(sorted(tokens, key=lambda w: (df[w], w))[:3]))


def dedupe(questions: list[str]) -> list[str]:
    # Pass 1: exact.
    seen_keys: set[str] = set()
    unique: list[str] = []
    for q in questions:
        k = dedupe_key(q)
        if k and k not in seen_keys:
            seen_keys.add(k)
            unique.append(q)

    # Pass 2: blocked fuzzy.
    token_sets = [_tokens(q) for q in unique]
    df: Counter = Counter()
    for ts in token_sets:
        df.update(ts)

    buckets: dict[tuple[str, ...], list[int]] = {}
    for i, ts in enumerate(token_sets):
        if not ts:
            buckets.setdefault(("",), []).append(i)
            continue
        buckets.setdefault(_signature(ts, df), []).append(i)

    drop: set[int] = set()
    for idxs in buckets.values():
        kept: list[int] = []
        for i in idxs:
            ti = token_sets[i]
            if not ti:
                kept.append(i)
                continue
            dup = False
            for j in kept:
                tj = token_sets[j]
                inter = len(ti & tj)
                union = len(ti | tj) or 1
                if inter / union >= _JACCARD_THRESHOLD:
                    dup = True
                    break
            if dup:
                drop.add(i)
            else:
                kept.append(i)

    return [q for i, q in enumerate(unique) if i not in drop]
