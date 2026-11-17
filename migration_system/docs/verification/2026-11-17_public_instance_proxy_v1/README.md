# 公开实例代理 v1 兼容性证据

用户授权先验证内部代理、后接入。本包只记录原型阶段，**不能据此解除生产阻断**。

- compatibility.json：当前 Vue 3.5.45／San 3.15.6 的 73 个一致性场景和 4 个未解决差异。
- browser.json：两张隔离 Edge 页的实际点击与状态观察，San 页未加载 Vue；非完整视觉评估。
- runtime.cjs、compatibility.cjs、browser_probe.cjs、test_public_instance_proxy_prototype.py：本轮实现／测试原文副本。
- SHA256SUMS.json：上述 6 payload 的原始字节指纹，不包含自身和本说明。

源码副本保留在此供审计，相对模块／项目定位仍按原工程位置解释，不能直接在本归档目录运行。正常复现使用 research/public_instance_v1 下当前脚本；运行前可先核对本包指纹。Node／Vue／San／浏览器仍是本机依赖，未把本包宣称为完整操作系统环境镜像。

最终原型专项 5 项通过（14.445 秒），原公开键／控件专项 11 项通过（24.430 秒）；没有全量系统／真实模型复跑。原型测试同时确认已知差异存在、旧生产阻断保留，并不表示所有场景通过或完整任意公开键已实现。详见 ../../PUBLIC_INSTANCE_PROXY_V1.md 与系统开发记录。
