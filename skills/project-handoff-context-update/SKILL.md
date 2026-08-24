---
name: project-handoff-context-update
description: 当用户要求更新 `migration_pipeline/stages/真正 Vue/项目快速上下文.md`，或需要把当前 Vue->San 迁移项目进度、最近改动、实验报告、当前问题和下一步任务整理成新对话交接上下文时，使用这个 skill。
---

# 项目交接上下文更新 Skill

当需要维护 `migration_pipeline/stages/真正 Vue/项目快速上下文.md` 时，使用这个 skill。目标是让新的 AI 对话能快速接手项目，而不是重新翻完整仓库。

## 目标文件

默认更新：

```text
migration_pipeline/stages/真正 Vue/项目快速上下文.md
```

这个文件是交接入口，不是完整设计文档。更新时要让它回答五件事：

- 项目是什么、主链路是什么
- 当前已经做到哪里
- 最近改了什么，为什么改
- 当前还有什么问题或不可信报告
- 下一步最该做什么

## 更新前先收集事实

不要只根据聊天记忆改文档。优先读取这些信息：

- 当前目标文件：`migration_pipeline/stages/真正 Vue/项目快速上下文.md`
- 当前代码改动：`git diff -- <相关文件>`
- 当前状态：`git status --short`
- pipeline 文档：`migration_pipeline/README.md`
- 最近实验报告：`data/experiments/repair_reports/*.json`
- 最近生成/修复产物：`data/experiments/pipeline/*.san`

如果涉及具体模块，按需读取：

- `migration_pipeline/orchestrator.py`
- `migration_pipeline/utils/repair_prompt.py`
- `migration_pipeline/stages/validate.py`
- `migration_pipeline/stages/visual_eval.py`
- `migration_pipeline/utils/vue_render.py`
- `migration_pipeline/utils/san_render.py`
- `migration_pipeline/utils/san_compile.py`
- `local_server/api/evaluation_routes.py`

## 必须更新的内容

更新目标文件时，至少检查这些栏目是否过期：

- `当前阶段进度摘要`
- `最近改动记录`
- `当前实验状态`
- `当前已知问题`
- `下一步任务`
- `Windows 本地操作提醒`
- `关键边界提醒`

如果旧文档中出现已经完成的事项，例如“多轮 repair 闭环待完成”，要改成当前真实状态，并标注旧文档不再可信的部分。

## 写作原则

- 以源码和最新实验报告为准，旧笔记只能作为背景。
- 明确区分“已验证事实”和“下一步假设”。
- 对失败报告要说明是否仍可信；如果报告是在某个 bug 修复前生成的，要明确提醒需要重跑。
- 操作命令要优先给 Windows PowerShell 版本，因为当前实际操作环境是 Windows。
- 保留关键路径，方便新对话直接打开文件。
- 不要把完整 README 或设计文档复制进来；只写交接所需的高信号信息。

## 推荐结构

目标文件推荐包含：

```text
# 项目快速上下文

更新时间
使用方式
项目定位
建议阅读顺序
当前阶段进度摘要
最近改动记录
当前实验状态
当前已知问题
下一步任务
Windows 本地操作提醒
关键边界提醒
当前环境约定
```

结构可以按实际情况调整，但必须保证“新 AI 下一步该做什么”清楚可执行。

## 当前项目中特别重要的交接点

维护本文档时，要特别留意这些容易过期的事实：

- `migration_pipeline` 已经有多轮 repair 闭环，入口是 `run_pipeline.py`。
- `run_pipeline.py` 会导出 `repair_history.json`。
- `visual_eval.py` 当前是轻量 DOM tree 结构评估，不是真实浏览器截图/像素评估。
- `local_server` 是 LLM 服务提供方，`migration_pipeline` 是流程消费和编排方。
- Windows 下启动 `local_server` 不用 `bash local_server/scripts/start.sh`，应使用 `python -m local_server.app`。
- `LLM_API_KEY` 必须配置在启动 `local_server` 的同一个 PowerShell 窗口。

## 验证

更新后至少做：

- 重新读取目标文件，确认中文编码正常。
- 检查文档中提到的关键路径是否存在。
- 用 `git diff -- migration_pipeline/stages/真正 Vue/项目快速上下文.md` 复查是否只更新了交接信息，没有误删重要背景。

如果同时新增或修改了本 skill，也复查：

```text
skills/project-handoff-context-update/SKILL.md
```

确保 frontmatter 中的 `name` 和文件夹名一致。
