"""`jobos` command line: serve, migrate, runner tokens, profile import, one-off discovery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="jobos")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("serve", help="run the API (and workers with --role all|worker)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--role", choices=["api", "worker", "all"], default=None)
    sub.add_parser("migrate", help="apply database migrations")
    p = sub.add_parser("runner-token", help="create a runner token (shown once)")
    p.add_argument("name")
    p = sub.add_parser("import-profile", help="build the master profile from a resume/profile file")
    p.add_argument("file", type=Path)
    p = sub.add_parser("add-document", help="upload a resume PDF")
    p.add_argument("file", type=Path)
    p.add_argument("--label", default="")
    p.add_argument("--default", action="store_true")
    p = sub.add_parser("discover-boards", help="find employers' public ATS boards and add them to the crawl list")
    p.add_argument("--names-file", type=Path, help="one company name per line (default: built-in list)")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true", help="only print what would be added")
    args = parser.parse_args(argv)

    if args.cmd == "migrate":
        from jobos.db.migrate import upgrade

        upgrade()
        print("database up to date")
    elif args.cmd == "serve":
        import os

        import uvicorn

        if args.role:
            os.environ["JOBOS_WORKER_ROLE"] = args.role
        from jobos.api.app import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
    elif args.cmd == "runner-token":
        from jobos.db import session_scope
        from jobos.services.candidates import get_or_create_default_candidate
        from jobos.services.runner_gateway import create_runner

        with session_scope() as s:
            cand = get_or_create_default_candidate(s)
            _, token = create_runner(s, cand.id, args.name)
        print(token)
    elif args.cmd == "import-profile":
        from jobos.db import session_scope
        from jobos.llm import get_gateway
        from jobos.services.candidates import get_or_create_default_candidate, save_profile
        from jobos.services.profile_import import build_profile, extract_text

        text = extract_text(args.file.name, args.file.read_bytes())
        profile = build_profile(get_gateway(), text)
        with session_scope() as s:
            cand = get_or_create_default_candidate(s)
            version = save_profile(s, cand.id, profile, source="import")
        print(json.dumps({"version": version, "name": profile.basics.full_name,
                          "work": len(profile.work), "projects": len(profile.projects)}))
    elif args.cmd == "add-document":
        import uuid

        from jobos.db import session_scope
        from jobos.db.models import Document
        from jobos.services.candidates import get_or_create_default_candidate
        from jobos.services.profile_import import extract_text
        from jobos.services.storage import put_bytes, sha256

        data = args.file.read_bytes()
        with session_scope() as s:
            cand = get_or_create_default_candidate(s)
            doc_id = uuid.uuid4()
            path = put_bytes(f"documents/{cand.id}/{doc_id}/{args.file.name}", data)
            s.add(Document(id=doc_id, candidate_id=cand.id, kind="resume", label=args.label, filename=args.file.name,
                           storage_path=path, sha256=sha256(data), text=extract_text(args.file.name, data)[:50000],
                           is_default=args.default))
        print(doc_id)
    elif args.cmd == "discover-boards":
        from jobos.db import session_scope
        from jobos.services.discovery import add_found_boards
        from jobos.sources.board_discovery import candidate_names, discover

        names = ([n.strip() for n in args.names_file.read_text().splitlines() if n.strip()]
                 if args.names_file else candidate_names())
        names = names[: args.limit] if args.limit else names
        found = discover(names)
        if args.dry_run:
            for f in found:
                print(f"{f.ats:10} {f.board_token:30} {f.name} ({f.jobs} jobs)")
        else:
            with session_scope() as s:
                added = add_found_boards(s, found)
            print(json.dumps({"probed": len(names), "found": len(found), "added": len(added)}))
    else:  # pragma: no cover
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
