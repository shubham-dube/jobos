"""`jobos-runner` CLI.

  jobos-runner setup --api http://localhost:8000 --token jr_...   # save config
  jobos-runner login                                             # open the JobOS Chrome profile to sign in
  jobos-runner run                                               # start working on tasks
"""

from __future__ import annotations

import argparse
import asyncio

from .config import load_config, save_config


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="jobos-runner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("setup", help="save API URL and runner token")
    p.add_argument("--api", required=True)
    p.add_argument("--token", required=True)
    p.add_argument("--max-sessions", type=int, default=2)
    p.add_argument("--profile-dir", default="")
    p = sub.add_parser("login", help="open the dedicated Chrome profile so you can sign in to Google/LinkedIn/...")
    p.add_argument("urls", nargs="*", default=["https://accounts.google.com", "https://www.linkedin.com/login"])
    sub.add_parser("run", help="connect to the API and execute tasks")
    sub.add_parser("show-config")
    args = parser.parse_args(argv)
    cfg = load_config()

    if args.cmd == "setup":
        cfg.api_url, cfg.token, cfg.max_sessions = args.api, args.token, args.max_sessions
        if args.profile_dir:
            cfg.profile_dir = args.profile_dir
        print(f"saved {save_config(cfg)}")
    elif args.cmd == "show-config":
        print({**cfg.__dict__, "token": (cfg.token[:6] + "…") if cfg.token else ""})
        print("profile:", cfg.resolved_profile_dir())
    elif args.cmd == "login":
        asyncio.run(_login(cfg, args.urls))
    elif args.cmd == "run":
        if not cfg.token:
            parser.error("run `jobos-runner setup --api ... --token ...` first")
        from .agent import run_forever

        run_forever(cfg)


async def _login(cfg, urls: list[str]) -> None:
    from .browser import BrowserManager

    cfg.headless = False
    bm = BrowserManager(cfg)
    await bm.start()
    for i, url in enumerate(urls):
        page = await bm.page_for(f"login-{i}")
        assert page is not None
        await page.goto(url)
    print("Sign in to your accounts in the opened Chrome window. Close the window (or press Ctrl+C) when done.")
    try:
        while bm.context.pages:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    await bm.stop()


if __name__ == "__main__":
    main()
