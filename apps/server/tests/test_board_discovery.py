"""Board discovery: slug guesses, company-name verification, exact-only probes for APIs without names."""

from __future__ import annotations

import httpx

from jobos.sources.board_discovery import BoardProber, candidate_names, slug_variants


def test_slug_variants() -> None:
    vals = [(s.value, s.exact) for s in slug_variants("Scale AI")]
    assert ("scaleai", True) in vals and ("scale-ai", True) in vals and ("scale", False) in vals
    assert [s.value for s in slug_variants("Weights & Biases")][:2] == ["weightsandbiases", "weights-and-biases"]
    assert ("cockroach", False) in [(s.value, s.exact) for s in slug_variants("Cockroach Labs")]


def _prober(routes: dict[str, tuple[int, object]]) -> BoardProber:
    def handler(req: httpx.Request) -> httpx.Response:
        key = f"{req.method} {req.url.host}{req.url.path}"
        code, body = routes.get(key, (404, {}))
        if isinstance(body, str):
            return httpx.Response(code, text=body)
        return httpx.Response(code, json=body) if req.method == "GET" else httpx.Response(code)
    return BoardProber(httpx.Client(transport=httpx.MockTransport(handler)), delay_s=0)


def test_probe_verifies_names_and_skips_empty_boards() -> None:
    p = _prober({
        "GET boards-api.greenhouse.io/v1/boards/scale": (200, {"name": "Scale"}),  # different company
        "GET boards-api.greenhouse.io/v1/boards/scaleai": (200, {"name": "Scale AI"}),
        "GET boards-api.greenhouse.io/v1/boards/scaleai/jobs": (200, {"jobs": [{"id": 1}, {"id": 2}]}),
        "GET api.lever.co/v0/postings/scale": (200, [{"id": "x"}]),  # shortened guess: never accepted
        "HEAD api.ashbyhq.com/posting-api/job-board/scale-ai": (200, None),
        "GET jobs.ashbyhq.com/scale-ai": (200, "<html><title>Scale AI Jobs</title></html>"),
    })
    found = {(f.ats, f.board_token, f.jobs) for f in p.probe("Scale AI")}
    assert found == {("greenhouse", "scaleai", 2), ("ashby", "scale-ai", 1)}

    p = _prober({"GET boards-api.greenhouse.io/v1/boards/acme": (200, {"name": "Totally Different Inc"})})
    assert p.probe("Acme") == []
    p = _prober({"GET api.lever.co/v0/postings/acme": (200, [])})  # board exists but no openings
    assert p.probe("Acme") == []
    p = _prober({"HEAD api.ashbyhq.com/posting-api/job-board/magic": (200, None),  # someone else's "magic"
                 "GET jobs.ashbyhq.com/magic": (200, "<title>Magic Leap Careers</title>")})
    assert p.probe("Magic") == []


def test_candidate_list_is_large_and_unique() -> None:
    names = candidate_names()
    assert len(names) > 500 and len(names) == len(set(names))
