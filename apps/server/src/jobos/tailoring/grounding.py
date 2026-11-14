"""Deterministic grounding checker for reworded lines (ADR-0008).

A reworded line may change *wording and emphasis* but not *facts*. We approximate "facts" with things that are
cheap to check and expensive to get wrong:

- every number must appear in the cited sources (no inflated metrics, years or team sizes);
- every technology/proper-noun-like term must appear in the sources, the item's names/skills, or the profile's
  skills (no new tools, employers or products);
- role-escalating verbs ("led", "architected", "managed"...) must appear in the sources;
- the line cannot be much longer than its sources, and most of its content words must come from them.

Anything that fails falls back to the verbatim source text, so a rejection never loses information.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .sources import tokens

_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# Common acronyms that describe *how* something was built, not *what* the candidate has: allowed anywhere.
_GENERIC_TERMS = {"api", "apis", "ui", "ux", "url", "urls", "json", "http", "https", "rest", "restful", "crud",
                  "sdk", "cli", "mvp", "e2e", "end-to-end", "real-time", "realtime", "i", "a"}
# Verbs that change the scope of the candidate's role: must be in the source to be used.
_ESCALATION = ("led", "lead", "leading", "manag", "spearhead", "architect", "owned", "own ", "mentor", "direct",
               "headed", "supervis", "oversaw", "oversee", "pioneer", "founded", "co-founded", "invent")
_STOP = set(["a", "an", "and", "or", "the", "of", "to", "for", "in", "on", "at", "by", "with", "from", "into", "via", "as", "is", "are", "was", "were", "be", "been", "being", "this", "that", "these", "those", "it", "its", "their", "our", "my", "we", "i", "you", "your", "over", "under", "across", "within", "using", "use", "used", "per", "than", "then", "so", "such", "both", "each", "more", "most", "less", "least", "very", "also", "not", "no", "new", "same", "other", "more"])
# Light, meaning-preserving resume verbs a rewrite may introduce.
_GENERIC_VERBS = set(["built", "build", "building", "developed", "develop", "developing", "created", "create", "creating", "implemented", "implement", "implementing", "designed", "design", "designing", "delivered", "deliver", "shipped", "ship", "wrote", "write", "written", "added", "add", "integrated", "integrate", "integrating", "improved", "improve", "improving", "reduced", "reduce", "enabled", "enable", "enabling", "worked", "work", "working", "made", "make", "making", "set", "setup", "automated", "automate", "automating", "deployed", "deploy", "deploying", "engineered", "engineer", "engineering", "contributed", "contribute", "supported", "support", "supporting", "launched", "launch", "powered", "power", "optimized", "optimize", "optimizing", "handled", "handle", "handling", "ran", "run", "running", "maintained", "maintain", "feature", "features", "system", "systems", "service", "services", "application", "applications", "app", "apps", "platform", "tool", "tools", "pipeline", "pipelines", "users", "user", "team", "teams", "product", "products", "project", "projects", "end-to-end", "production", "scalable", "fast", "faster", "reliable", "based"])


@dataclass
class Verdict:
    ok: bool
    reason: str = ""


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in _NUMBER.findall(text)}


def _stem(word: str) -> str:
    return word[:5]


def _entity_like(tok: str, sentence_start: bool) -> bool:
    """Tech terms and names: inner capitals, digits or symbols, or capitalised mid-sentence."""
    if any(ch.isdigit() for ch in tok) or any(ch in ".+#&" for ch in tok.strip(".")):
        return True
    if any(ch.isupper() for ch in tok[1:]):
        return True
    return tok[0].isupper() and not sentence_start


def check_line(text: str, source_text: str, allowed_vocab: set[str], *, max_ratio: float = 1.45,
               max_novel_fraction: float = 0.5) -> Verdict:
    """Is ``text`` a faithful rewording of ``source_text``? ``allowed_vocab`` = lowercase tokens the line may
    use beyond its sources (item names/skills, profile skills)."""
    text = text.strip()
    if not text:
        return Verdict(False, "empty")
    if not source_text.strip():
        return Verdict(False, "no source text")
    if len(text) > max(len(source_text) * max_ratio + 30, 80):
        return Verdict(False, "much longer than its source")

    extra_numbers = _numbers(text) - _numbers(source_text)
    if extra_numbers:
        return Verdict(False, f"number not in source: {', '.join(sorted(extra_numbers))}")

    src_tokens = [t.lower() for t in tokens(source_text)]
    src_set = set(src_tokens)
    src_stems = {_stem(t) for t in src_tokens}
    vocab = src_set | allowed_vocab | _GENERIC_TERMS

    low = text.lower()
    src_low = source_text.lower()
    for verb in _ESCALATION:
        if re.search(rf"\b{re.escape(verb)}", low) and not re.search(rf"\b{re.escape(verb)}", src_low):
            return Verdict(False, f"role-escalating wording '{verb.strip()}' not in source")

    novel: list[str] = []
    content = 0
    prev_end = ""
    for i, tok in enumerate(tokens(text)):
        lt = tok.lower()
        sentence_start = i == 0 or prev_end in {".", ":", ";", "!", "?"}
        prev_end = tok[-1] if tok[-1] in ".:;!?" else ""
        if _entity_like(tok, sentence_start) and lt.strip(".") not in vocab and lt not in vocab:
            return Verdict(False, f"term not in source or skills: {tok}")
        if lt in _STOP or len(lt) < 4:
            continue
        content += 1
        if lt not in vocab and _stem(lt) not in src_stems and lt not in _GENERIC_VERBS:
            novel.append(tok)
    if content and len(novel) / content > max_novel_fraction:
        return Verdict(False, "too far from the source wording: " + ", ".join(novel[:5]))
    return Verdict(True)


def normalize(text: str) -> str:
    return re.sub(r"[\s.]+$", "", re.sub(r"\s+", " ", text.strip())).lower()
