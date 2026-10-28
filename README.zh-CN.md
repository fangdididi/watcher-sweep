# watcher-sweep 监视排查

[English](README.md) | **简体中文**

一个智能体技能，用来应对人们可能向助手提出的最紧张的问题之一：*“我觉得有人通过我的手机、电脑或账号在监视我。”*

它把这种恐惧变成一次冷静、经本人授权、有边界的排查：先过安全关；把当事人描述的迹象对应到可能解释它们的渠道；先查成本低、可能性大的地方，再查少见的；每一项检查都记录查了还是没查；最后给出诚实的结论，永远不说“干净”。后续步骤把保全证据和安全计划放在删除任何东西之前。

## 为什么需要它

觉得自己被监视的人，常听到的是“你想多了”或者“全部清空吧”。前者忽视了真实的风险；后者会毁掉证据，而且当监视者和当事人同住时，还可能惊动对方。现实中大多数情况能用账号解释（密码被人知道、忘了退出的关联会话、转发规则、位置共享），一部分是追踪器，设备间谍软件反而较少。好的排查应该按这个顺序进行，并且清楚说明自己的局限。

## 功能

- **安全关。** “此刻有危险”会立即停止排查并指向求助渠道。监视者距离（`shared_home`、`knows_me`、`remote`、`state_level`、`unknown`）会改变建议内容。
- **授权关。** 设备主人未授权就拒绝；属于别人的设备也拒绝。
- **担忧卡。** 用当事人自己的话、带日期记录迹象，每条对应到 `account`、`device`、`tracker` 或 `people`。
- **自动生成检查清单。** 每个账号、每类设备（Android、iPhone、Windows、Mac、Linux）、追踪器各有检查行；怀疑高能力攻击者时，为手机加一项离线特征扫描。
- **证据规则。** 无法解释或令人担忧的结果必须原样记录所见；无害结果必须写出解释；没执行的检查必须写原因。
- **诚实的结论。** `NOTHING_FOUND_IN_SCOPE`、`LEAD`、`CONCERNING`、`INCOMPLETE`、`REFUSED/INVALID`、`SAFETY_FIRST`，各有独立退出码。
- **安全的后续顺序。** 先保全，再做安全计划（监视者在身边时），再用安全设备修改，再决定是否删除，令人担忧的发现交给专家确认。
- **私密报告和最小化分享摘要。** 摘要只有数量，没有细节。
- **过度承诺检查。** 在你准备给当事人看的文字里，标出“干净”“你没有被监视”“这证明了”“没什么好担心的”“多疑”等说法（中英文都支持）。
- 纯 Python 标准库，不联网，78 个测试。

## 安装

整个文件夹就是技能，复制到智能体读取技能的位置即可：

| 智能体 | 位置 |
|---|---|
| Claude Code | `~/.claude/skills/watcher-sweep/`（或项目内 `.claude/skills/`） |
| Codex CLI | `~/.codex/skills/watcher-sweep/` |
| Cursor | 项目内 `.cursor/skills/watcher-sweep/`，或在规则里引用 `SKILL.md` |
| 其他智能体 | 任意位置，让智能体读取 `SKILL.md` |

```bash
git clone https://github.com/fangdididi/watcher-sweep ~/.claude/skills/watcher-sweep
```

辅助脚本只需要 Python 3.8 及以上。

## 使用

对智能体说类似这样的话：“好像有人知道我发给妹妹的消息，能帮我检查一下手机和账号吗？”智能体会按 `SKILL.md` 执行。脚本也可以直接使用：

```bash
python3 scripts/sweep.py plan card.json > checks.csv        # 生成初始检查清单
python3 scripts/sweep.py check card.json checks.csv         # 结论和退出码
python3 scripts/sweep.py report card.json checks.csv report.md
python3 scripts/sweep.py share card.json checks.csv         # 只含数量的摘要
python3 scripts/sweep.py lint message.txt                   # 过度承诺检查
python3 -m unittest discover -s tests                       # 运行测试
```

## 示例

```text
$ python3 scripts/sweep.py check examples/card.json examples/checks.csv
VERDICT CONCERNING
  concern: A-chat-linked_devices: Linked web session "Chrome (Windows)" active since 2026-10-02; person has never used chat on a computer
  lead: A-mail-password_known: Ex-partner set up this mail account in 2023 and chose the first password
  lead: D-phone-accessibility: Accessibility service "System Sync Service" is on; no app with that name in the launcher

$ python3 scripts/sweep.py lint examples/draft-message.txt
line 1: 'is clean' says the device or person is clean/safe
line 1: 'not being watched' states absence as fact
line 2: 'proves' claims certainty
3 overclaim(s)
```

完整的私密报告见 `examples/report.md`。中文示例的完整讲解见 `SKILL.zh-CN.md` 中“小敏”的案例。

## 边界

这个技能不安装任何监控，不检查别人的设备，不访问或浏览特征里的地址，也不能替代专业人员。如果有人可能身处危险，请先联系当地报警电话或家暴／数字安全求助热线。

## 文件结构

```text
watcher-sweep/
├── SKILL.md                     # 技能说明（英文）
├── SKILL.zh-CN.md               # 技能说明（中文）
├── README.md / README.zh-CN.md
├── LICENSE
├── scripts/sweep.py             # plan、check、report、share、lint
├── references/
│   ├── check-catalog.md         # 每个检查项的含义（英文）
│   └── check-catalog.zh-CN.md   # 每个检查项的含义（中文）
├── examples/
│   ├── card.json                # 担忧卡
│   ├── checks.csv               # 填好的排查结果
│   ├── report.md                # 私密报告
│   ├── share.txt                # 最小化摘要
│   └── draft-message.txt        # 一条无法通过检查的消息
└── tests/test_sweep.py          # 78 个测试
```

## 许可

MIT
