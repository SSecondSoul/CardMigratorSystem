# local_server 使用说明

## 1. 这个目录的目标

`local_server` 是一个本地服务层，作用不是自己完成 Vue -> San 转换，而是把已有的 `SSM` 提取器和外部大模型串起来。

它在整条链路中的职责是：

- 接收本地 `.vue` 文件路径、Vue 源码，或者已经提取好的 `SSM`
- 在需要时调用 `SSM/extractors` 生成 `SSM`
- 把 `SSM` 组织成 prompt 发给外部大模型
- 接收大模型返回的 San 代码
- 通过 HTTP API 把结果返回给调用方

可以把它理解为：

`Vue 文件 / Vue 源码 / SSM` -> `local_server` -> `SSM 提取器（可选）` -> `外部大模型` -> `San 代码`

---

## 2. 整体数据流程

### 2.1 从 Vue 文件直接生成 San 的流程

1. 调用 `POST /api/evaluation/generate`
2. 请求体中传入 `vue_file_path` 或 `vue_source`
3. `local_server` 读取 Vue 内容
4. `local_server` 调用 `SSMFactory` 提取 `SSM`
5. `local_server` 把 `SSM` 发给外部大模型
6. 外部大模型返回生成的 San 代码
7. `local_server` 把结果放到 `generation.code` 返回，并自动保存到 `data/experiments/*.san`

这条链路适合：

- 已经有现成的 Vue 文件，想直接转成 San
- 暂时不关心中间 `SSM` 是否单独落盘

### 2.2 先提取 SSM，再生成 San 的流程

1. 调用 `POST /api/evaluation/extract`
2. 请求体中传入 `vue_file_path` 或 `vue_source`
3. `local_server` 调用 `SSMFactory` 提取 `SSM`
4. 返回提取结果 `ssm`
5. 你检查 `ssm` 是否完整
6. 再调用 `POST /api/evaluation/generate`
7. 请求体中直接传入 `ssm`
8. `local_server` 直接把 `ssm` 发给外部大模型生成 San

这条链路适合：

- 想先验证提取器输出是否正确
- 想把“提取”和“生成”拆开调试
- 想复用同一个 `SSM` 多次测试不同 prompt

---

## 3. 调用逻辑

## 3.1 服务入口

文件：`local_server/app.py`

作用：

- 创建 Flask 应用
- 注册所有路由
- 提供 `/health` 健康检查接口

关键调用点：

- `local_server/app.py:9` 定义 `create_app()`
- `local_server/app.py:13` 注册 `dataset_bp`
- `local_server/app.py:14` 注册 `evaluation_bp`
- `local_server/app.py:15` 注册 `migration_bp`
- `local_server/app.py:17` 定义 `/health`
- `local_server/app.py:35` 启动服务

## 3.2 配置加载

文件：`local_server/config.py`

作用：

- 从环境变量读取本地服务配置
- 从环境变量读取外部模型配置

关键字段：

- `LOCAL_SERVER_HOST`：监听地址，默认 `127.0.0.1`
- `LOCAL_SERVER_PORT`：监听端口，默认 `8787`
- `LOCAL_SERVER_DEBUG`：是否开启 debug
- `LLM_PROVIDER`：大模型提供方，当前默认 `qwen`
- `LLM_API_KEY`：外部模型密钥
- `LLM_BASE_URL`：外部模型接口地址
- `LLM_MODEL`：模型名
- `LLM_TIMEOUT`：接口超时时间

## 3.3 请求进入 evaluation_routes

文件：`local_server/api/evaluation_routes.py`

这是当前最核心的文件，负责两件事：

- 提取 `SSM`
- 基于 `SSM` 调大模型生成 San 代码

### 提取逻辑

接口：`POST /api/evaluation/extract`

对应代码：

- `local_server/api/evaluation_routes.py:60` 定义接口
- `local_server/api/evaluation_routes.py:64` 读取 Vue 源码
- `local_server/api/evaluation_routes.py:65` 创建 `SSMFactory`
- `local_server/api/evaluation_routes.py:66` 调用 `factory.build(...)` 提取 `SSM`

### 生成逻辑

接口：

- `POST /api/evaluation/run`
- `POST /api/evaluation/generate`

这两个路由目前共用同一个函数。

对应代码：

- `local_server/api/evaluation_routes.py:72` 和 `local_server/api/evaluation_routes.py:73` 定义路由
- `local_server/api/evaluation_routes.py:79` 读取请求里是否直接提供了 `ssm`
- `local_server/api/evaluation_routes.py:81` 到 `local_server/api/evaluation_routes.py:83`：如果已经有 `ssm`，直接使用
- `local_server/api/evaluation_routes.py:84` 到 `local_server/api/evaluation_routes.py:87`：如果没有 `ssm`，先从 Vue 提取
- `local_server/api/evaluation_routes.py:89` 创建大模型 client
- `local_server/api/evaluation_routes.py:90` 生成 prompt
- `local_server/api/evaluation_routes.py:91` 到 `local_server/api/evaluation_routes.py:94` 调用外部大模型
- `local_server/api/evaluation_routes.py:96` 到 `local_server/api/evaluation_routes.py:107` 返回生成结果

### prompt 构造逻辑

- `local_server/api/evaluation_routes.py:15` 的 `_build_generation_prompt(...)`

当前实现已经改成：

- **只把 `SSM` 发给大模型**
- 不再把 Vue 源码和 `SSM` 一起发过去

也就是说，现在大模型看到的核心输入就是 `SSM`。

---

## 4. SSM 提取器是怎么接进来的

`local_server` 自己不解析 Vue AST，它复用的是 `SSM` 目录里的提取器。

关键导入：

- `local_server/api/evaluation_routes.py:7`
  - `from SSM.extractors.factory import SSMFactory`

关键调用：

- `local_server/api/evaluation_routes.py:65`
  - `factory = SSMFactory(use_node_bridge=True)`
- `local_server/api/evaluation_routes.py:66`
  - `ssm = factory.build(vue_source, file_path=source_name, source_file=source_name)`

因此职责边界很清楚：

- `SSM/extractors`：负责 Vue -> SSM
- `local_server`：负责 SSM -> Prompt -> 外部大模型 -> San 代码

---

## 5. client 目录的作用

### 5.1 `local_server/client/base_client.py`

作用：

- 定义统一的大模型客户端接口
- 约束所有模型客户端都实现 `generate()`

这样以后如果切换到别的模型提供方，API 层不需要大改。

### 5.2 `local_server/client/qwen_client.py`

作用：

- 真正通过 HTTP 请求调用外部大模型
- 当前实现兼容 Chat Completions 风格接口

关键逻辑：

- 组装 `model`、`messages`、`temperature`
- 把 prompt 发到 `LLM_BASE_URL`
- 从响应中取出 `choices[0].message.content`
- 把结果标准化成统一返回结构

### 5.3 `local_server/client/factory.py`

作用：

- 根据 `config.py` 中的 `LLM_PROVIDER` 创建具体 client
- 当前只支持 `qwen`

后续如果你想接 OpenAI、DeepSeek、文心等，主要就是在这里扩展。

---

## 6. 其他路由文件的作用

### 6.1 `local_server/api/dataset_routes.py`

当前状态：占位。

现在只有一个健康检查接口，后续可扩展为：

- 列出可测试的数据集
- 按组件名筛选测试样本
- 随机抽样某类 Vue 组件

### 6.2 `local_server/api/migration_routes.py`

当前状态：占位。

后续可扩展为：

- 一键迁移接口
- 批量转换接口
- 保存 San 代码到指定目录
- 生成迁移报告

---

## 7. 使用 local_server 的步骤

## 7.1 安装 Python 依赖

项目根目录下已经有 `requirements.txt`，至少包含 Flask。

执行：

```bash
python3 -m pip install -r requirements.txt
```

## 7.2 配置环境变量

最少需要配置：

```bash
export LLM_API_KEY="你的密钥"
```

常见可选配置：

```bash
export LLM_PROVIDER="qwen"
export LLM_MODEL="qwen-plus"
export LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
export LOCAL_SERVER_HOST="127.0.0.1"
export LOCAL_SERVER_PORT="8787"
```

## 7.3 启动服务

执行：

```bash
bash local_server/scripts/start.sh
```

这个脚本会：

- 切到项目根目录
- 执行 `python3 -m local_server.app`

对应文件：`local_server/scripts/start.sh:4` 到 `local_server/scripts/start.sh:7`

## 7.4 确认服务是否启动成功

执行：

```bash
curl http://127.0.0.1:8787/health
```

如果成功，说明 `local_server` 已经启动。

也可以检查：

```bash
curl http://127.0.0.1:8787/api/evaluation/health
```

这个接口还会告诉你：

- 当前使用哪个 provider
- 当前使用哪个 model
- `LLM_API_KEY` 是否配置完成

---

## 8. 常用调用示例

## 8.1 先提取 SSM

```bash
curl -X POST http://127.0.0.1:8787/api/evaluation/extract \
  -H "Content-Type: application/json" \
  -d '{
    "vue_file_path": "/Users/baidu-yangrunsheng/Desktop/CardMigratorSystem/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue"
  }'
```

用途：

- 先看提取出的 `SSM` 是否完整
- 适合调试提取器

## 8.2 直接从 Vue 文件生成 San

```bash
curl -X POST http://127.0.0.1:8787/api/evaluation/generate \
  -H "Content-Type: application/json" \
  -d '{
    "vue_file_path": "/Users/baidu-yangrunsheng/Desktop/CardMigratorSystem/data/datasets/components/03_complex/TaskManager/vue/TaskManager.vue",
    "instruction": "生成完整的 san 组件代码，尽量保留 methods、props、事件和子组件注册"
  }'
```

用途：

- 本地服务先提取 `SSM`
- 再把 `SSM` 发给大模型生成 San 代码
- 若未传 `output_file_path`，生成后的代码默认保存到 `data/experiments/<组件名或源文件名>.san`
- 若传了 `output_file_path`，则只保留该路径下的输出文件

## 8.3 直接传入 SSM 生成 San

```bash
curl -X POST http://127.0.0.1:8787/api/evaluation/generate \
  -H "Content-Type: application/json" \
  -d '{
    "source_file": "TaskManager.vue",
    "ssm": {
      "metadata": {"component_name": "TaskManager"},
      "template": {},
      "script": {},
      "styles": {},
      "binding_graph": {},
      "event_model": {},
      "style_model": {},
      "san_generation_contract": {}
    },
    "instruction": "输出完整可运行的 san 组件代码"
  }'
```

用途：

- 不重新跑提取器
- 直接验证某份 `SSM` 对 San 生成的效果

---

## 9. 返回结果怎么看

### `/api/evaluation/extract` 的返回

重点字段：

- `ok`：是否成功
- `source_file`：源文件名
- `ssm`：提取结果

### `/api/evaluation/generate` 的返回

重点字段：

- `ok`：是否成功
- `source_file`：源文件名
- `ssm`：本次用于生成的 `SSM`
- `generation.provider`：实际调用的 provider
- `generation.model`：实际调用的模型名
- `generation.code`：生成的 San 代码（已自动去掉 ```javascript ... ``` 代码围栏，并要求输出完整 .san 单文件组件）
- `generation.saved_file_path`：最终保存的 `.san` 文件路径（始终只保留这一份）
- `generation.usage`：模型使用量信息

如果你只关心最终代码，主要看：

- `generation.code`

---

## 10. 常见问题

### 10.1 执行 curl 前是否需要先启动服务？

需要。

因为 `curl` 请求的是 `http://127.0.0.1:8787/...`，如果 `local_server` 没启动，请求不会成功。

### 10.2 为什么调用 `/api/evaluation/generate` 时还可能触发提取器？

因为这个接口支持两种输入：

- 直接传 `ssm`
- 传 `vue_source` 或 `vue_file_path`

如果你没有直接传 `ssm`，它就会先调用 `SSMFactory` 提取。

### 10.3 现在的大模型输入里还有 Vue 源码吗？

没有。

当前版本已经改成：

- **只把 `SSM` 发送给大模型**
- Vue 源码只在本地用于生成 `SSM`

### 10.4 报错 `LLM_API_KEY is not configured` 是什么意思？

说明服务虽然起来了，但你还没有配置外部模型的 API Key。

先执行：

```bash
export LLM_API_KEY="你的密钥"
```

然后重新启动服务。

---

## 11. 推荐的使用方式

如果你现在要做 Vue -> San 转换，建议按下面顺序使用：

1. 启动 `local_server`
2. 调 `/api/evaluation/extract` 看 `SSM` 是否正确
3. 如果 `SSM` 正确，再调 `/api/evaluation/generate`
4. 查看返回里的 `generation.code`
5. 如果 San 代码质量不理想，优先检查 `SSM` 是否缺字段，再考虑调整 prompt

这样可以把问题清楚地分成两层：

- 是 `SSM` 提取不完整
- 还是大模型基于 `SSM` 的代码生成不理想

这会比直接把所有问题混在一起更容易定位。
