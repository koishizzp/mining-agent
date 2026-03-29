# Project State: all-ai-bio

**Status:** paused
**Created:** 2026-03-27
**Canonical local repo root:** `D:\all-ai-bio`
**GitHub origin:** `https://github.com/koishizzp/all-ai-bio`

## 这是什么项目

这是一个以温泉微生物数据为核心的长期生物计算项目。当前本地仓库 `D:\all-ai-bio` 是代码、设计文档、实施计划的源头仓库，会先在本地整理和提交，再推送到 GitHub，然后由服务器上的克隆仓库拉取执行。重计算、批处理、结构搜索、模型推理主要发生在服务器端，而不是本地 Windows 机器。

这个仓库当前不是装配仓库本身，而是逐步演化为“挖掘 -> 改造 -> 设计 -> 进化 -> 微调”的统一编排与记录仓库。

## 你的核心目标

### 1. 挖掘

从温泉宏基因组原始数据中，尽可能高效且尽量准确地挖掘广义嗜热蛋白，而不是只盯某个单一功能家族。用户当前手上的主要输入还是类似 `Unknown_CZ113-001R0001_good_1.fq.gz` 这样的原始 reads，因此真正进入本仓库主线的输入，应该是上游装配和注释后得到的 `contigs.fa` 或 `proteins.faa`。

### 2. 改造 / 设计 / 定向进化

在挖掘得到的 shortlist 之上，继续做蛋白改造、重新设计、甚至定向进化闭环。这个阶段会更依赖结构建模、生成模型、约束设计和实验反馈，但当前还没有开始实施。

### 3. 用温泉数据库微调生物大模型

最终希望利用温泉细菌、温泉蛋白、环境标签、结构与功能信息构建一个高价值专有数据库，用于对当前生物大模型进行后续微调或对齐，使模型更理解高温生态位中的蛋白规律。这个目标已经明确，但目前不是第一阶段。

## 当前阶段边界

当前明确处于 **Phase 1: 泛嗜热蛋白挖掘**。

边界已经确认如下：

- 装配和基础注释由用户在仓库外部自行负责
- 本仓库第一阶段从 `proteins.faa` 和样本 metadata 开始
- 当前重点是建立高通量、可恢复、可审计的挖掘流水线
- 还没有开始实现改造、定向进化或大模型微调

## 已确认的技术路线

已经确认通过的 Phase 1 主路线是混合级联，不走纯 `Foldseek` 主线，也不走纯 `ProTrek` 主线。

确认通过的流程是：

`predicted proteins -> prefilter -> MMseqs2 compression -> TemStaPro prescreen -> ProTrek rerank -> Foldseek confirm -> evidence-integrated tiered shortlist`

核心原因：

- 目标是“泛嗜热蛋白”，边界模糊，不能依赖单模型
- 数据规模大，必须先用廉价步骤压缩候选空间
- `ProTrek` 更适合广义召回与重排
- `Foldseek` 更适合结构确认
- 昂贵的结构预测和后续生成设计应该推迟到 shortlist 足够小时再做

## 当前已完成内容

### 已完成设计文档

- 设计文档路径：`D:\all-ai-bio\docs\designs\2026-03-27-thermophile-mining-design.md`
- 当前中文版本提交：`2925604`

该文档已经固定了：

- 为什么当前阶段聚焦“挖掘”
- 为什么采用混合级联路线
- 每一层的职责与目标
- 仓库目录设计
- 必需与可选工具优先级
- 第一周执行重点
- 失败点、断点续跑、质量控制和 shortlist 分层标准

### 已完成实施计划

- 计划文档路径：`D:\all-ai-bio\docs\plans\2026-03-27-thermophile-mining-implementation-plan.md`
- 当前提交：`c178163`

该计划已经把 Phase 1 拆成了可执行任务：

- 项目骨架与配置加载
- manifest / FASTA I/O / `DONE.json`
- prefilter stage
- `MMseqs2` 去冗余包装层
- `TemStaPro` 预筛包装层
- `ProTrek` 本地索引与文本查询桥接
- `Foldseek` 确认层客户端
- 最终合分、Tier 分层和报告
- 主编排器、断点续跑和 CLI

## 当前尚未开始的部分

- 还没有开始写 Phase 1 的实际代码实现
- 还没有建立独立 worktree
- 还没有把计划中的 Task 1 到 Task 9 逐个落地
- 还没有补 `.planning/PROJECT.md`、`.planning/ROADMAP.md` 等更完整规划文件
- 还没有建立服务器端仓库路径记录

## 服务器与本地的关系

这是非常关键的上下文，后续任何代理都不应弄混：

- 本地 Windows 仓库 `D:\all-ai-bio` 是源头整理仓库
- GitHub 仓库 `https://github.com/koishizzp/all-ai-bio` 是同步中枢
- 服务器上的仓库克隆是执行仓库
- 应遵循“本地提交 -> push 到 GitHub -> 服务器 pull 执行”的基本关系

如果未来在服务器上继续本项目，应该优先确认服务器克隆仓库的绝对路径，并把它补进本文件。

## 已知服务器环境

以下信息来自 `D:\all-ai-bio\fwq.txt`：

- CPU: `AMD EPYC 9654`, `384` 线程
- 内存: `3.0 TiB`
- GPU: `NVIDIA GeForce RTX 4090 D`, `48 GiB`
- 大容量存储可用：`/mnt/disk1`、`/mnt/disk2`、`/mnt/disk3`、`/mnt/disk4`

这意味着：

- CPU 与内存不是当前主要瓶颈
- 真正要节省的是 GPU 时间和无效结构推理
- Phase 1 设计必须强调“先压缩候选，再把 GPU 留给高价值目标”

## 已知相关工具与当前角色

### Phase 1 挖掘主线中保留

- `Foldseek` / `foldseek-agent`
- `ProTrek`

### 当前阶段不放进关键路径

- `esm3-agent`
- `protein-binder-agent`

这些工具不是没用，而是更适合 Phase 2 以后做改造、生成和进化。

## 当前重要约束

- 当前目标不是装配优化，而是“挖掘效率和准确性兼顾”
- 当前目标不是单一家族，而是“泛嗜热蛋白”
- 当前仓库内的设计与计划都默认从 `proteins.faa` 开始
- 当前不应把 binder design 需求混进 Phase 1 主线
- 当前不应直接跳到模型微调实现，除非 Phase 1 和后续 shortlist 已经稳定

## 后续推荐执行顺序

1. 在新的 worktree 中实现 Phase 1，而不是直接在 `main` 上开发
2. 先按计划落地 Task 1 到 Task 3，跑通仓库骨架、I/O 和 prefilter
3. 再实现 `MMseqs2` 与 `TemStaPro`，形成便宜的候选压缩链路
4. 再桥接 `ProTrek` 和 `Foldseek`
5. 最后做合分、Tier 分层、报告与 CLI

## 推荐优先使用的技能

如果后续代理要继续这个项目，建议优先考虑以下 skill：

- `session-awareness`
  - 在恢复会话、切换 worktree、问“当前进展是什么”时优先使用
- `context-handoff`
  - 在停止前更新本文件或生成新的 handoff 文档
- `brainstorming`
  - 当目标从“挖掘”切换到“改造 / 设计 / 微调”时重新设计
- `writing-plans`
  - 当进入新的多步骤子项目时先写计划
- `executing-plans`
  - 当需要按既有计划落地实现时使用
- `verification-before-completion`
  - 在声称功能完成前做验证
- `using-git-worktrees`
  - 在正式开始实现前建立隔离 worktree

## 建议读取顺序

后续任何代理或新 worktree 在继续项目前，建议按这个顺序读取：

1. `D:\all-ai-bio\.planning\STATE.md`
2. `D:\all-ai-bio\docs\designs\2026-03-27-thermophile-mining-design.md`
3. `D:\all-ai-bio\docs\plans\2026-03-27-thermophile-mining-implementation-plan.md`

如果是在服务器的克隆仓库中继续工作，则应把上述路径中的仓库根路径替换为服务器上的实际 clone 根目录。

## 当前 open questions

- 服务器上的仓库 clone 绝对路径还没有记录
- `MMseqs2`、`TemStaPro`、`ProTrek`、`Foldseek` 在服务器上的最终安装路径还没有纳入配置文件
- 未来用于模型微调的数据结构和标签体系还没有设计
- shortlist 进入改造与定向进化后的评价闭环还没有设计

## 当前 gotchas

- `fwq.txt` 当前仍是未跟踪文件，提交时不要误带
- Windows PowerShell 输出中文时可能显示乱码，但文件内容本身应按 UTF-8 保存
- 当前已经有设计文档和计划文档，不要绕过它们直接拍脑袋重写路线
- 如果后续 scope 从“挖掘”扩展到“改造 / 微调”，应该新开设计文档，不要硬塞进 Phase 1

## 可以直接复制使用的同步命令

本地推送：

```bash
git push origin main
```

服务器拉取：

```bash
git pull origin main
```

开始实现前建议先建新 worktree，而不是直接在 `main` 上改代码。
