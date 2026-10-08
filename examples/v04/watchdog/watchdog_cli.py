"""Read-only status/alerts/handoff CLI. All reports are derived, not success claims."""
import argparse
import json
import sqlite3
from pathlib import Path
import bridge
import evidence
import journal
import risk
import task_contract


def recent_from_db(db=journal.DEFAULT_DB, limit=12):
    if not Path(db).exists():
        return []
    with journal.connect(db) as con:
        rows = con.execute("SELECT payload FROM events ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
    return [json.loads(row[0]) for row in rows][::-1]


def report(repo):
    source = evidence.read_json(evidence.state_dir(repo) / "bridge_report.json")
    if not source:
        source = bridge.scan(repo, "read-only status refresh")
    try:
        contract = task_contract.acceptance_status(repo)
    except (RuntimeError, ValueError):
        contract = None
    events = recent_from_db()
    alerts = risk.evaluate(source, contract, events)
    return {"repo": str(repo), "git": source, "contract": contract,
            "alerts": alerts, "events_window": len(events),
            "limitations": ["No proof of semantic goal completion", "Events not complete", "No automatic control"]}


def markdown_report(data):
    contract = data["contract"]
    lines = ["# Agent Watchdog — 交接快照", "", "- 仓库：`" + data["repo"] + "`",
             "- 生成时 Git 指纹：`" + data["git"].get("snapshot", "UNKNOWN") + "`",
             "- 最近扫描：`" + data["git"].get("scanned_at", "UNKNOWN") + "`",
             "- 已观察的保护文件变化：" + (", ".join(data["git"].get("protected",[])) or "未观察到"),
             "- V0.3 最近测试：" + data["git"].get("test_status","UNKNOWN"), ""]
    if contract:
        lines += ["## 合同状态", "", "- 目标：" + contract["goal"],
                  "- 当前阶段：**" + contract["stage"] + "**", "- 合同已批准：" + str(contract["approved"]),
                  "- 验收项目："]
        for key, value in contract["acceptance"].items():
            lines.append("  - `" + key + "`：" + value)
        lines.append("")
    lines += ["## 已观察到的提示", ""]
    if not data["alerts"]:
        lines.append("没有触发已配置的风险规则；这**不代表无风险**。")
    for item in data["alerts"]:
        lines.append("- " + item["code"] + "（" + item["kind"] + "）：" + str(item["evidence"]))
    lines += ["", "## 下次继续之前", "", "1. 先核对原始用户目标和合同有没有变化。",
              "2. 核对 `git diff` 与被保护文件，不靠 Agent 自己总结。",
              "3. 对 STALE、FAILED、INCONCLUSIVE 的验收逐项调查。",
              "4. 需要重新执行测试时，必须由用户明确启动。", "",
              "> 本文是监督器状态摘要，不是完整审计日志；不包含敏感命令或工具原文。"]
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("status"); sub.add_parser("alerts")
    x=sub.add_parser("handoff"); x.add_argument("--out", required=True)
    args=p.parse_args()
    repo=evidence.root_for(args.repo)
    data=report(repo)
    if args.action == "status":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "alerts":
        print(json.dumps(data["alerts"],ensure_ascii=False,indent=2))
    else:
        out=Path(args.out)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(markdown_report(data),encoding="utf-8")
        print("Handoff written:",out)

if __name__ == "__main__": main()
