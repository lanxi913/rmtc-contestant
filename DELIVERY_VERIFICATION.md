# 手册核对与验证记录（更新至 2026-10-31）

本记录由AI工具执行命令后整理，王烨为单人参赛责任人；不构成主办方认证。

## 历史源码复核（不代表 10 月 30 日修订验证）

- Windows PATH Python 3.9.13，在项目 `rmtc_contestant` 包目录运行 `python -B -m unittest discover -s test -v`，82 项测试通过，输出 `Ran 82 tests in 0.667s`、`OK`。
- Ubuntu 22.04 虚拟机 SSH 可达，Python 3.10.12、ROS 2 Humble 存在。在既有验证副本运行同一完整测试命令，82 项通过，输出 `Ran 82 tests in 0.445s`、`OK`；加载 Humble 后运行 `~/.local/bin/colcon build --packages-select rmtc_contestant`，输出 `1 package finished [0.55s]`。
- 使用 Python hashlib 与 PowerShell Get-FileHash 比对 Ubuntu 副本的包源码、测试及 setup.py 共16份Python文件，全部与当前交付源码逐字节哈希相同。
- 在 Ubuntu 验证副本运行 `bash -n scripts/run_contestant.sh`，输出 `LAUNCH_BASH_SYNTAX_OK`。
- 五份原始练习证据实际 SHA-256 与 EVIDENCE_MANIFEST.md 全部一致。
- 当前版本无人工策略切换配置文件；README/指南/报告明确不支持该功能。

## 历史 ZIP 独立复核（以下旧包已被修订取代）

- 历史包：`submission/rmtc-contestant-submission-2026-10-27-164938.zip`，SHA-256：`8050F1611794E2A4CC1BB927F7977EE700842CCEF9D576E11FE4CBD58DD7F847`。
- Windows 独立校验器结果 `PASS`：33 个文件、五份证据、白名单、证据 manifest SHA、源码逐字节匹配及解压检查通过。临时目录：`%TEMP%\\rmtc-delivery-verified-wg84qk8w\\rmtc-contestant`。
- 同一确切 ZIP 在 Ubuntu 全新解压后 82 项单测通过（`Ran 82 tests in 0.448s`，`OK`），`bash -n scripts/run_contestant.sh` 通过，ROS 2 Humble colcon 输出 `1 package finished [0.54s]`。临时目录：`/tmp/rmtc-final-archive-7kuyr2m6/rmtc-contestant`。
- 归档脚本 PowerShell Parser 通过；负向拒绝检查曾对既有脚本版本执行通过。根文档白名单严格六份，不含 HANDOFF。ZIP 使用 POSIX 正斜杠。

源码或 ZIP 构建后发生任何变化，都须按新内容重新验证；以上复核对应本节所列哈希。


## 2026-10-30 修订验证

- 已完整提取并核对 8 页参赛手册；设备 IP/席位分离、域为示例、网关/DNS 留空、VMware 有线桥接与赛前影像流程已更正。
- 新增 HTTP 请求断言后先复现 `None != 512`，修正 payload 的 max_tokens 后 Windows Python 3.9 全部 82 项测试通过（0.740s）。模型由启动配置设为 deepseek-flash。
- 本文不会写入包含自身的 ZIP 哈希，避免循环更新。此次新 ZIP 文件名、SHA 和最终解压验证结果在 ZIP 外 HANDOFF.md 与同名 .sha256 中记录。
- 本次未取得真实 AI、正式网络或合格影像；AI 首帧兜底、失败去重及换场队列风险已如实列入报告，未修改其行为。

## 证据边界

历史Stage1一次练习资源200、采集40/40、非法动作0；历史Stage2 mock一次练习31.4、任务2/3、非法动作0、第4/4。没有新增真实LLM或正式比赛成绩。本记录不修改原始练习证据，以免其已登记哈希失效。

主办方真实统一 AI、本场本席位成功记录、完整连续检录影像、正式网络检录及裁判确认均未完成。10 月 31 日已另采集公开练习裁判页截图并附本队原始日志。规则原文截图/录屏随材料提交截止为2026年10月31日20:00前，以主办方通知为准。


## 2026-10-31 新版练习包验证

- supplied dist 中 rmtc_practice.tar.gz 的 SHA-256 校验匹配：`b2e92c20829258a1caf1f2224b8b22f2ca6ce6a2e41a20a6ca5752564ff747f1`。
- Ubuntu 22.04 / ROS 2 Humble 的本次测试输出：82 tests，0.490s，OK；随后在正确包根执行 colcon，输出 `1 package finished [1.23s]`。不将早先 HOME 目录构建失败算作成功。
- 隔离练习实例使用 ROS_DOMAIN_ID=40、端口 8081；既有 8080 实例未停止。没有参考车，唯一 A 控制节点是本队程序。
- 慢速诊断场次：1000 ms/Tick、60 Tick，session `practice-c0992cb0377946b38aa6c5d65fa38096`；最终资源 170、练习分 34、非法动作 0、HP 100，感知/动作 Tick 60、执行 Tick 59。该时长不是标准满场比较条件。
- 裁判页截图经 CDP 从原页直接保存，页面 DOM 核对了上述字段；节点原始日志核对 position、同 tick/session 动作及后续 receipt。完整连续影像与正式收件尚未完成。
- 公开仓库排除所有历史 ZIP、交接单、缓存和桌面截图；学号从公开文档移除，维护邮箱替换为已核验 GitHub noreply。策略代码未修改。
