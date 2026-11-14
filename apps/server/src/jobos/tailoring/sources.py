"""The citable source catalogue: every line on a tailored document must trace back to one of these."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jobos_common.profile import MasterProfile

_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+#'&-]*[A-Za-z0-9+#]|[A-Za-z0-9]")


def tokens(text: str) -> list[str]:
    """Words, keeping tech spellings together (Next.js, C++, C#, CI/CD splits on '/')."""
    return _TOKEN.findall(text.replace("/", " "))


@dataclass
class Item:
    id: str
    kind: str  # work | project
    name: str  # "SDE Intern, Acme" / "GSTVerify"
    sources: dict[str, str] = field(default_factory=dict)  # source id -> text (highlights, summary)
    vocab: set[str] = field(default_factory=set)  # lowercase tokens allowed on this item's lines
    priority: int = 0


@dataclass
class Catalogue:
    items: dict[str, Item]
    facts: dict[str, str]  # every citable id -> text (profile.fact_index + item summaries)
    skills: dict[str, str]  # lowercase skill name -> canonical name
    global_vocab: set[str]  # names, skills, companies: allowed anywhere

    def source_text(self, ids: list[str]) -> str:
        return " ".join(self.facts.get(i, "") for i in ids).strip()


def summary_id(item_id: str) -> str:
    return f"{item_id}:summary"


def build_catalogue(p: MasterProfile) -> Catalogue:
    facts = dict(p.fact_index())
    items: dict[str, Item] = {}
    skills = {s.name.lower(): s.name for s in p.skills}
    global_vocab: set[str] = set()
    for s in p.skills:
        global_vocab |= {t.lower() for t in tokens(s.name)}

    for w in p.work:
        it = Item(id=w.id, kind="work", name=f"{w.title}, {w.company}", priority=w.priority)
        for h in w.highlights:
            it.sources[h.id] = h.text
        if w.summary:
            it.sources[summary_id(w.id)] = w.summary
            facts[summary_id(w.id)] = w.summary
        words = " ".join([w.title, w.company, w.location, *w.skills, *[s for h in w.highlights for s in h.skills],
                          *it.sources.values()])
        it.vocab = {t.lower() for t in tokens(words)}
        global_vocab |= {t.lower() for t in tokens(f"{w.title} {w.company}")}
        items[w.id] = it
    for pr in p.projects:
        it = Item(id=pr.id, kind="project", name=pr.name)
        for h in pr.highlights:
            it.sources[h.id] = h.text
        if pr.summary:
            it.sources[summary_id(pr.id)] = pr.summary
            facts[summary_id(pr.id)] = pr.summary
        words = " ".join([pr.name, *pr.skills, *[s for h in pr.highlights for s in h.skills], *it.sources.values()])
        it.vocab = {t.lower() for t in tokens(words)}
        global_vocab |= {t.lower() for t in tokens(pr.name)}
        items[pr.id] = it
    for e in p.education:
        global_vocab |= {t.lower() for t in tokens(f"{e.institution} {e.degree} {e.field}")}
    return Catalogue(items=items, facts=facts, skills=skills, global_vocab=global_vocab)


def owner_of(cat: Catalogue, source_id: str) -> str | None:
    for item in cat.items.values():
        if source_id in item.sources:
            return item.id
    return None
