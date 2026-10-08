"""Read-only Rich dashboard for the original V0.3/V0.4 data path."""
import argparse
import json
import time
from pathlib import Path
import evidence


def screen(repo):
    from rich.table import Table
    from rich.panel import Panel
    from rich.console import Group
    state = evidence.state_dir(repo)
    report = evidence.read_json(state / "bridge_report.json") or {}
    events = []
    logfile = Path(__file__).resolve().parent / "logs" / "events.jsonl"
    if logfile.exists():
        # bounded recent window, intentionally not a complete session history
        with logfile.open("rb") as f:
            f.seek(max(0, logfile.stat().st_size - 256 * 1024))
            text = f.read().decode("utf-8", "replace")
        for line in text.splitlines()[-150:]:
            try:
                row = json.loads(line)
                if isinstance(row, dict) and row.get("cwd") and Path(row["cwd"]).resolve().is_relative_to(repo):
                    events.append(row)
            except (ValueError, OSError, RuntimeError):
                continue
    t = Table(title="最近观察到的 Hook 事件（窗口，不是全部历史）")
    t.add_column("时间"); t.add_column("事件"); t.add_column("工具")
    for e in events[-8:]:
        t.add_row(str(e.get("received_at", ""))[11:19], str(e.get("event", "")), str(e.get("tool") or "-"))
    ev = Table(title="Git / Test 独立证据")
    ev.add_column("项目"); ev.add_column("结果")
    ev.add_row("仓库", str(repo))
    ev.add_row("扫描触发", str(report.get("trigger", "尚未运行 Bridge")))
    ev.add_row("文件变化", str(len(report.get("changed", []))))
    ev.add_row("保护文件", ", ".join(report.get("protected", [])) or "未观察到")
    ev.add_row("测试证据", str(report.get("test_status", "UNKNOWN")))
    ev.add_row("最近扫描", str(report.get("scanned_at", "-")))
    return Panel(Group(ev, t), title="Agent Watchdog 04 · observer only")


def main():
    from rich.live import Live
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    args = p.parse_args()
    repo = evidence.root_for(args.repo)
    with Live(screen(repo), refresh_per_second=2) as live:
        while True:
            time.sleep(1)
            live.update(screen(repo))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
