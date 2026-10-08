# Codex Desktop × Watchdog：Hook 信任与 Windows 现场修订（2026-10-08）

> **不要覆盖已经在用户机器上跑通的全局 Hook。** 这是现场操作指南，不是网页 ChatGPT 能替你点击的授权按钮。只依据用户发送的现场摘要编排；尚未读取本地完整 Markdown 和私有日志。

## 现场证据与严格边界

操作者报告：来自 Codex Desktop 的 SessionStart / PreToolUse / PostToolUse / Stop / SessionEnd 事件已保存到本机脱敏日志；一个监控窗口显示新事件；旧的 SUSPECTED_STALL 只通知一次。报告声称总计 25 条、其中 24 条来自 App，**尚未由本会话独立核验原始证据**。建议状态为 `G1 OPERATOR_REPORTED_E2E_PASS / TRUST_CONFIRMATION_PENDING`；G3 真实有效性与 G4 长期稳定性仍缺。

前 29–32 篇仅推荐**项目级** `.codex/hooks.json`，以及直接启动带引号的 Python 命令；用户实机记录显示此环境最稳定方案是**全局** `~/.codex/hooks.json`、`commandWindows` 和无空格 ASCII `.cmd` 包装。两者不是同一个部署结论，不应覆盖工作中的配置。

## 官方规则与问题单纠正

- [官方 Codex Hooks](https://developers.openai.com/codex/hooks)：多来源 Hooks **叠加**；非 managed 命令 Hook 按其当前定义 hash 审核信任，变更后要重新信任；`/hooks` 是**交互式 CLI** 的命令。`--dangerously-bypass-hook-trust` 是临时跳过门槛，不是信任登记。
- [#37362](https://github.com/openai/codex/issues/37362) 记录 Desktop 项目 Hook 可能因信任审查入口不足而无声跳过；[ #38168 ](https://github.com/openai/codex/issues/38168) 记录 Windows 带引号命令执行问题。这些是对应版本/用户的报告，不是本机所有版本的定律。
- 用户提到的 [#16430](https://github.com/openai/codex/issues/16430) 讨论的是**插件内 Hook**，并非项目级 Hook 在 Windows Desktop 不派发的直接证明。
- 官方 `SessionEnd` Hook 最大 timeout 为 3 秒；`commandWindows` 用于覆盖 Windows 的执行命令。不要为让测试通过而关闭沙盒或向未经审查的程序放权。
- **App 显示 completed、CLI 显示 trusted，都不替代实际处理器产生新事件**；参阅 [#33564](https://github.com/openai/codex/issues/33564)。

## 1. 安全审查（不写配置、不触发 Hook）

在**与你启动 Desktop 相同的 Windows 用户身份**下，先用 PowerShell：

```powershell
$env:CODEX_HOME
$HOME
Get-Command codex
codex --version
```

没有设置 `CODEX_HOME` 通常使用默认用户目录的 `.codex`。不要把另一个进程的 `LOCALAPPDATA` 或 `CODEX_HOME` 当作当前 App 的身份，避免出现你已记录的多身份日志目录错误。

同步此仓库的 v33 诊断工具后，在本地运行：

```powershell
cd D:\program\Agent-Watchdog\examples\v04\watchdog
python app_trust_review_v33.py
python app_trust_review_v33.py --project "D:\Projects\codex-app-test"
```

**这些仅是示意的用户报告路径**；不能假设脚本已存在于这两个本地位置。工具只显示配置层事件数量、`commandWindows` 有无、可疑带引号 Windows 命令/重复事件来源等；**不会输出任何命令文本、trusted_hash 或私人配置数据，也不会对 Hook 做修改或信任确认**。如果某事件计数超过 1，属于“可能并发匹配”，不是已经证实重复执行同一个处理器。

如果日志目录路径环境与 App 不一致，优先对照已成功写入的本机位置，而不是自动修改/迁移私人日志。

## 2. 真正的信任操作必须在交互式 Codex CLI 里完成

仍在同一用户、同一 `CODEX_HOME` 的终端，执行：

```powershell
codex
```

待进入 **Codex CLI 的交互式输入框后**，键入：

```text
/hooks
```

不要在普通终端运行 `codex /hooks`，也不要在 ChatGPT 网页里输入这行期待它修改本机信任。按照交互界面逐项审阅实际启用的全局 Hook：核对来源、事件、`commandWindows`、ASCII `.cmd` 绝对路径、运行命令、SessionEnd 超时；只信任确实经你审阅的当前定义。出现多份全局与项目配置时不要全部点击 Trusted，需先排除重复、错误版本、未知处理器。

**绝对不要用 `--dangerously-bypass-hook-trust` 作为此步通过的证据。** 既有带 bypass 的 CLI 测试只能说明临时绕过后某条事件运行过。

## 3. 回到真实 Codex Desktop 完成新会话验证

退出交互 CLI、完全重启桌面 App，用已经验证的工作配置开启一次新的低风险任务。核对五个条件：

1. `/hooks` 中当前定义显示已审查并信任，期间没有修改 Hook JSON、包装脚本或执行命令；
2. 没有 bypass 的新 Desktop 会话实际执行了有工具调用的任务；
3. 日志新增来自此 App 会话、时间相符的 SessionStart/PreToolUse/PostToolUse（其他 SessionEnd/Stop 的触发时机按实际生命周期），而不是 fixture；
4. 同一工具调用没有全局 + 项目级处理器重复触发；关掉 Watchdog 不会关闭 App；
5. 历史 SUSPECTED_STALL 不重新弹出。历史提醒 ID 的持久化只是通知去重，不代表卡死准确率。

以上事实应写进私有现场验收表；不应公开 GitHub 提交本人的真实用户名、研究目录、完整日志、私有 `config.toml`、`hooks.json`、token 等。只分享去敏统计和状态。

## 4. 状态与下一步

现状是**真人操作已声称打通桌面生命周期事件，但 Hook 定义的正常信任状态仍须复验**。这比“完全未接入”更进一步，也不足以把 G3/G4 判定完成。

本 ChatGPT 网页会话可以修订公开 GitHub 参考代码与文档，但不能直接访问用户 C/D 盘、也不能在本机交互 CLI 里代替用户选择 Trust。若仍未收到事件，可按“配置来源 → 同一 CODEX_HOME → 定义 hash → Windows 子进程启动 → 脱敏日志路径”的顺序定位。
