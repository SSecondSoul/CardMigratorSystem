# 原生浏览器分支与祖先错误链审计 v1（2026-11-13）

**这是新增负向证据，不是修复成功。** 原批仍24/30、6失败、0执行异常、1,821,544 tokens；0模型调用，无新增人工验收。不改v5或任何生产规则/Prompt/页面。

## 方法

Vue2.7.16/San3.15.6在固定受限miniDOM中实际创建并挂载Far→Near→Subject，验证真实$parent/parentComponent身份；原TaskManager业务方法及生命周期身体不改，只将Subject根render/template替换为最小节点。配置的ancestor hooks/global handler是测试应用环境，不声称既有应用已部署。Vue真的执行inBrowser分支，未调用任何私有错误函数；这不是Chrome等真实浏览器、CSS、真实存储或业务timer验收。Node宿主只观察unhandledRejection，不给被测Promise补catch。原始Vue warning组件栈、Error严格身份、hook顺序及拒绝记录完整保留。

11场景×2变体×10阶段=22运行、220快照、110比较。正常/显式返回global handler两个控制组20/20阶段在状态、事件、原始console和拒绝上匹配。其余9组仍有差异；这是同一个未闭合错误上下文契约下的9种场景，不计为9条生产缺陷。

## 已确认的源约定

- 浏览器默认无handler时，Vue记录原错误后继续下一watcher；v5无报告器则Promise拒绝并漏掉本轮settings，同步interval没有启动。
- errorCaptured从近到远、同祖先按声明顺序执行；返回false停止传播，返回true不停止。hook的this是祖先，错误subject仍是原组件。
- 捕获钩子抛错时，次生错误按该祖先及errorCaptured hook归属进入全局路径；之后原错误仍可继续被远祖捕获。
- 全局handler抛不同错误时，浏览器分支先记录次生错误，再记录原错误并继续队列；重新抛原错误只记录一次。v5目前没有该fallback。
- 业务状态完全一致也可能错误链不一致：capture_returns_true_global、near_throw_global_returns两组的所有状态阶段相等，但hook路径/事件不等。

11个独立原生San watch阳性控制均证实原Error可到达最近ancestor.error。**最近error返回true时，San仍停止，不会像Vue errorCaptured那样继续向远祖冒泡。** 因此既不能说San钩子坏了，也不能直接把errorCaptured改名成error。自定义合并Promise队列的异常还绕过了这条可用的San原生链。

## 保留的失败

[
  {
    "scenario": "browser_default",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_sync",
      "recovery_tick",
      "destroy_sync",
      "destroy_tick"
    ],
    "state_matches_all_phases": false
  },
  {
    "scenario": "near_capture_false",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_sync",
      "recovery_tick",
      "destroy_sync",
      "destroy_tick"
    ],
    "state_matches_all_phases": false
  },
  {
    "scenario": "near_bubble_far_false",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_sync",
      "recovery_tick",
      "destroy_sync",
      "destroy_tick"
    ],
    "state_matches_all_phases": false
  },
  {
    "scenario": "near_two_hooks_false",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_sync",
      "recovery_tick",
      "destroy_sync",
      "destroy_tick"
    ],
    "state_matches_all_phases": false
  },
  {
    "scenario": "capture_returns_true_global",
    "mismatch_phases": [
      "primary_tick"
    ],
    "state_matches_all_phases": true
  },
  {
    "scenario": "near_throw_far_false",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_sync",
      "recovery_tick",
      "destroy_sync",
      "destroy_tick"
    ],
    "state_matches_all_phases": false
  },
  {
    "scenario": "global_handler_throws_different",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_sync",
      "recovery_tick",
      "destroy_sync",
      "destroy_tick"
    ],
    "state_matches_all_phases": false
  },
  {
    "scenario": "global_handler_rethrows_original",
    "mismatch_phases": [
      "primary_tick",
      "repeat_sync",
      "repeat_tick",
      "recovery_sync",
      "recovery_tick",
      "destroy_sync",
      "destroy_tick"
    ],
    "state_matches_all_phases": false
  },
  {
    "scenario": "near_throw_global_returns",
    "mismatch_phases": [
      "primary_tick"
    ],
    "state_matches_all_phases": true
  }
]

上述所有原始帧/console/拒绝与应用hook事件在audit.json，无过滤成成功。未生成新San；仍使用上轮封存v5原字节。沿用其San编译通过/生产验证失败的已有记录，不声称本轮新编译。动态键/异常策略守卫继续保留。

## 验证、边界及下一步

定向测试：{"passed": 54, "failed": 0, "skipped": 0, "elapsed_seconds": 45.875, "suites": [{"suite": "test_browser_error_chain_audit_v1.py", "passed": 20, "elapsed_seconds": 1.352}, {"suite": "test_parent_watch_error_router_v5.py", "passed": 20, "elapsed_seconds": 13.138}, {"suite": "test_parent_watch_scope_guard.py", "passed": 14, "elapsed_seconds": 31.385}], "not_a_full_suite": true}；并非完整703项重跑。旧413项（含387生产/既有运行文件）、30个保留输入/Vue、页面/验收脚本及Notebook旧64单元/元数据未改；新增3诊断文件后416项，7payload封存。

下一步设计独立的“源错误上下文桥”：明确映射source ancestor hook顺序、false短路、全局handler及浏览器fallback，同时保留原/次生错误身份与组件归属。不能把所有错误直接交给San最近error钩子、吞掉异常或仅凭UI状态相等放行。浏览器/SSR策略、依赖暂停和真实应用祖先配置仍需分别证明；在此之前不生产集成、不付费模型复跑、不更新原成绩。
