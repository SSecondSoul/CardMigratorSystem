# 部分实现证据，不是生产放行

2026-11-17，san-business-instance-v1。最终数据由 scripts/verify_san_business.py 在本地隔离浏览器生成。summary.json、三个 unittest 日志、五份探针报告和 replay/ 是同一实现绑定的本轮证据；implementation/ 保存执行前源码字节，执行后检查无漂移。SHA256SUMS.json 覆盖本目录全部 payload（不含它自己），旧证据不变。

18 项新专项、41 项旧代理回归、11 项生产公开键边界检查均通过；它们不是 70 个迁移样本。replay/ 是一个冻结商品筛选源／原生成模板的派生新产物及 11 步动作检查，初始和每步真实 DOM／样式／控件状态一致，UI 100%，SSIM 1。静态通过范围仅为规范源脚本／业务接收器绑定；模板 key 身份投影有编译验证前提，DOM 原始属性不投影、不放宽。截图为最终动作后的截图，不宣称逐动作均有像素／SSIM 检查。

原始失败样本来自实验仓库冻结文件，复制在 source.vue／original-target.san 中；离线运行时自身不依赖父工程。历史结果和费用不回写，不生成新的迁移通过率。

intermediate/attrs-before.json 是本轮修复前真实观察，记录连字符 props／attrs 差异，**不是当前源码通过报告，也没有修复前完整源码副本**，不能拿它冒充可逐字节重放的最终实现证明。其他早期未封存的中间记录、Windows 换行不一致导出不放入最终证据冒充通过。

主 Worker、生成／验证／修复／候选门尚未接入；组件树、祖先错误捕获、slots／动态 attrs／ref、复杂父事件及部分调度／副作用顺序仍未闭合。full_contract_complete=false，production_admission_eligible=false。无真实模型调用、LangSmith、训练、实际业务库／队列写入或 commit/push。
