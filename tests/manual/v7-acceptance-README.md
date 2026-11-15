# v7 通用人工验收入口

一个页面壳，通过验收项和框架配置复用，不再为每个组件复制两套 HTML。当前配置 `TaskManager · v7 + class 绑定修复 v1`。

“通用”指加载、版本校验、对照和日志工具可复用；不表示实验性的 v7 watcher 接口已自动适用于所有组件。

## 打开

在项目根目录启动静态服务器，不需要配置 LLM：

```powershell
python -m http.server 8080 --bind 127.0.0.1
```

- San：http://127.0.0.1:8080/tests/manual/v7-acceptance.html?case=task-manager-v7-class-v1&framework=san
- Vue：http://127.0.0.1:8080/tests/manual/v7-acceptance.html?case=task-manager-v7-class-v1&framework=vue

也可打开 `v7-acceptance.html`，通过顶部选择器切换框架，或点击“打开另一框架对照页”并排比较。

先分别清空本页隔离数据，再检查默认主题及明暗／紧凑模式的四种组合，然后按顶部验收清单检查任务、设置、弹窗和拖拽。清空只删除 manifest 声明的本验收项、当前框架的隔离键，不清空原应用或旧 v7 数据。

## 当前版本

- Vue：官方完整编译构建 2.7.16，复用本地已验证的资源。
- San：本地 3.15.6。
- San 候选：`data/experiments/analysis/formal_30_v4_class_binding_closure_v1_20261113/TaskManager_class_binding_offline.san`，不是原来默认始终暗黑的候选。
- 完整父模板、内联子组件、样式和业务计时器保留；加载前检查运行时和组件 SHA-256。
- 仅使用 manifest 明确选择的 `v7-parent-watch-report-only` 适配：父 watcher 私有配置入口、无源祖先捕获、全局错误只报告，并保留 Console 错误。未把这段实验适配写入生产组件。
- 正常交互检查后再按需尝试一次保存失败；可复制当前版本信息和错误日志反馈。

完整生产校验仍有 watcher 调度、动态键及异常策略阻断。页面加载不表示交互通过；人工确认也不自动修改原批次成绩或解除生产阻断。

## 以后添加验收项

1. 准备新的不可覆盖 manifest，明确组件标签、相同 props、两端组件／运行时路径及 SHA-256、存储键、隔离命名空间和验收清单。
2. 在 `v7-acceptance-config.json` 的 `cases` 添加唯一 id、名称和 manifest 路径；`default_case` 决定默认项。
3. `san_adapter` 必须显式声明：需要 v7 私有接口时选 `v7-parent-watch-report-only`，不需要时选 `none`。缺少必需接口会停止加载，不偷偷降级。
4. props 仅填组件已声明的 JSON 值，两端使用同一份，不能虚构业务数据。组件需为可直接执行的 CommonJS SFC；San 仅支持 `require('san')`，不代为打包外部子组件。
5. 存储只代理组件脚本词法作用域的 `localStorage`，不代理 `window.localStorage`、IndexedDB 或任意全局 API；新组件需先核对适用范围。入口不是任意代码沙箱。
6. manifest 及证据冻结后不要原地改文件指纹。新候选使用新 manifest，并记录用户的明确人工结果。

当前资源的准备命令是 `python -m migration_pipeline.prepare_v7_acceptance --prepare`；本次已准备完成，无须重复运行，重复运行会拒绝覆盖。

原 `vue-test-runner.html`、`san-test-runner.html`、`taskmanager-v7-*` 页面和加载器均保留未改。本次只建立入口与配置，未启动服务器、浏览器或运行测试命令；等待用户人工验证。
