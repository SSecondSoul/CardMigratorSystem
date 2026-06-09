要做到真正 Vue/San DOM 树编辑距离，还差 4 块能力。你现在只完成了 San 侧的“近似渲染树快照”。

还需要做什么

Vue 渲染快照工具：新增 migration_pipeline/utils/vue_render.py，像 san_render.py 一样输出 Vue 的 dom_snapshot.tree。否则没有源端 DOM tree 可以对比。
真实浏览器渲染环境：当前 san_render.py 是 Node 沙箱里的轻量模板渲染，不是真正 San runtime + 浏览器 DOM。完整版本需要 Playwright/Puppeteer 或 jsdom + runtime。
DOM 归一化规则：Vue 和 San 渲染出来可能有运行时属性、空白文本、注释、class 顺序、动态时间等差异，需要统一清洗，否则距离会被噪声放大。
树编辑距离算法：新增 migration_pipeline/utils/dom_compare.py 或完善 ast_compare.py，输入 Vue/San 两棵树，输出：
tree_edit_distance
structure_similarity
tag_sequence_similarity
text_similarity
missing_nodes / extra_nodes / changed_nodes
建议实现顺序

第一步：做 vue_render.py，先让 Vue 侧也能输出同格式 dom_snapshot.tree。
第二步：做 dom_compare.py，先比较两棵快照树，哪怕不是浏览器真实 DOM。
第三步：把 visual_eval.py 接起来，形成 vue_render -> san_render -> dom_compare。
第四步：再升级成 Playwright 真实浏览器渲染和截图对比。
当前最合理的下一步

先实现 migration_pipeline/utils/vue_render.py。
原因：没有 Vue 侧 tree，就无法计算 Vue/San 之间的树编辑距离。