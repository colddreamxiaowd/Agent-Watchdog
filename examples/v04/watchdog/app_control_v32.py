"""One entry point to local Codex App companion. Human review first.
This is NOT an in-process Codex plugin or a validated turnkey installer.
"""
import argparse
import json

import app_setup_v29
import app_recovery_v31
import app_watch_v30


def main():
    p=argparse.ArgumentParser(description="Agent Watchdog Codex App sidecar, opt-in")
    sub=p.add_subparsers(dest="command",required=True)
    x=sub.add_parser("doctor")
    x.add_argument("--repo",required=True)
    x=sub.add_parser("propose")
    x.add_argument("--repo",required=True)
    x=sub.add_parser("install")
    x.add_argument("--repo",required=True)
    x.add_argument("--ack-reviewed-hooks",action="store_true")
    x=sub.add_parser("watch")
    x.add_argument("--once",action="store_true")
    x.add_argument("--notify",action="store_true")
    x.add_argument("--include-existing",action="store_true")
    x.add_argument("--interval",type=int,default=3)
    sub.add_parser("status")
    sub.add_parser("backup")
    args=p.parse_args()
    if args.command=="doctor":
        print(json.dumps(app_setup_v29.doctor(args.repo),ensure_ascii=False,indent=2))
    elif args.command=="propose":
        print(json.dumps(app_setup_v29.config(),ensure_ascii=False,indent=2))
    elif args.command=="install":
        print(json.dumps({"installed":str(app_setup_v29.install(
                         args.repo,app_setup_v29.config(),args.ack_reviewed_hooks)),
                         "codex_app_end_to_end":"NOT_VERIFIED"},ensure_ascii=False))
    elif args.command=="watch":
        # Reuse the watcher CLI after argument validation. Does not run Codex.
        import sys
        argv=["app_watch_v30.py"]
        if args.once: argv.append("--once")
        if args.notify: argv.append("--notify")
        if args.include_existing: argv.append("--include-existing")
        argv.extend(["--interval",str(args.interval)])
        old=sys.argv
        try:
            sys.argv=argv
            app_watch_v30.main()
        finally:
            sys.argv=old
    elif args.command=="status":
        print(json.dumps(app_recovery_v31.status(),ensure_ascii=False,indent=2))
    elif args.command=="backup":
        print(json.dumps(app_recovery_v31.backup(),ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
