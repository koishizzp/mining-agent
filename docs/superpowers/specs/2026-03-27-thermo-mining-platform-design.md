# Thermo Mining Platform Design

## Goal

把当前仓库从“Phase 1 嗜热蛋白挖掘 stage 原型”升级为一个部署在 Linux
服务器上的端到端挖掘平台。平台通过网页聊天页接收自然语言请求，
但 LLM 只负责把请求解析成受限的结构化计划；真正的执行、恢复、
日志、`tmux` 长任务和产物管理都由确定性的 runner 完成。

## Context

当前仓库已经有 `prefilter`、`MMseqs2`、`TemStaPro`、`ProTrek`、
`Foldseek` 和 `rerank` 的 Python stage 原型，但还缺少：

- 从原始 `paired-end FASTQ` 开始的上游流程
- 真正的主编排器和统一运行时状态
- 面向自然语言的网页入口
- `tmux` 托管的长任务模型
- 任意路径文件浏览和 reads 配对保护

参考仓库 `D:\esm3-agent` 已经证明了以下模式有效：

- 用显式 settings 管理运行时配置
- 用 LLM 先做受限规划，再交给确定性执行层
- 用 API/UI 统一承载对话、状态和执行结果
- 用脚本和健康检查管理长期运行服务

本设计沿用这些工程原则，但不复制其“通用代理式”执行模式。
本平台不允许 LLM 自由拼 shell 命令。

## Product Decisions

### Primary interaction model

- 主入口是部署在服务器上的网页聊天页
- 用户通过 SSH 隧道或其他安全隧道从本地电脑访问网页
- CLI 和 HTTP API 同时存在，但都共享同一套控制平面

### LLM role

- 第一版只支持 OpenAI 兼容接口
- LLM 只负责 `自然语言 -> 结构化 MiningIntent / ExecutionPlan`
- LLM 不能决定任意 shell 命令
- 执行前必须展示结构化计划并等待用户确认

### Job model

- 第一版同一时间只允许一个活跃任务
- 确认执行后，系统在服务器上创建 `tmux` session
- 浏览器、隧道和前端刷新都不影响任务继续运行

### Input model

系统必须支持三个入口：

1. `paired_fastq`
2. `contigs`
3. `proteins`

其中 `paired_fastq` 是第一优先入口，因为真实流程通常从原始 reads 起步。

### Toolchain

第一版默认外部工具栈：

- QC: `fastp`
- assembly: `SPAdes`
- ORF calling: `Prodigal`
- mining: `MMseqs2`、`TemStaPro`、`ProTrek`、`Foldseek`

## Non-Goals

第一版明确不做以下内容：

- LLM 自主 shell 代理
- 同时运行多个重任务
- 从网页直接修改服务器任意文件
- 自动做下游蛋白改造、定向进化或模型微调
- 把所有可能的装配工具都做成可选矩阵

## Architecture

系统拆成六层。

### 1. Domain layer

负责平台内的显式 schema 和状态模型：

- `InputBundle`
- `MiningIntent`
- `ExecutionPlan`
- `RunRecord`
- `StageState`
- `ArtifactIndex`

这层不依赖 Web、CLI 或 `tmux`，是所有入口共享的核心。

### 2. Planner layer

负责把自然语言请求转换成受限结构化计划。

输入：

- 用户自然语言
- 文件选择器提供的结构化路径选择
- 当前默认参数
- 历史运行上下文

输出：

- `MiningIntent`
- `ExecutionPlan`
- 面向用户的解释文本

Planner 必须始终输出 JSON 可校验结果。若 LLM 不可用或返回非法结果，
系统必须回退到确定性的规则解析器。

### 3. Control plane API

这是网页、CLI 和外部程序共享的控制平面。

它负责：

- 文件浏览
- bundle 预构建
- 自然语言规划
- 计划确认
- 任务提交
- 运行状态查询
- 停止和恢复
- 产物索引查询

### 4. Job manager

Job manager 是唯一有权启动或停止后台任务的组件。

它负责：

- 确保单活跃任务约束
- 分配 `run_id`
- 创建 `runs/<run_id>/`
- 创建和命名 `tmux` session
- 把 runner 命令注入 `tmux`
- 跟踪停止、终止和恢复

### 5. Pipeline runner

Runner 只读取落盘计划并执行 DAG，不理解自然语言。

它负责：

- 根据 `InputBundle` 类型裁剪阶段图
- 调用各 stage adapter
- 按阶段写日志、状态和产物
- 维护输入哈希和参数摘要
- 在恢复时判断哪些阶段可以跳过

### 6. Stage adapter layer

现有 `prefilter`、`MMseqs2`、`TemStaPro`、`ProTrek`、`Foldseek`、
`rerank` 代码会被保留，但改造成统一 adapter 接口。

同时新增：

- `fastp` adapter
- `SPAdes` adapter
- `Prodigal` adapter

## Input Bundles

### `paired_fastq`

字段：

- `sample_id`
- `read1`
- `read2`
- `metadata`
- `output_root`

约束：

- `read1` 和 `read2` 必须都是绝对路径
- 必须是存在的文件
- 必须通过配对规则校验
- 不允许把两个不匹配的 reads 组成同一样本

### `contigs`

字段：

- `sample_id`
- `contigs_fa`
- `metadata`
- `output_root`

### `proteins`

字段：

- `sample_id`
- `proteins_faa`
- `metadata`
- `output_root`

## File Selection and Pairing

网页文件选择器不是单文件输入框，而是服务器端路径浏览器加 bundle
构建器。

### Capabilities

- 浏览任意绝对路径
- 搜索路径
- 记住最近访问目录
- 扫描目录并批量识别样本
- 对原始 reads 做自动配对建议

### Pairing rules

第一版必须支持常见双端命名模式：

- `_1` / `_2`
- `_R1` / `_R2`
- `.1` / `.2`

识别到配对时，系统展示的是“样本包预览”，而不是直接开跑。

例如：

- sample `all`
  - `read1=/mnt/disk3/tio_nekton4/ngs_project/raw/haicangwenqun/all_1.fq.gz`
  - `read2=/mnt/disk3/tio_nekton4/ngs_project/raw/haicangwenqun/all_2.fq.gz`

### Safety rules

- 路径必须先规范化和解析符号链接
- 只有类型匹配的文件才能放进对应字段
- 若存在多个候选配对，必须要求人工确认
- 目录扫描结果必须先生成 bundle 清单，再由用户确认

## Execution Graph

### `paired_fastq`

`fastp -> SPAdes -> Prodigal -> prefilter -> MMseqs2 -> TemStaPro -> ProTrek -> Foldseek -> rerank/report`

### `contigs`

`Prodigal -> prefilter -> MMseqs2 -> TemStaPro -> ProTrek -> Foldseek -> rerank/report`

### `proteins`

`prefilter -> MMseqs2 -> TemStaPro -> ProTrek -> Foldseek -> rerank/report`

阶段图是显式 DAG，而不是拼接字符串命令。计划里必须明确：

- 起始 bundle 类型
- 将被启用的 stage 列表
- 每个 stage 的关键参数
- 每个 stage 的预期输入和输出

## Planner Semantics

### `MiningIntent`

表示用户真正想做什么，例如：

- 从哪类输入起跑
- 是单样本还是目录批量
- 使用默认参数还是某些参数覆盖
- 输出放到哪里
- 是否尝试恢复旧任务

### `ExecutionPlan`

表示系统准备怎么做，至少包括：

- `bundle_type`
- `input_items`
- `stage_order`
- `parameter_overrides`
- `output_root`
- `resume_policy`
- `requires_confirmation`
- `explanation`

Planner 的系统提示词必须强调：

- 输出只能是 schema 允许的字段
- 不要发明 shell 命令
- 不要臆造不存在的文件
- 不要跳过用户确认

## Web UI

网页由四个固定面板构成。

### 1. Chat

负责自然语言输入和解释输出。

示例：

- “从这个目录里把所有成对 reads 扫出来，用默认流程跑”
- “从 `/mnt/disk2/foo/proteins.faa` 直接开始，但 TemStaPro 阈值放宽”

### 2. Plan Review

负责在执行前展示结构化计划：

- 输入 bundle 列表
- 配对结果
- stage 图
- 参数覆盖
- 输出目录
- 将创建的 `tmux` session

用户只能在这里确认执行。

### 3. Run Monitor

负责展示唯一活跃任务的运行状态：

- 当前阶段
- 阶段状态
- 最近心跳
- 最近日志
- 产物路径
- `tmux` session 名称

### 4. Artifacts

负责查看历史运行：

- `summary.md`
- shortlist 表格
- `scores.tsv`
- `execution_plan.json`
- `runtime_state.json`
- 阶段日志

## API Surface

第一版 API 采用普通 REST 风格，并额外提供 OpenAI 兼容聊天入口。

### Core API

- `POST /api/plan`
- `POST /api/runs`
- `POST /api/runs/{run_id}/confirm`
- `POST /api/runs/{run_id}/stop`
- `POST /api/runs/{run_id}/terminate`
- `POST /api/runs/{run_id}/resume`
- `GET /api/runs/active`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/logs`
- `GET /api/runs/{run_id}/artifacts`
- `GET /api/fs/list`
- `POST /api/fs/pair-fastq`
- `POST /api/fs/scan-bundles`

### OpenAI-compatible chat API

提供受限的 `POST /v1/chat/completions` 兼容入口，但它只返回：

- 规划解释
- 结构化计划摘要
- 当前运行状态解释

它不能绕过 `ExecutionPlan` 和确认步骤直接启动执行。

## Runtime Layout

每个运行都必须有独立目录：

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

### `runtime_state.json`

这是网页和 API 的真相源，不直接依赖 `tmux` 输出。

它必须记录：

- `run_id`
- `status`
- `started_at`
- `updated_at`
- `tmux_session`
- `active_stage`
- 每个 stage 的状态、输入哈希、参数摘要、开始结束时间
- 最近错误摘要

阶段状态取值：

- `pending`
- `running`
- `succeeded`
- `failed`
- `stopped`

## tmux Execution Model

### Session creation

确认执行后，job manager 创建：

- `tmux` session: `thermo_<run_id>`
- runner command: `thermo-mining run-job --run-dir <path>`

### Why `tmux`

选择 `tmux` 的原因：

- 隧道断开时任务不受影响
- 可以直接 attach 调试
- 与 Linux 服务器使用习惯一致
- 不必把网页连接和任务生命周期绑死

### Stop semantics

提供两级停止：

- `stop`
  - 在安全点停止
  - 保留可恢复状态
- `terminate`
  - 立即终止当前 session
  - 标记异常结束

### Recovery

恢复不能只看 `DONE.json` 是否存在。恢复必须同时比较：

- 输入哈希
- 关键参数摘要
- 工具版本摘要
- stage 完整状态

只有完全匹配时才能跳过阶段。

## Configuration

第一版采用 typed settings，统一加载：

- `.env`
- 环境变量
- YAML 配置文件

配置必须覆盖：

- OpenAI 兼容 LLM 连接
- 工具路径
- 默认参数
- 数据根目录
- 结果目录
- 服务端口
- 日志路径

实现时必须移除当前仓库里会遮蔽三方库的本地 `yaml.py` 和
`requests.py` 风险，改为真实依赖和明确模块命名。

## Testing Strategy

### Domain tests

- bundle schema 校验
- paired reads 自动配对
- 路径规范化和类型校验
- stage DAG 裁剪

### Planner tests

- LLM 响应合法 JSON 解析
- LLM 非法响应回退
- 自然语言到 `ExecutionPlan` 的关键字段覆盖

### API/UI tests

- 文件浏览接口
- 计划确认接口
- 单活跃任务约束
- OpenAI 兼容 chat 接口的受限行为

### Runtime tests

- `tmux` session 创建命令
- `runtime_state.json` 状态迁移
- `stop/terminate/resume` 生命周期
- 从 `paired_fastq`、`contigs`、`proteins` 三种入口的 DAG 生成

### Smoke tests

至少要有一条本地轻量 smoke path：

- `proteins.faa -> mining`

以及一条集成 smoke path：

- `paired_fastq -> fastp -> mock assembly/prodigal -> downstream mining`

## Deployment

平台部署目标是 Linux 服务器。第一版需要提供：

- `start_web.sh`
- `start_worker.sh`
- `start_all.sh`
- `status.sh`
- `stop.sh`

这些脚本要模仿 `D:\esm3-agent` 的服务管理方式：

- 环境变量加载
- PID 文件
- 健康检查
- 日志落盘
- 端口冲突检测

## Migration From Current Repo

当前仓库里的 stage 原型不是废弃品，但需要重构定位：

- 保留 stage 业务逻辑
- 增加统一 adapter 接口
- 用新的 config/runtime/domain 层包裹
- 用新的 runner 接管执行

当前 README、STATE 和 implementation plan 都基于“从 `proteins.faa`
起跑”的旧边界。进入实施前必须更新这些文档，避免后续实现仍沿用旧假设。

## Risks and Mitigations

### Risk: 任意路径浏览导致误选文件

Mitigation:

- 用 bundle 预览代替直接运行
- 做严格配对校验和类型校验
- 强制确认

### Risk: LLM 计划不可靠

Mitigation:

- 受限 schema
- 非法输出回退到规则解析器
- 执行前人工确认

### Risk: 长任务状态和前端不同步

Mitigation:

- 以 `runtime_state.json` 为真相源
- `tmux` 只作为运行承载和调试入口

### Risk: 外部工具阶段失败难恢复

Mitigation:

- 每阶段写显式状态和输入摘要
- 把恢复逻辑做成 runner 的一部分

## Success Criteria

完成后的平台应满足：

- 用户可以从网页自然语言发起任务
- 用户可以从任意路径安全选择成对 reads 或中间产物
- 系统可以在执行前展示准确计划并等待确认
- 任务在 `tmux` 中稳定运行且可恢复
- CLI、HTTP API 和网页共享同一套控制平面
- 平台可以从 `paired_fastq`、`contigs`、`proteins` 三种入口启动
