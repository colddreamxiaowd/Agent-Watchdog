"""Chapter 18: read-mostly Streamlit dashboard for local, private use only.

Usage: streamlit run dashboard.py -- --repo D:\\program\\agent_watchdog\\hook_demo
No CLI, test execution, or Agent-control actions are exposed to the UI.
"""
import argparse
from pathlib import Path

import evidence
import journal
import supervision


def snapshot(repo, db=journal.DEFAULT_DB):
    """Build a UI data payload. Does not create a scan or run tests."""
    repo = evidence.root_for(repo)
    current = evidence.read_json(evidence.state_dir(repo) / 'bridge_report.json') or {}
    safe_events = supervision.recent_events(db, limit=20)
    assessment = supervision.diagnose(repo, db=db, events=safe_events)
    return {'repo': str(repo), 'git': current, 'assessment': assessment, 'events': safe_events}


def main():
    # Lazy dependency means unit tests and CLI work without Streamlit installed.
    import streamlit as st
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--repo', required=True)
    p.add_argument('--db', default=str(journal.DEFAULT_DB))
    args, _ = p.parse_known_args()
    st.set_page_config(page_title='Agent Watchdog', page_icon='🛡️', layout='wide')
    st.title('🛡️ Agent Watchdog · 本地监督面板')
    st.caption('只显示独立观察到的证据与风险提示；不执行测试，不控制 Codex。')

    @st.fragment(run_every='5s')
    def live():
        try:
            data = snapshot(args.repo, args.db)
        except (RuntimeError, ValueError, OSError) as exc:
            st.error('无法读取受监控仓库：' + type(exc).__name__)
            return
        summary = data['assessment']
        a, b, c = st.columns(3)
        a.metric('验收阶段', summary['state'].get('stage', 'UNKNOWN'))
        b.metric('独立风险事实', len(summary['facts']))
        c.metric('待人工复核的信号', len(summary['hypotheses']))
        st.subheader('验收证据')
        checks = summary['state'].get('checks')
        st.table([{'验收项': k, '状态': v} for k, v in checks.items()] if isinstance(checks, dict) else [])
        st.subheader('确定性事实（含 Git 路径差异）')
        if summary['facts']:
            st.json(summary['facts'])
        else:
            st.info('当前未触发已实现的事实规则；并不证明没有风险。')
        st.subheader('启发式信号（不能证明卡住）')
        if summary['hypotheses']:
            st.json(summary['hypotheses'])
        else:
            st.caption('暂无达到阈值的启发式提示。')
        st.subheader('最近事件 · 脱敏元数据')
        st.dataframe(data['events'], use_container_width=True, hide_index=True)
        st.caption('来源必须人工核验。页面读取事件仓库日志，缺失事件不代表 Agent 已停机。')
    live()


if __name__ == '__main__':
    main()
