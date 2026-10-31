# RMTC 参赛程序使用与演示指南

## 1. 当前交付状态

本程序面向 Ubuntu 22.04、ROS 2 Humble。第一阶段单车资源采集已实际接入官方练习裁判；第二阶段支持官方结构化任务、基础攻击/避险和非阻塞统一AI请求，但尚未证明完整赛事能力。请勿把单测或模拟AI当作正式检录通过。

已采集公开 Stage 1 裁判页面截图并嵌入报告；程序侧原始日志另存于 docs/。截图显示裁判的执行回执，日志显示 self.position、同 tick/session_id 动作和后续 receipt。完整编译启动及双向链路连续影像仍待补齐，不能据此自行认定检录合格。比赛当天另在分配网络/席位验证真实 AI。

完整项目入口见 `README.md`；规则对应的技术说明见 `TECHNICAL_REPORT.md`；递交与现场检录步骤见 `SUBMISSION_CHECKLIST.md`；每条证据的可证明范围见 `EVIDENCE_MANIFEST.md`。

已验证：Windows Python 3.9.13与Ubuntu系统Python各82项单测通过；Ubuntu colcon构建成功；第一阶段单次练习资源价值200、采集分40/40、非法动作0。

## 赛场有线网络与虚拟机（2026-10-30 手册第 3–5 页）

- 设备 IPv4、长期队伍 ID、A/B/C/D 席位分别管理；换席位不自动更换 IP。按群内发放的设备地址/掩码配置。`192.168.50.11/24`、ROS 域 `27`、网关示例均不是实际分配结果。
- VMware 使用桥接到实际插线的物理以太网卡，避免桥接到 Wi-Fi 或继续使用 NAT。分配的设备 IP 应配置在运行 ROS 的 Ubuntu 来宾系统；Windows 若也接入该网络须另用地址，不能与 Ubuntu 重复。SSH 能登录不代表 DDS 双向通信成功。
- Ubuntu：设置 → 网络 → 对应有线连接 → IPv4 → 手动；填分配地址和掩码。手册操作要求网关/DNS 留空，若实际接入单另有通知则按通知。应用后重新连接。
- Ubuntu 执行 `ip -4 -brief address`；对实际裁判机 IP 执行 `ip route get <实际裁判机IP>`、`ping -c 3 <实际裁判机IP>`。路由应走比赛网卡，ping 仅辅助检查，ROS 节点是否启动不能决定 IP 层 ping 是否成功。
- 所有程序/诊断终端使用同一所属赛场 ROS 域；设置 `ROS_LOCALHOST_ONLY=0`、`RMW_IMPLEMENTATION=rmw_fastrtps_cpp`。切换域后按裁判安排重启，修改终端变量不会影响已运行进程。
- 停止同席位参考车/旧节点，只留一个控制进程。以感知 → 动作 → 后续 self.last_action 完成双向验证。
- Stage 2 完整 AI 地址以本场发放值为准；模型按手册为 `deepseek-flash`，请求已设置 `max_tokens=512`、`stream=false`。每次部署重新确认本场令牌，实际资格以裁判侧本场成功记录为准。

## 2. Ubuntu 启动

从项目根目录进入 `rmtc_contestant`。以下命令在Ubuntu终端执行。正式上场必须按主办方通知修改域、席位及网关；不得沿用练习令牌。

### 第一阶段

```bash
cd /path/to/rmtc-contestant/rmtc_contestant
export ROS_DOMAIN_ID=27
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=0
export TEAM=A
export TEAM_NAME='我的参赛队'
export RMTC_STAGE=1
bash scripts/run_contestant.sh
```

### 第二阶段：练习端模拟AI

```bash
cd /path/to/rmtc-contestant/rmtc_contestant
export ROS_DOMAIN_ID=27
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=0
export TEAM=A
export TEAM_NAME='我的参赛队'
export RMTC_STAGE=2
export AI_GATEWAY='http://127.0.0.1:8080/v1/chat/completions'
export RMTC_TEAM_TOKEN='practice-A'
export AI_MODEL='practice-mock'
bash scripts/run_contestant.sh
```

模拟端返回的内容不符合本程序事件提取schema时会被丢弃，确定性策略继续运行。这只能证明降级与HTTP通信，不能证明模型理解事件。

### 第二阶段：主办方真实服务

先取得本场、本席位的正式网关、令牌、模型名；不要把令牌写进源码、截图或演示日志。

```bash
cd /path/to/rmtc-contestant/rmtc_contestant
export ROS_DOMAIN_ID='主办方本场公布值'
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=0
export TEAM='主办方分配的本场席位'
export TEAM_NAME='本队正式队名'
export RMTC_STAGE=2
export AI_GATEWAY='主办方提供的完整HTTP或HTTPS地址'
export AI_MODEL='deepseek-flash' # 手册指定；如有更新按主办方通知
read -rsp '本场本席位令牌: ' RMTC_TEAM_TOKEN; echo
export RMTC_TEAM_TOKEN
bash scripts/run_contestant.sh
```

上述路径及主办方提供的域、席位、队名、网关、模型和令牌均须按本场实际值替换；TEAM只能A/B/C/D。

### 停止与重启

节点所在终端按Ctrl+C。重新运行相同启动命令即可；程序从新的公开感知self.position定位，不依赖上次进程保存的位置。历史探索和资源记忆不会跨进程保留。新的session_id会清空上一场策略与动作缓存；重复tick重发缓存动作，不重复更新定位。

## 3. 启动练习裁判

在另一Ubuntu终端：

练习裁判需另行获取，不随本参赛包提供。以下为练习环境路径示例：

```bash
cd /path/to/rmtc_practice
./start_referee.sh --stage 1
```

第二阶段可改为：

```bash
cd /path/to/rmtc_practice
./start_referee.sh --stage 2 --bots B,C,D
```

同一端口只运行一个裁判。打开Ubuntu浏览器 http://127.0.0.1:8080 ，先启动参赛程序，再点“开始/继续”。不要让陪练占据本车A席位。裁判默认公开域27，内部域28。

网页与score文件只用于人工观赛、赛后验证，禁止作为策略输入。参赛节点仅订阅本队感知及公开公告话题。

## 4. 演示流程与证据

1. 展示阶段、席位、ROS域，隐藏令牌。
2. 启动参赛节点，确认注册队名。
3. 开始第一阶段，展示自动移动与采集；结束后展示资源价值、非法动作数、执行Tick。
4. 展示节点JSON日志中的perception、action与receipt，特别是last_action的moved和effective_direction，证明不是只有网页动画。
5. 第二阶段展示结构化任务完成情况及基础对抗。真实AI验证必须另外展示官方本场本席位成功记录及经过schema校验的模型理解效果；mock不可替代。
6. 暂停后退出节点、重启节点，再恢复裁判；检查当前tick/session_id和动作回执。
7. 重开场次，检查session_id变化且动作没有沿用旧场次。

## 5. 已知限制与上场前必检

- 当前封存版本没有人工策略切换/`decision_config`；不得现场新增该文件或借它修改策略。
- 幻术尚未完整追踪激活时本车是否中术及效果跨死亡持续；不能承诺反向行走正确。
- angel、unrivaled、pepper、pan等效果未完整策略化。
- 临时墙与永久障碍重叠无法可靠区分；当前不主动删除已观测障碍，保守策略可能绕路或不再走已消失墙位置。
- 异步模型到达时事件可能已经结算，无法撤销既成伤害。
- 当前尚无正式网关/令牌/席位；不得声称通过正式AI资格。
- 通信测试需使用比赛实际网络；VM同机DDS成功不保证异机网络免检。
- 第一阶段40/40为一张练习地图单次结果，不保证正式地图满分。

## 6. 快速自检

```bash
cd /path/to/rmtc-contestant/rmtc_contestant
python3 -B -m unittest discover -s test -v
source /opt/ros/humble/setup.bash
cd /path/to/rmtc-contestant
colcon build --packages-select rmtc_contestant
```

本指南不是正式检录合格证。实测结果和剩余缺口以 EVIDENCE_MANIFEST.md 中的证据来源、哈希和证明范围为准（归档内记录位于 evidence/development-test-record.md）。
