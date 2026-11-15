# TaskManager v7 独立人工验收

保留原 `vue-test-runner.html` / `san-test-runner.html` 不动。

在项目根目录启动静态服务器（不用配置 LLM）：

```powershell
python -m http.server 8080 --bind 127.0.0.1
```

- Vue：http://127.0.0.1:8080/tests/manual/taskmanager-v7-vue.html
- San：http://127.0.0.1:8080/tests/manual/taskmanager-v7-san.html

首次对照先分别点击“清空本页隔离数据并重新加载”。先销毁本页组件，再只删除各自命名空间中的 `task_manager_data`，避免卸载时重新保存；不清空原应用数据，两页互不覆盖。组件代码、完整模板和样式来自冻结输入，加载前验证 SHA-256。

Vue 使用官方 npm `vue@2.7.16` 的完整编译构建；San 使用本地 `3.15.6`，候选为冻结的 `TaskManager_async_scope_v7_offline.san`。两页显式设置“全局只报告错误”应用策略；San 在父组件 `inited` 完成后、首次排队前配置私有 watcher scope。该绑定不是生产部署或任意回调纯度证明。

默认是真实命名空间存储和原业务计时器，没有最小 render 替换。顶部按钮可注入一次保存失败；这是可选异常验收，正常交互验收时先不启用。日志区保留组件错误、window.error 和未处理拒绝。

请按准备目录中的 `MANUAL_CHECKLIST.md` 检查；发现异常时发来操作步骤、Vue/San差异和首条红色报错。未启动页面或得到用户确认前，不计为人工通过，不改原批次成绩。不要将该离线候选复制覆盖生产产物。
