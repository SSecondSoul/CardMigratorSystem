# CardMigrator 五个 TAB 效果图

使用内置 image_gen 工具生成。所有数据均为设计示例，未修改前端源代码。

## 共同提示词

Use case: ui-mockup. Create ONE high-resolution Chinese desktop UI screenshot as the next screen in the exact same CardMigrator app as the attached reference. The reference is the visual design authority: retain its layout geometry, left nav, top header, task title and status, six-stage pipeline, recent-task panel, spacing, typography, colors, icons and overall 16:10 canvas. White panels on #F5F7FA, deep slate text, teal #087F8C selected states, green pass and amber untested, refined line icons and thin borders. No perspective or laptop frame. This is a coherent set of different tabs of ONE product, not a new visual design. Prioritize crisp readable Chinese text and realistic usable content.

Persistent outer shell must match reference: CardMigrator / 前端技术栈迁移, 新建迁移 button, left nav 迁移工作台 active, 任务记录, 实验对比, bottom 开发验证, 设置与连接. Breadcrumb 迁移工作台 / 搜索结果卡片. Header badge 设计预览 · 示例数据, 服务已连接. Title 搜索结果卡片迁移, green 检查通过 and amber 待人工验收 chips. SearchCard.vue · Vue → San · 2026-11-18 10:24. Top 下载报告 and 下载 San 代码 buttons. Pipeline 源码解析 / SSM 提取 / 代码生成 / 结构校验 / 视觉评估 / 自动修复, 已修复 2 轮 / 最多 3 轮, 本次执行已结束. Recent tasks same four rows SearchCard.vue selected, UserProfile.vue 评估中, FilterBar.vue 待复核, Pagination.vue 检查通过. Task info SSM + 自动修复, 模型调用 3 次, Token 用量 12,480, 总耗时 1 分 42 秒.

Keep report panel at right with EXACT same tab order "视觉对比", "结构与语义", "San 代码", "修复记录 2", "人工验收". Select only the requested tab with teal text and bottom underline, the other four neutral. Replace ONLY the report content below that tab bar as specified next. All data is sample data, not empirical claims. No English filler, no marketing banners, no giant raw JSON blocks, no tiny unreadable crammed text. Every metric across tabs consistent: structure 98.6%, UI restoration 97.8%, SSIM 0.982, differing pixels 2.2%, automated checks passed for configured scope, representative interaction not tested, manual acceptance not recorded.

## 视觉对比

Selected tab: 视觉对比. Refine and reproduce the reference visual comparison view. Four compact metric tiles: 结构一致性 98.6% 达到阈值 >95%; UI 还原度 97.8% 达到阈值 >95%; 像素差异率 2.2% 目标 <5%; 代表性交互 未测试 尚未配置交互场景 (amber). Big card 界面还原对比, 同一视口 · 1440×900 · SSIM 0.982, right segmented 并排 (active) / 叠加 / 差异. Two equal screenshots 源界面 · Vue and 迁移结果 · San showing identical search card with small landscape photo, 探索更高效的前端开发, two-line supporting text, Vue and 组件化 tags, 查看详情 button. Mark subtle 2px spacing difference in San tag with amber outline and 1 marker. Below compact table 需要关注的差异 · 1项 with columns 位置 / 差异说明 / 影响 and row 标签区域 / 右侧间距相差2px / 低. Bottom pale amber inline notice 交互尚未测试，自动检查通过后仍需人工验收。 with 去验收 →. Full polished screenshot, not collage.

## 结构与语义

Selected tab: 结构与语义. Show an approachable structured quality inspection screen grounded in SSM four dimensions. Top compact summary: 结构一致性 98.6%, 已匹配节点 71/72, 阻断问题 0. Below four compact dimension chips with simple line icons: 模板结构树, 数据绑定图, 事件交互表, 样式特征集, first selected pale teal. Main card title 结构映射 and subtitle 源 SSM 与目标 AST / DOM 对照, right outline 下载 SSM button. Side-by-side readable tree panels 源 SSM and 目标 San DOM, matching nested nodes "SearchCard", "article.search-card", "img.cover", "div.content", "h3.title", "p.description", "div.tags", "button.detail". Teal thin connectors or aligned highlighted rows map corresponding div.tags nodes. Most checkmarked green, selected div.tags pale teal and small amber 提示 marker for style discrepancy only; no structural failure. Below a compact table 语义检查结果, columns 检查项 / 覆盖情况 / 结果, rows 数据绑定 / title、description、tags / 通过; 事件映射 / @click → on-click / 静态映射通过; 样式特征 / scoped CSS 已转换 / 1项轻微差异. Bottom unobtrusive amber notice 静态事件映射通过不代表运行交互已验证。Right 查看视觉差异 →. Keep tree and table readable and sophisticated, no huge node graph, no fabricated semantic equivalence claim.

## San 代码

Selected tab: San 代码. Primary content is a polished developer code review screen, light theme matching reference. Small top file bar with file icon "SearchCard.san", green "编译通过", neutral "最终接受版本 · 第2轮", right outline "复制代码" and teal "下载文件". Under it a subtle two-option switch 最终代码 (selected) / 与初始版本对比. Main bordered editor with narrow file tree left about 150px showing "迁移产物", SearchCard.san selected, styles.css, migration-report.json, ssm.json; editor right occupying remaining width with line numbers and tasteful syntax highlighting (teal tags, slate text, muted blue strings, no dark theme). Readable coherent San source excerpt about 20 lines:
import san from 'san';
export default san.defineComponent({
  template: `
    <article class="search-card">
      <img class="cover" src="{{imageUrl}}">
      <div class="content">
        <h3>{{title}}</h3>
        <p>{{description}}</p>
        <div class="tags">
          <span s-for="tag in tags">{{tag}}</span>
        </div>
        <button on-click="openDetail">查看详情</button>
      </div>
    </article>
  `,
  initData() {
    return { title: '', description: '', tags: [] };
  },
  openDetail() { this.fire('detail'); }
});
Tiny line marker at tags row indicates repair, no giant diff. Bottom editor status "San · UTF-8 · 只读产物". Below compact checks row "静态检查 通过" "编译运行 通过" "代表性交互 未测试" and a pale neutral informational strip "下载前建议完成交互与人工验收。" right 去验收 →. This is source inspection, not arbitrary code editing; do not include fake save or deployed status. Prioritize gorgeous readable editor with realistic code.

## 修复记录

Selected tab: 修复记录 with badge 2. Build a clear bounded self-repair audit view, easy for developers to understand cause and improvement. Top compact summary row "已修复 2 / 3 轮", "UI 还原度 91.3% → 97.8%", "结构一致性 93.1% → 98.6%". Main card "修复过程" with small right "展开全部" button. Left narrow vertical timeline three numbered nodes 初始生成, 第1轮修复, 第2轮修复; last node selected teal with green 已接受. To its right two stacked repair summaries, enough whitespace:
"第1轮 · 规则修复" subtitle "修正事件映射与列表指令"; compact before/after chips structure 93.1%→98.6%, UI 91.3%→95.1%; 2 changed files, status 已保留.
"第2轮 · 模型修复" subtitle "修正卡片布局与标签样式"; structure 98.6%→98.6%, UI 95.1%→97.8%; small teal 当前接受版本.
Below focused detail of selected 2nd round: section "修改依据" simple amber-highlighted finding "卡片内容区间距偏大，标签对齐存在偏差". Side-by-side compact light code diff labelled 修复前 / 修复后, CSS .content { padding: 20px; gap: 16px; } vs .content { padding: 16px; gap: 12px; }, muted red removed lines and pale green added lines. Footer decision "停止原因：已达到配置阈值" green check; small text "仍有1项低影响视觉差异，代表性交互未测试。" right 查看最终代码 →. NO fourth or unlimited rounds, no generic meaningless chart, no complete functional equivalence claim. Keep clean compact audit evidence and clear iteration sequence.

## 人工验收

Selected tab: 人工验收. Design an excellent manual QA form for the same task, pending state with no invented saved acceptance. Top pale amber notice "自动检查已通过，人工验收尚未提交。" and small subtext "请结合实际业务场景检查，验收记录独立保存。". Main content two columns within report panel, left wider about 60% white form and right narrower supporting context. Form header "验收记录" with tiny "待填写" badge. First "验收结论" two large radio cards "通过验收" and "需要修改" both UNSELECTED neutral empty radio circles (no green pass selection). Next "检查清单" with three unchecked checkboxes "页面布局与样式符合预期", "数据展示与边界状态正常", "关键交互已手动验证". Small hint "自动交互未测试，请手动补充验证。". Two parallel labelled numeric inputs "人工修改行数" placeholder "未知可留空" unit 行 and "验收耗时" placeholder "未知可留空" unit 秒. Label "验收范围与备注" large multiline blank textbox placeholder "记录验证场景、发现的问题及修改说明…". Bottom teal button "提交验收记录", secondary "重置"; helper "提交后追加记录，不覆盖自动评估结果。" Keep form fields comfortably sized and no fake saved toast.
Right reference card "自动评估摘要": 结构一致性 98.6% green; UI还原度 97.8% green; 编译运行 通过 green; 代表性交互 未测试 amber. Then "待关注事项" amber item "标签区域间距相差2px" with 查看差异 link. Below small "历史验收记录" empty state fine-line document icon and "暂无人工验收记录". Make genuine user completion workflow, clear required decision and practical optional effort fields. Avoid making a screenshot of already accepted state.

