# RMTC 证据清单与证明边界

> 本文件是材料整理用的证据索引，不是主办方认证、正式成绩单、正式 AI 资格证明或现场检录结论。任何资格结论均以主办方在本场、本席位的记录和确认为准。

## 来源与哈希计算方法

- 下表“原始相对位置”均相对于 `default-workspace`；原始证据根目录为 `rmtc_materials/`。
- 本表中的 SHA-256 在编写本文件时使用 PowerShell `Get-FileHash -Algorithm SHA256` 对原始文件重新计算；哈希仅用于识别当时的精确字节内容，不替代来源认证或主办方确认。
- 表内所有实测 `*.json` 和 `*.log` 均**仅为练习材料**；其中 Stage 2 明确为 `mock`。其中的分数、回执、结束状态或 HTTP 成功次数均不得改写为正式成绩、正式检录或正式 AI 资格。

## 归档路径映射

若将本表五份原始证据纳入递交 ZIP，路径映射固定为：原 `rmtc_materials/<basename>` → ZIP 内 `evidence/<basename>`。复制前后必须字节一致，因此 ZIP 内对应文件的 SHA-256 必须与下表同名原始文件的 SHA-256 一致；若不一致，必须重新计算、记录，且不得称为同一证据副本。

| 原始相对位置 | SHA-256 | 可证明内容（限于该文件记录） | 不能证明内容 |
|---|---|---|---|
| `rmtc_materials/stage1-self-developed-r15.json` | `F842A6318207F75742D68ED0F06F48CDBDEE4D2A4E2B3D1B36DB106919F94FFC` | 一场标为 `practice` 的 Stage 1 自研 A 席位结算：资源价值 `200`、采集分 `40/40`、`invalid_actions=0`；结算记录为 tick 100、最终动作 tick 99。 | 正式比赛成绩；所有地图或所有场次的性能；真实统一 AI 调用；现场检录或裁判确认。 |
| `rmtc_materials/stage2-final-r16.json` | `3AA237C25C2EA30B48F79B49BDD3CFC3F0178962E721F31FD1274F2F07D09F5C` | 一场 500 tick 的 Stage 2 **mock 练习**结算：A 得分 `31.4`、任务 `2/3`、`invalid_actions=0`；A 的 AI 记录为 `mode=mock`、`success_count=31`。 | 真实 LLM 的理解或调用效果；主办方真实统一 AI 的本场本席位成功记录；正式 AI 资格；正式成绩、竞争力或现场检录。 |
| `rmtc_materials/stage2-after-restart-final-r16.log` | `65571C77BED423103BDC9E211582079E57BA078E9D33958E06D0D1433EAA672C` | 练习场中同一 `practice` session 在进程重启后继续接入的节点日志；日志逐条记录感知、带当前 `tick`/`session_id` 的动作及后续回执，例如 tick 143 的动作在 tick 144 得到移动回执。 | 主办方允许的正式重启流程或次数；正式设备、正式有线网络的可靠性；正式检录完成。 |
| `rmtc_materials/cross-session-r17.log` | `474BF6F9F26448BEC84E344A30508D48C9661B54744FCD2924D55F591EAD3F8E` | 同一进程记录的两个不同 `practice` session；各记录含当前感知的 `session_id`/`tick`、同值动作字段及后续动作回执，可用于核对跨 session 不沿用上一场身份。 | 正式席位分配；主办方环境中的跨场稳定性；真实 AI 或现场检录。 |
| `rmtc_materials/development-test-record.md` | `2327D09F8D9693406D0EDD73834533A094FD71856897489C4D6EB9E32078E6BC` | 人工编写的开发、测试、练习联调及限制记录，并指向上述结算和日志。 | 独立的密码学签发证明；主办方签发的资格证明；任何未由原始实测材料和现场记录复核的结论。 |

## 关键边界

1. Stage 1 的“资源价值 200、采集分 40/40、非法动作 0”仅是上表首项的一场练习结算。
2. Stage 2 的“31.4、任务 2/3、非法动作 0、mock success 31”仅说明该份文件记载的 mock 练习状态；尤其 `mode=mock` 和 `success_count=31` **不能**推导为真实 AI、真实模型理解或正式 AI 资格。
3. 日志中的动作与回执只能作为练习中已记录行为的核对材料；它们不替代主办方在当前正式环境下对感知、同 tick/session_id、合法动作和执行回执的现场检查。
4. 文件哈希匹配只说明待核验副本与上述原始文件字节一致；若原始文件或复制件发生变化，应重新计算并更新哈希，不能沿用本表数值。

## 当前缺失或不能由本包证明的材料

- 新增 `docs/precheck-referee-2026-10-31.png`：真实公开练习裁判页，session `practice-c0992cb0377946b38aa6c5d65fa38096`，感知/动作 Tick 60、执行 Tick 59。SHA-256：`3F0FF2F41901AC23FF31E91A5382711F7FE2E6933A77DC476B8360B813E19DD8`。
- 同场程序日志与状态摘录位于 `docs/precheck-node-2026-10-31.log`、`docs/precheck-state-2026-10-31.json`，仅为公开练习；完整编译启动及全部检录字段的连续影像尚待补齐。
- `rmtc_materials/vm-status.png` 未列为本表证据，且**不是**该检录所需的运行截图/录屏图像证据；不得把它标注或提交为合格检录图像。
- 本包没有主办方真实统一 AI 在本场、该席位的成功记录，没有主办方指定正式设备和有线网络上的现场运行记录，也没有裁判确认。
- 因此，本清单不能支持“已完成正式检录”或任何等价结论。现场需要补齐的项目见 `SUBMISSION_CHECKLIST.md`。

## 使用要求

- 递交、报告引用和文件名必须保留“练习”或“mock”标签，不得去除限定词。
- 如需随归档复制这些原始文件，应在复制后再次运行 `Get-FileHash -Algorithm SHA256`，并与本表逐项比对。
- 本清单不包含令牌、Authorization 头、AI 网关凭据或其他秘密；后续现场证据也必须保持这一边界。
