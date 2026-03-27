# Thermo Mining Control Plane MVP Design

## Goal

在现有 `thermo_mining` pipeline 基础上，新增一个可部署到 Linux 服务器上的
control-plane MVP。它提供：

- 单用户网页聊天入口
- 任意绝对路径的服务器端文件浏览与 FASTQ 配对选择
- 执行前的计划审阅与少量参数编辑
- 基于 `tmux` 的单活跃任务管理
- 运行监控、历史产物查看与基础失败解释

这个 MVP 的目标不是替换现有 pipeline，而是把现有 pipeline 包进一个受限、
可恢复、可审计、可通过网页使用的控制面。

## Relationship To Existing Docs

仓库里已经有一份更宽的设计文档：

- `docs/superpowers/specs/2026-03-27-thermo-mining-platform-design.md`

那份文档描述了完整平台方向。本 spec 只定义第一版 control-plane MVP 的明确边界，
作为后续 implementation plan 的直接输入。旧的
`2026-03-27-thermophile-mining-implementation-plan.md` 仍然只覆盖
`proteins.faa -> mining pipeline` 这一条 CLI / stage 主线，不覆盖本 spec。

## Product Boundary

### In scope

- 单页控制台网页
- `Chat` 面板
- `Plan Review` 面板
- `Run Monitor` 面板
- `Artifacts` 面板
- 文件浏览与 bundle 构建弹层
- 受限的 OpenAI-compatible chat API
- 任务创建、确认、停止、终止、恢复 API
- `tmux` 驱动的后台运行
- 统一状态源 `runtime_state.json`
- 对现有 pipeline 的 runner 封装

### Out of scope

- 多用户账号系统
- 登录、权限分级、RBAC
- 本地文件上传
- 多活跃任务或任务排队
- LLM 自由调用 shell
- 网页直接编辑任意服务器文件
- 全量计划表单编辑
- 通用生信问答助手
- 自动修复失败任务

## Locked Decisions

这些边界已经在设计讨论中明确，不再开放：

- 交付形态选 `后端完整 + 极简网页`
- 技术路线选 `FastAPI + 服务端模板 + 少量 HTMX / 原生 JS`
- 第一版是单用户、无登录系统，依赖 SSH 隧道、内网或反向代理保护访问
- 文件浏览器允许浏览任意绝对路径，不限制为预设根目录
- 同一时间只允许一个活跃任务
- `Plan Review` 只允许编辑少量字段，不做全量计划编辑
- `Run Monitor` 用短轮询，不上 SSE 或 WebSocket
- `Chat` 只做规划、状态查询和基础失败解释
- 不支持本地文件上传，所有输入都由服务器路径浏览器选择

## User Experience

### Page layout

网页采用单页控制台布局：

- 顶部状态栏
  - 当前是否存在活动任务
  - 服务健康状态
  - 配置摘要入口
- 左主栏：`Chat`
- 右侧上半：`Plan Review`
- 右侧下半：`Run Monitor`
- 底部宽栏：`Artifacts`

文件浏览器不是常驻栏，而是由 `Chat` 或 `Plan Review` 触发的独立弹层。

### Chat

`Chat` 是唯一自然语言入口。它负责：

- 接收用户自然语言需求
- 将路径选择意图引导到文件浏览器
- 展示 planner 生成的解释文本
- 回答当前运行状态和历史运行状态问题
- 基于有限上下文解释失败原因

它不负责：

- 直接启动任务
- 生成任意 shell 命令
- 修改平台配置文件
- 作为通用生信顾问回答开放式问题

### File browser modal

文件浏览器弹层负责：

- 浏览任意绝对路径
- 路径关键字搜索
- 目录扫描
- 将目录内容识别为 `paired_fastq`、`contigs` 或 `proteins`
- FASTQ 自动配对
- 生成 bundle 预览

它必须在用户确认前只做“选择和预览”，不能绕过 `Plan Review` 直接提交任务。

### Plan Review

`Plan Review` 负责在执行前展示结构化计划：

- bundle 类型
- 输入条目
- 阶段顺序
- 关键参数覆盖
- 输出目录
- 预计创建的 `tmux` session
- planner 的警告信息

第一版允许编辑的字段只有：

- `output_root`
- `resume_policy`
- `prefilter_min_length`
- `prefilter_max_length`
- `prefilter_max_single_residue_fraction`
- `thermo_top_fraction`
- `thermo_min_score`
- `protrek_top_k`
- `foldseek_topk`
- `foldseek_min_tmscore`

用户只能 `confirm` 或取消并回到聊天重新规划。

### Run Monitor

`Run Monitor` 只面向单活跃任务。它显示：

- run 状态
- 当前阶段
- 阶段状态列表
- 最近日志
- 最近错误摘要
- `tmux` session 名称
- `stop` / `terminate` / `resume` 操作

状态通过 2 到 3 秒短轮询更新。

### Artifacts

`Artifacts` 面板负责查看：

- `summary.md`
- shortlist 表格
- `scores.tsv`
- `execution_plan.json`
- `runtime_state.json`
- 阶段日志
- 最近完成的 runs

## Architecture

### 1. Web/API layer

使用 `FastAPI` 提供：

- HTML 页面
- REST API
- 受限的 `POST /v1/chat/completions`

网页和 API 共用同一套后端服务，不拆独立前端 SPA。

### 2. Planner layer

planner 输入：

- 用户聊天消息
- 文件浏览器返回的结构化路径选择
- 默认配置
- 当前活动 run 摘要
- 可选的历史 run 摘要

planner 输出：

- `assistant_message`
- `MiningIntent`
- `ExecutionPlan`
- `plan_warnings`

planner 必须受 schema 约束。LLM 输出不合法时，系统要返回明确错误，
必要时回退到规则型解析，而不是自由拼接命令。

### 3. Filesystem layer

filesystem 层负责：

- 路径规范化
- 解析符号链接
- 列目录
- 搜索
- 文件类型判断
- FASTQ 配对
- bundle 预览生成

它是“服务器路径浏览”的唯一入口，任何 run 创建都必须经过这一层产出的结构化结果。

### 4. Job manager

job manager 是唯一能真正启动后台任务的组件。它负责：

- 检查单活跃任务约束
- 分配 `run_id`
- 创建 run 目录
- 落盘计划文件
- 创建和管理 `tmux` session
- stop / terminate / resume 生命周期

### 5. Runner

runner 负责读取落盘的 run 目录并调用现有 pipeline/stage 代码。

它负责：

- 按 bundle 类型裁剪 DAG
- 维护阶段状态
- 写 `runtime_state.json`
- 比较输入哈希和参数摘要
- 在 resume 时决定哪些阶段可以跳过

runner 不接触自然语言，也不暴露网页接口。

### 6. State and artifact indexing

统一状态源是 `runtime_state.json`，不是 `tmux` 输出。

`tmux` 只承担：

- 承载长任务
- 支持 attach 调试
- 提供最后一道执行隔离

网页监控、聊天状态解释和产物面板都只读取状态文件和 run 目录。

## Core Data Models

### PathEntry

- `path`
- `name`
- `kind` (`file` or `dir`)
- `size`
- `mtime`
- `is_symlink`

### FastqPairCandidate

- `sample_id`
- `read1`
- `read2`
- `confidence`
- `needs_manual_confirmation`

### InputBundle

- `bundle_type` (`paired_fastq`, `contigs`, `proteins`)
- `sample_id`
- `input_paths`
- `metadata`
- `output_root`

### MiningIntent

表达用户真正想做什么：

- 从哪类输入启动
- 是单样本还是批量
- 是否覆盖默认参数
- 输出到哪里
- 是否意图恢复旧任务

### ExecutionPlan

- `bundle_type`
- `input_items`
- `stage_order`
- `parameter_overrides`
- `output_root`
- `resume_policy`
- `requires_confirmation`
- `explanation`

### RunRecord

- `run_id`
- `status`
- `created_at`
- `confirmed_at`
- `tmux_session`
- `run_dir`

### StageState

- `stage_name`
- `status`
- `input_hash`
- `parameter_digest`
- `started_at`
- `finished_at`
- `error_summary`

### ArtifactEntry

- `kind`
- `path`
- `label`
- `size`
- `updated_at`

## API Surface

### Filesystem API

- `GET /api/fs/list?path=<abs_path>`
- `GET /api/fs/search?root=<abs_path>&q=<keyword>`
- `POST /api/fs/pair-fastq`
- `POST /api/fs/scan-bundles`

### Planner API

- `POST /api/plan`
- `POST /v1/chat/completions`

### Run API

- `POST /api/runs`
- `POST /api/runs/{run_id}/confirm`
- `POST /api/runs/{run_id}/stop`
- `POST /api/runs/{run_id}/terminate`
- `POST /api/runs/{run_id}/resume`
- `GET /api/runs/active`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/logs`
- `GET /api/runs/{run_id}/artifacts`

## Runtime Model

### Single active run

第一版不做排队。若已存在活动任务：

- 新 run 创建或确认必须返回冲突错误
- 前端必须显式告知用户当前已有活动任务

### Run directory layout

每个 run 目录至少包含：

```text
runs/<run_id>/
  intent.json
  execution_plan.json
  bundle_manifest.json
  runtime_state.json
  tmux.json
  stage_logs/
  artifacts/
  reports/
    summary.md
```

### tmux execution

确认执行后，job manager 创建：

- `tmux` session，例如 `thermo_<run_id>`
- runner 命令：`thermo-mining run-job --run-dir <path>`

用户不能直接编辑 `tmux` 命令或 shell 片段。

### Stop semantics

- `stop`
  - 在安全点停止
  - 保留可恢复状态
- `terminate`
  - 立即终止后台任务
  - 标记为异常结束

### Resume semantics

resume 不能只看 `DONE.json` 是否存在。必须比较：

- 输入哈希
- 关键参数摘要
- 工具版本摘要
- 阶段完整状态

只有完全匹配的阶段才允许跳过。

## Safety Rules

### Filesystem safety

- 浏览任意绝对路径前先做规范化
- 解析符号链接后再判断真实路径
- 所选路径必须存在
- 必须符合目标输入类型
- 若 FASTQ 自动配对存在多候选或冲突，必须人工确认

### Planner safety

planner 只能输出 schema 允许的字段，不能：

- 发明 shell 命令
- 绕过 `Plan Review` 直接触发执行
- 声称不存在的文件存在
- 修改服务器任意文件

### Chat safety

聊天接口只允许：

- 规划解释
- 当前 / 历史 run 状态解释
- 基础失败解释

它不允许：

- 通用开放问答
- 自动下发任务
- 自动修复和自动重试

## Failure Explanation

第一版失败解释是受限功能，不是 agent 诊断系统。

输入来源仅限：

- `runtime_state.json`
- 最近阶段日志片段
- 阶段名
- `error_summary`

输出目标仅限：

- 失败发生在哪个 stage
- 一句到几句可读解释
- 建议查看哪个日志或产物路径

第一版不提供自动修复建议生成器，不提供自动重试策略。

## Testing Strategy

### Domain tests

- 路径规范化
- 文件类型校验
- FASTQ 自动配对
- bundle 构建
- plan schema 校验

### API tests

- 文件浏览接口
- plan 生成接口
- run 生命周期接口
- 单活跃任务冲突
- 受限 chat 接口

### Runtime tests

- `tmux` session 创建命令
- `runtime_state.json` 状态流转
- stop / terminate / resume
- 从三种 bundle 类型裁剪 DAG

### UI tests

- Chat 到 Plan Review 的流转
- Plan Review 小范围字段编辑
- Run Monitor 轮询更新
- Artifacts 列表渲染

### Smoke tests

- `proteins.faa -> planning -> confirm -> mock runner`
- `paired_fastq -> pairing -> plan -> mock runner`

## Deployment Assumptions

- 部署目标是 Linux 服务器
- 平台通过 SSH 隧道、内网或反向代理暴露给单用户
- 第一版不做应用内登录
- 服务需要长期运行并能稳定管理 `tmux`

## Success Criteria

MVP 完成后必须满足：

- 用户可通过网页自然语言发起规划
- 用户可通过服务器端路径浏览器选择任意绝对路径输入
- FASTQ 配对结果在执行前可预览和确认
- 用户可在执行前审阅计划并修改少量字段
- 平台一次只能运行一个活跃任务
- 确认后任务在 `tmux` 中稳定运行
- 网页可查看活动任务状态、日志和产物
- 聊天界面可解释当前状态和基础失败原因
- 所有状态都能从 run 目录和 `runtime_state.json` 恢复
