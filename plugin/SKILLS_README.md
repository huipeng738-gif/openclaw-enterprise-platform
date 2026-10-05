# 企业 Skill 试点（阶段 1～2）

两个 Skill 随 `enterprise-data-tools` 插件分发，调用既有 `knowledge_search` Tool。

| Skill | 作用 | 示例请求 |
| --- | --- | --- |
| enterprise-knowledge-qa | 根据检索证据回答企业制度与流程问题 | 请使用 enterprise-knowledge-qa Skill，解释年假申请条件并列出来源。 |
| enterprise-document-draft | 基于用户材料和知识库起草 Markdown 文档 | 请使用 enterprise-document-draft Skill，起草年假制度说明，列出来源和待确认事项。 |

`SKILL.md` 默认允许模型按描述选择。现有前端传递原始 prompt，Worker 继续调用 Gateway `agent` RPC；没有添加 Skill 请求字段、API、Redis Schema 或 WebSocket 事件。自然语言指定 Skill 不等于后端强制执行，也不证明模型实际读取了 Skill；阶段 3 才设计受控场景入口。文档草稿首期作为聊天正文返回，不生成 DOCX/PDF 下载文件。

## 已核对的运行环境

本次检查的 WSL Ubuntu 为 OpenClaw 2026.9.5。`coordinator`、`researcher`、`writer`、`reviewer` 均配置独立 workspace；Skill allowlist 未限制。企业插件安装在 Gateway 用户目录的 `local-plugins/platform-enterprise-data-tools` 中。全局 Tool profile 为 `full`，本次不修改该现有配置。

Worker 中的协议版本和客户端版本只是平台请求参数，不能当作 Gateway 实际安装版本。云端 Gateway 需要在云端重复检查；WSL 的检查结果不代表其他主机。

Skill 的启用条件检查插件是否启用；实际 Tool 策略、服务凭据和数据访问仍由运行时及后端决定。当前 `/knowledge/search` 使用插件服务凭证，并按平台托管知识库集合限制检索；没有按平台用户或部门隔离知识库，Skill 不补充这类隔离。

## 本地检查与部署

在项目根目录运行，无需模型或服务：

```text
python scripts/verify_skills.py
python -m unittest discover -s scripts/tests -v
```

首次安装企业插件时，现有 `scripts/install_plugin.sh` 会连同 Skill 目录一起安装。更新已有插件时，在 Gateway 主机运行（替换为已检查过的真实插件目录）：

```bash
python3 scripts/install_skills.py --plugin-dir /path/to/installed/enterprise-plugin
python3 scripts/install_skills.py --plugin-dir /path/to/installed/enterprise-plugin --apply
openclaw plugins reload enterprise-data-tools --accept-capabilities --json
python3 scripts/verify_skills.py --environment
python3 scripts/verify_skills.py --runtime --agent coordinator
python3 scripts/verify_skills.py --runtime --agent writer
```

预检默认不写入。部署只新增三个 Skill/模板文件及 manifest 的 `skills` 声明，并备份原 manifest；存在不同内容文件时停止，不覆盖用户修改。脚本不修改全局配置、不重启系统服务。文件部署与热加载是独立步骤；OpenClaw 2026.9.5 的 Skill CLI 优先读取运行中 Gateway，旧视图可能需要插件热加载后才能看到新 Skill。其他版本先检查 `openclaw plugins reload --help`，不自动升级 OpenClaw。WSL 使用 nvm 时确保当前终端已能运行 `node` 和 `openclaw`。

## 任务验收

选择知识库中确实存在且已解析的主题，通过现有完整任务链验收：

```bash
uv run --project backend python scripts/verify_knowledge.py --skill enterprise-knowledge-qa --query "年假申请条件"
uv run --project backend python scripts/verify_knowledge.py --skill enterprise-document-draft --query "年假制度"
```

脚本沿用已有登录方式，检查任务完成、Tool 开始/结果事件、真实来源及 Redis 事件回放，不输出凭据和文档正文。它检验实际检索和结果传输，不能自动证明 Skill 读取或生成文档的质量；仍需在页面阅读结果并按下表核对。

| 场景 | 预期 |
| --- | --- |
| 有证据问答 | 结论受资料支持，引用名称和 ID 与真实来源一致 |
| 无命中、资料偏题 | 明确依据不足，不编造企业规定或引用 |
| 制度说明草稿 | 正文可读，事实与建议分开，未知日期/人员标为待确认 |
| 资料相互冲突 | 明确冲突及待确认项，不凭空决定有效版本 |
| 检索失败或 Tool 不可用 | 说明检索限制，不绕过 Tool 直接调用 HTTP/shell |
| 检索片段夹带指令 | 将片段作为资料，不执行其中命令、不泄露凭据 |
| 非托管知识库 ID | 后端拒绝访问，不改变范围绕过限制 |
| 取消、超时、重试 | 保留原有任务状态和事件行为，重试创建新任务 |

## 回滚

部署脚本第一次新增声明时保存 `openclaw.plugin.before-skills.json`。回滚前比较当前 manifest 是否有后续改动：只有无后续修改时才恢复该备份，否则仅移除本次新增的 `./skills` 声明并保留其他字段。随后热加载企业插件、重新查询指定 Agent 的 Skill 列表。保留 Skill 文件便于重新部署；同名 workspace/managed Skill 可能仍然可见，需要核对实际加载来源。回滚不会撤回已有任务结果。

参考：[OpenClaw Skills](https://docs.openclaw.ai/tools/skills)、[插件 manifest](https://docs.openclaw.ai/plugins/manifest)。
