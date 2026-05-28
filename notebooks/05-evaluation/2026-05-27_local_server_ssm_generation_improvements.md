# 2026-05-27：SSM 提取与 `local_server` 联调改进记录

## 1. 这次改进的目标

本轮改进主要围绕两件事展开：

1. 把 `SSM` 提取器和 `local_server` 串起来，形成 `Vue -> SSM -> 大模型 -> San` 的可运行链路
2. 修正实际联调过程中暴露出来的提取错误，提升 `SSM` 质量，避免错误信息传给大模型

当前链路已经支持：

- 本地读取 `.vue` 文件
- 调用 `SSMFactory` 提取 `SSM`
- 将 `SSM` 发送给外部 Qwen API
- 由大模型生成 San 代码

---

## 2. local_server 侧的新增能力

### 2.1 新增本地服务骨架

在 `local_server` 下补齐了最小可用服务：

- `local_server/app.py`
  - Flask 服务入口
  - 注册 `dataset` / `evaluation` / `migration` 三类路由
  - 提供 `/health` 健康检查

- `local_server/config.py`
  - 从环境变量读取运行配置
  - 包括：`LLM_PROVIDER`、`LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`、`LOCAL_SERVER_HOST`、`LOCAL_SERVER_PORT`

- `local_server/scripts/start.sh`
  - 用于本地启动服务
  - 实际执行 `python3 -m local_server.app`

### 2.2 新增大模型 client 抽象

补充了 `client` 目录：

- `local_server/client/base_client.py`
  - 定义统一的 `generate()` 接口

- `local_server/client/qwen_client.py`
  - 负责向阿里云 Qwen 兼容接口发 HTTP 请求
  - 返回统一格式的模型输出结果

- `local_server/client/factory.py`
  - 根据 `LLM_PROVIDER` 创建具体模型 client
  - 当前默认支持 `qwen`

### 2.3 新增接口能力

在 `local_server/api/evaluation_routes.py` 中实现了两个核心接口：

- `POST /api/evaluation/extract`
  - 输入：`vue_source` 或 `vue_file_path`
  - 输出：提取得到的 `SSM`

- `POST /api/evaluation/generate`
  - 输入：`ssm`，或 `vue_source` / `vue_file_path`
  - 输出：`generation.code`，即 San 代码

兼容保留了：

- `POST /api/evaluation/run`

其行为与 `/generate` 一致。

---

## 3. 生成链路的重要调整

### 3.1 从“评估模式”改为“生成模式”

最开始的 `local_server` 设计是：

- 把 Vue 源码和 `SSM` 一起发给大模型
- 让大模型评估“这个 `SSM` 是否足够支撑迁移”

后来改成了更贴近当前目标的模式：

- **只把 `SSM` 发给大模型**
- 让大模型直接生成 San 代码

这样做的原因是：

- 当前目标不是做 `SSM` 质量评审，而是做 Vue -> San 代码生成
- 避免把 Vue 原始源码和 `SSM` 同时发给模型，减少 prompt 冗余
- 强制验证 `SSM` 本身是否足以作为中间表示驱动 San 生成

### 3.2 prompt 调整

`local_server/api/evaluation_routes.py` 中新增了 `_build_generation_prompt()`，其核心要求变成：

- 仅基于 `SSM` 生成 San 代码
- 优先遵循：
  - `san_generation_contract`
  - `template`
  - `script`
  - `styles`
  - `binding_graph`
  - `event_model`
  - `style_model`
- 尽量保留：
  - 组件名
  - props
  - data
  - computed
  - methods
  - 事件绑定
  - 子组件注册
  - scoped 样式语义

---

## 4. 提取器联调中暴露的问题

在使用下面这个样例进行联调时：

- `data/datasets/components/01_simple/step/vue/step.vue`

通过调用：

- `POST /api/evaluation/extract`

发现了两个关键问题。

### 4.1 props 名称提取错误

问题现象：

- `script.options.props[0].name` 被错误提取成整段注释 + prop 对象文本
- `binding_graph.nodes` 中的 prop 节点名也随之错误

实际错误表现类似：

- `// 可选：初始步数 initialSteps: { type: Number, default: 0 }`

而期望结果应该是：

- `initialSteps`

### 4.2 事件名提取错误

问题现象：

- `@click="addSteps"` 被错误保留成事件名 `@click`
- `san_event_syntax` 被错误生成成 `on-@click="addSteps"`

而期望结果应该是：

- `event_name = click`
- `san_event_syntax = on-click="addSteps"`

这两个问题说明：

- 主链路已经打通
- 但 `SSM` 细节字段还会直接影响 San 代码生成质量

---

## 5. 这次对提取器做的修复

### 5.1 修复 `props` 提取时被注释污染的问题

修改文件：

- `SSM/extractors/script_extractor.py`

改进点：

- 新增 `_strip_js_comments()`
- 在 `_extract_object_properties()` 进入对象属性切分前，先移除：
  - `// ...` 单行注释
  - `/* ... */` 块注释

效果：

- `props` 对象中的注释不再影响属性切分
- `initialSteps` 能被正确识别为 prop 名称

### 5.2 补充 `props.default` 提取

修改文件：

- `SSM/extractors/script_extractor.py`
- `SSM/extractors/parse_sfc.cjs`

改进点：

- 之前 `default` 没有真正提取出来，统一写成 `null`
- 现在会从对象语法里提取 `default` 字段

效果：

- `initialSteps` 的默认值现在可以提取为 `0`
- 这对后续映射到 San 的 `initData` 更有帮助

### 5.3 修复模板中 `@click` 简写指令识别

修改文件：

- `SSM/extractors/template_extractor.py`

改进点：

- 原先 `VueDirective._parse()` 对 `@click`、`:class` 这类简写形式处理不完整
- 现在区分：
  - 完整写法：`v-on:click`
  - 简写写法：`@click`
  - 绑定写法：`:class`
  - 插槽写法：`#default`

效果：

- `@click` 的 `argument` 能正确识别为 `click`
- 事件绑定信息不再被错误归类为 `custom`

### 5.4 修复 AST 路径里的事件名与 San 语法生成

修改文件：

- `SSM/extractors/parse_sfc.cjs`

改进点：

- 修正 `v-on` 指令分析时的 `event_name`
- 为 AST 路径生成正确的：
  - `event_name`
  - `san_event_syntax`

效果：

- 事件名从 `@click` 变成 `click`
- `san_event_syntax` 从 `on-@click="addSteps"` 修正为 `on-click="addSteps"`

---

## 6. 修复后的验证结果

### 6.1 提取器直接验证

使用：

- `SSMFactory(use_node_bridge=True).build_from_file(step.vue)`

验证结果：

- `prop names: ['initialSteps']`
- `prop defaults: ['0']`
- `event names: ['click']`
- `san syntax: ['on-click="addSteps"']`
- `directive args: ['click']`

### 6.2 local_server 接口回归验证

调用：

- `POST /api/evaluation/extract`

验证结果：

- HTTP 状态码：`200`
- `props[0].name = initialSteps`
- `event_name = click`
- `san_event_syntax = on-click="addSteps"`

说明：

- `local_server -> SSMFactory -> 返回 SSM` 链路正常
- 修复后的 `SSM` 已能正确反映这个简单组件的 prop 和点击事件信息

---

## 7. 当前状态总结

截至这次改进，已经具备：

1. 可运行的本地 Flask 服务
2. 可通过 `curl` 调用的 `extract` / `generate` 接口
3. 基于 `SSM` 的 San 代码生成链路
4. 环境变量配置说明和 `.env.example` 模板
5. 对典型样例 `step.vue` 的联调和提取错误修复

当前推荐使用方式：

1. 先启动 `local_server`
2. 调 `/api/evaluation/extract` 检查 `SSM`
3. 如果 `SSM` 正确，再调 `/api/evaluation/generate`
4. 检查返回中的 `generation.code`

---

## 8. 后续仍可继续优化的点

### 8.1 提取器层面

- 更全面地处理 `props` 的复杂语法
  - `validator`
  - 工厂函数默认值
  - 联合类型
- 更精准地处理事件修饰符
  - `.stop`
  - `.prevent`
  - `.native`
- 更细化地提取 `binding_graph` 中的 props/data/computed 关系

### 8.2 生成层面

- 增加“直接保存生成的 San 文件”的接口
- 增加“提取 + 生成 + 落盘”的一键流水线
- 增加失败重试和响应缓存
- 增加生成结果自动校验（例如检查 `san.defineComponent`、`initData`、`components`）

### 8.3 使用体验层面

- 支持自动加载 `.env`
- 增加单文件转换脚本
- 增加 notebooks 中的评估实验记录和效果对比

---

## 9. 一句话结论

这次改进把项目从“只有提取器原型”推进到了“可本地调用、可联调、可把 `SSM` 发给外部模型生成 San”的阶段；同时修复了 `props` 和事件提取两个关键错误，使 `SSM` 更适合作为后续 San 代码生成的中间表示。
