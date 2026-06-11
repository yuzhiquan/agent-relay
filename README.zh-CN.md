# agent-relay

**将任意 AI 编码 CLI 串联成「一次审批」流水线。**

> 中文版 | [English](README.md)

你只需给出一个目标。一个 agent 负责规划，另一个审查方案，再一个负责实现——
全程自动衔接，无需在它们之间来回复制粘贴。唯一会停下来等你的时刻，是在提交任何东西之前的
最终确认关卡。

```
  target ─▶ ┌──────┐   PLAN.md   ┌────────┐  review.md  ┌──────────┐   ⏸ 你
            │ plan │ ──────────▶ │ review │ ──────────▶ │ implement│ ─────▶ 是否提交?
            └──────┘             └────────┘             └──────────┘
            (claude)              (codex)                 (codex)
```

每个箭头都是一次自动交接；磁盘上的文件就是传递媒介。只需改一行 YAML，
就能把任意一个环节替换成另一个 agent。

## 为什么

手动运行多 agent 工作流，意味着要把一个工具的输出反复粘贴到下一个工具里。
再加一个 agent，传递次数就成倍增长。agent-relay 让这些交接自动完成，
只在真正需要人来决定的那一步设卡。

## 支持的 agent

内置适配器：**claude**（Claude Code）、**codex**（OpenAI Codex）、
**gemini**（Gemini CLI）、**aider**，以及 **generic**——无需写代码，
直接用 YAML 包装*任意* CLI：

```yaml
- name: implement
  agent: generic
  command: ["mytool", "run", "--prompt", "{prompt}", "--out", "{output}"]
```

占位符：`{prompt} {output} {workspace} {model} {role}`。

## 安装

```bash
pipx install relaypipe         # 发布后可用
# 或者从源码安装：
pip install -e ".[dev]"
```

## 快速开始：想法 → 项目（零配置）

最快的路径。给出一个想法和一个目录，agent-relay 会规划方案、让方案在审查中循环迭代
直到足够可靠、把**最终方案**展示给你，并在你确认后把项目构建到该目录。无需 YAML，
无需 prompt 文件：

```bash
relaypipe new "a todo-list CLI in Rust with JSON persistence" -d ./todo-cli
```

执行过程：

1. **plan**——一个 agent 起草构建方案
2. **review loop**——审查者批评方案；方案被修订并重新审查，
   直到出现 `VERDICT: APPROVED` 或达到循环上限（默认 3 次）
3. **⏸ 你来确认**——打印最终方案；回答 `y` 即开始构建
4. **build**——项目在 `./todo-cli` 中创建

实用选项：

```bash
relaypipe new "..." -d ./app --agent codex          # 用 Codex 规划+审查+构建
relaypipe new "..." -d ./app --agent claude --build-agent codex   # 混用 agent
relaypipe new "..." -d ./app --max-iterations 5     # 允许更多审查轮次
relaypipe new "..." -d ./app --dry-run              # 预览将要执行的命令
relaypipe new "..." -d ./app --yes                  # CI 模式：跳过确认提示
```

如需完全控制步骤、agent 和关卡，请编写流水线（见下文）并使用 `relaypipe run`。

## 使用

```bash
# 列出可用的 agent
relaypipe agents

# 运行示例流水线
relaypipe run "Add a --json flag to the CLI" -p examples/pipeline.yaml

# 只预览命令，不实际执行
relaypipe run "..." -p examples/pipeline.yaml --dry-run

# 恢复被中断的运行
relaypipe run --resume -p examples/pipeline.yaml

# CI 模式：自动通过每个关卡
relaypipe run "..." -p pipeline.yaml --yes

# 为本次运行覆盖循环上限（优先级高于 YAML 中的 max_iterations）
relaypipe run "..." -p pipeline.yaml --max-iterations 5
```

## 示例：agent-relay 改进它自己

仓库自带一个**自托管（self-hosted）**流水线，让 agent-relay 指向它自己的代码库。
它读取本项目的 [`PLAN.md`](PLAN.md)，让一个 agent 审查某个路线图条目
（`agent-relay init`），再让另一个 agent 去实现——在你提交前暂停一次以等待确认：

```bash
# 预览整条链路（读取 PLAN.md，不调用任何 API）
relaypipe run -p examples/self-hosted/pipeline.yaml --dry-run

# 真正运行
relaypipe run -p examples/self-hosted/pipeline.yaml
```

目标已经写进了 prompt，因此无需提供位置参数形式的 target——方案文件*本身*就是输入。
这是「审查现有方案 → 实现」流程的最佳实战示例：参见
[`examples/self-hosted/`](examples/self-hosted/)。

## 流水线配置

```yaml
name: plan-review-implement
workspace: .
steps:
  - name: plan
    agent: claude
    role: plan                  # plan | review | implement | generic
    prompt_file: prompts/plan.md
    output: PLAN.md             # 此 agent 写入的内容

  - name: review-plan
    agent: codex
    role: review
    inputs: [PLAN.md]           # 喂给 prompt 的文件（{inputs}）
    output: .agent-relay/plan-review.md

  - name: implement
    agent: codex
    role: implement
    inputs: [PLAN.md, .agent-relay/plan-review.md]
    approve_after: true         # 唯一的人工关卡
```

## 审查循环（迭代至上限）

单次 plan→review 往往不够。`loops:` 块会重复一组连续的步骤，
直到审查者批准——或达到硬性迭代上限，从而绝不会无限空转：

```yaml
steps:
  - name: plan
    agent: claude
    role: plan
    inputs: [PLAN.md, .agent-relay/review.md]   # 能看到上一轮的反馈
    output: PLAN.md
  - name: review
    agent: codex
    role: review
    inputs: [PLAN.md]
    output: .agent-relay/review.md
  - name: implement
    agent: codex
    role: implement
    inputs: [PLAN.md]
    approve_after: true

loops:
  - name: plan-review
    steps: [plan, review]            # 必须连续且按流水线顺序排列
    until_step: review               # 谁的输出保存最终结论
    max_iterations: 3                # 上限（每次运行可用 --max-iterations 覆盖）
    approved_marker: "VERDICT: APPROVED"
```

它如何停下：

- **审查 prompt** 被要求以 `VERDICT: APPROVED` 或 `VERDICT: NEEDS_WORK` 结尾。
  运行器读取结论步骤的输出：批准 → 提前退出循环；否则 → 重新运行这组步骤。
- 反馈路径就是普通的文件交接：把审查的 `output` 列为第一步的 `input`，
  这样下一轮就能看到上一次的审查。
- 如果达到上限仍未批准，运行会记录 `🛑 hit max_iterations`
  并照常进入下一步（人工关卡仍是最后的兜底）。

自托管示例正是用了这套机制——参见
[`examples/self-hosted/pipeline.yaml`](examples/self-hosted/pipeline.yaml)。

## 添加新的 agent

两种方式：

1. **无需写代码**——用 `generic` 适配器配合 `command:` 模板（见上文）。
2. **写一个适配器类**——约 20 行：

   ```python
   from agent_relay.adapters.base import Agent, AgentContext, register

   @register
   class MyToolAgent(Agent):
       name = "mytool"
       binary = "mytool"

       def build_command(self, ctx: AgentContext) -> list[str]:
           cmd = [self.binary, "--prompt", ctx.prompt]
           if ctx.output_file:
               cmd += ["--out", str(ctx.output_file)]
           return cmd
   ```

   通过注册 `agent_relay.adapters` 入口点，可将它作为独立包发布——无需 fork。

## 开发

```bash
pip install -e ".[dev]"
pytest          # 测试使用 mock 的 agent——无需 API key
ruff check .
```

## 许可证

MIT——参见 [LICENSE](LICENSE)。
