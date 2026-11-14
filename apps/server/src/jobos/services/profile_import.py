"""Profile Builder agent: resume / profile document → structured MasterProfile."""

from __future__ import annotations

import io

from jobos.llm import LLMGateway, untrusted
from jobos_common.profile import MasterProfile


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(io.BytesIO(data))
            return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except (PdfReadError, ValueError, KeyError):
            return ""  # unreadable/scanned PDF: still storable and uploadable
    return data.decode("utf-8", errors="replace").strip()


SYSTEM = """You are the Profile Builder agent. Convert the candidate's own career document into the
MasterProfile JSON structure. Rules:
- Copy facts exactly; never invent or embellish. If the document marks values as raw vs. alternative
  ("brag-safe", "if needed"), always use the RAW / verified value.
- Give every item a short stable id: work w1,w2…; their highlights w1h1,w1h2…; education e1…; projects p1…
  with highlights p1h1…; awards a1…; other facts f1….
- Dates as YYYY-MM (or YYYY). Current roles: end=null, current=true.
- Countries as ISO-3166 alpha-2 codes (India = IN). Phone: split country code ("+91") and national number.
- Skill levels map to: heard_of, read_about, dabbled, working_knowledge, proficient, strong.
  Skills listed as "stretch" get stretch=true.
- work_authorization: the candidate's citizenship country with status citizen and needs_sponsorship=false,
  plus {"country":"*","status":"none","needs_sponsorship":true} unless the document says otherwise.
- Put exam scores, rankings, user/traction numbers and similar into facts (one fact per item).
- Put internships, jobs and founder roles into work (employment_type: internship | full_time | founder |
  part_time | volunteer). Mark lower-priority items with priority -1 and headline items with priority 1.
- Demographics: leave as "decline" unless explicitly stated by the candidate."""


def build_profile(gateway: LLMGateway, text: str, *, ref: str = "") -> MasterProfile:
    user = f"Candidate document:\n{untrusted('candidate_profile_document', text, limit=60000)}"
    return gateway.structured("profile.extract", SYSTEM, user, MasterProfile, ref=ref, max_tokens=16000)
