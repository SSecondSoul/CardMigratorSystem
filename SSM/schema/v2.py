"""
SSM Schema v2

面向 Vue -> San 组件迁移的数据抽取 schema。该 schema 的输出会直接作为大模型生成 San 组件的依据，
因此字段设计重点覆盖模板结构、数据绑定、事件交互、样式特征、组件通信与迁移约束。
"""

SSM_SCHEMA_VERSION = "2.0"

SSM_SCHEMA = {
    "schema_version": "2.0",
    "schema_name": "San Source Model",
    "schema_goal": "将源 Vue 单文件组件抽取为可指导大模型稳定生成等价 San 组件的结构化中间表示。",
    "component_identity": {
        "component_id": "来自 dataset_manifest.json 的 id，例如 todo_list",
        "component_name": "组件英文名或源码 name，例如 TodoListPro",
        "display_name": "组件中文名，例如 待办事项列表",
        "complexity": "simple | medium | complex",
        "source_framework": "Vue",
        "target_framework": "San",
        "dataset_path": "组件目录相对路径，例如 components/02_medium/TodoList/",
        "source_files": {
            "vue_file": "源 Vue 文件名",
            "san_file": "已有目标 San 文件名，可为空或用于对齐验证"
        },
        "migration_status": "vue_ready | san_ready | vue_ready,san_ready | unknown"
    },
    "feature_profile": {
        "complexity_score": {
            "template": "模板复杂度评分，来自 complexity_tags.json",
            "data_logic": "数据与计算逻辑复杂度评分",
            "interaction": "交互复杂度评分",
            "styling": "样式复杂度评分",
            "communication": "父子通信与事件复杂度评分",
            "total_score": "总分",
            "level": "simple | medium | complex"
        },
        "pattern_tags": {
            "templates": {
                "has_v_for": False,
                "has_v_if": False,
                "has_v_bind": False,
                "has_v_on": False,
                "has_slot": False
            },
            "scripts": {
                "has_props": False,
                "has_data": False,
                "has_computed": False,
                "has_methods": False,
                "has_watch": False,
                "has_lifecycle": False
            },
            "styles": {
                "has_scoped": False,
                "has_dynamic_class": False,
                "has_dynamic_style": False
            },
            "migration_patterns": [
                "event_name_conversion",
                "class_binding_conversion",
                "style_binding_conversion",
                "v_for_conversion",
                "v_if_conversion",
                "v_model_conversion",
                "component_name_conversion",
                "props_init_conversion",
                "lifecycle_conversion",
                "data_access_conversion"
            ]
        },
        "feature_tags": [
            "v-for",
            "v-if",
            "v-on",
            "v-bind",
            "v-model",
            "computed",
            "watch",
            "props",
            "emit",
            "lifecycle-hooks",
            "dynamic-class",
            "dynamic-style",
            "scoped",
            "sub-components",
            "async-logic",
            "filter",
            "cache",
            "local-storage",
            "modal",
            "notification",
            "drag-and-drop",
            "svg-drawing",
            "timer"
        ]
    },
    "template_structure_tree": {
        "description": "描述 DOM 节点层次、子组件引用、插槽分布，以及每个节点上的 Vue 指令与 San 迁移提示。",
        "root": {
            "node_id": "稳定节点编号，例如 root 或 root.header.actions.button_theme",
            "node_type": "element | component | slot | text | comment",
            "tag": "HTML 标签名或子组件标签名，例如 div、stat-card",
            "san_tag": "迁移后的 San 标签名；子组件建议使用短横线命名，例如 stat-card",
            "depth": 0,
            "parent_id": None,
            "path": "节点路径，例如 /div[0]/header[0]/button[1]",
            "semantic_role": "节点语义，例如 app-header、stats-section、modal-overlay",
            "static_attrs": {
                "class": "静态类名字符串",
                "type": "静态属性值"
            },
            "dynamic_attrs": [
                {
                    "source_attr": ":title",
                    "target_attr": "title",
                    "expression": "isDarkMode ? '亮色模式' : '暗色模式'",
                    "dependencies": ["isDarkMode"],
                    "san_expression": "{{isDarkMode ? '亮色模式' : '暗色模式'}}"
                }
            ],
            "directives": [
                {
                    "source": "v-if | v-for | v-model | v-bind | v-on | v-show",
                    "argument": "指令参数，例如 click、class、model 字段",
                    "expression": "Vue 表达式",
                    "san_equivalent": "San 写法，例如 s-if、s-for、value={= field =}、on-click",
                    "dependencies": ["表达式依赖的数据字段、props 或 computed"],
                    "migration_note": "迁移注意事项"
                }
            ],
            "text_bindings": [
                {
                    "raw_text": "{{ totalCount }} 项",
                    "expressions": ["totalCount"],
                    "dependencies": ["totalCount"],
                    "san_text": "{{totalCount}} 项"
                }
            ],
            "children": ["子节点使用同结构递归展开"],
            "component_ref": None,
            "slot_ref": None
        },
        "component_references": [
            {
                "source_name": "Vue 子组件名，例如 StatCard",
                "source_tag": "模板中出现的标签，例如 stat-card 或 StatCard",
                "san_name": "San 组件变量名，例如 StatCard",
                "san_tag": "San 注册标签，例如 stat-card",
                "definition_location": "inline | import | external",
                "registration_required": True,
                "props_in": [
                    {
                        "prop_name": "value",
                        "binding_type": "literal | expression | object | array | boolean",
                        "source_expression": "stat.value",
                        "dependencies": ["statistics"]
                    }
                ],
                "events_out": [
                    {
                        "event_name": "click",
                        "source_syntax": "@click",
                        "target_syntax": "on-click",
                        "handler": "onStatClick(stat)",
                        "payload_shape": "stat 对象或子组件 this.fire payload"
                    }
                ],
                "children_or_slots": ["传给子组件的默认内容或具名插槽"]
            }
        ],
        "slot_distribution": [
            {
                "slot_name": "default | 具名插槽名",
                "owner_component": "接收插槽的组件标签",
                "provided_by_node_ids": ["提供插槽内容的节点 id"],
                "scope_bindings": ["slot-scope 或 scoped slot 变量"],
                "san_strategy": "San 中的 slot 或 children 迁移方式；无插槽时为空数组"
            }
        ]
    },
    "data_binding_graph": {
        "description": "追踪 data、computed、props、watch 在模板和方法中的绑定关系，明确 San 生成时的 dataTypes、initData、computed 与 this.data.get/set 访问方式。",
        "props": [
            {
                "name": "title",
                "type": "String | Number | Boolean | Array | Object | Function | unknown",
                "required": False,
                "default": None,
                "used_in_template_nodes": ["node_id"],
                "used_in_computed": ["computedName"],
                "used_in_methods": ["methodName"],
                "san_data_type": "DataTypes.string",
                "san_initialization": "dataTypes 声明；如需基于 props 初始化内部状态，在 inited 中同步"
            }
        ],
        "data_fields": [
            {
                "name": "todos",
                "default": "[]",
                "value_type": "Array<Todo>",
                "source": "data()",
                "mutability": "read_only | set | append | replace | deep_mutation",
                "initialized_from_props": False,
                "initialized_from_external_effect": "localStorage | async API | timer | none",
                "used_in_template_nodes": ["node_id"],
                "used_in_computed": ["filteredTodos", "totalCount"],
                "read_by_methods": ["saveToLocal"],
                "written_by_methods": ["addTodo", "deleteTodo"],
                "san_access": {
                    "read": "this.data.get('todos')",
                    "write": "this.data.set('todos', nextTodos)"
                }
            }
        ],
        "computed_props": [
            {
                "name": "filteredTodos",
                "return_type": "Array<Todo>",
                "dependencies": ["todos", "currentFilter"],
                "used_in_template_nodes": ["node_id"],
                "used_by_computed": [],
                "used_by_methods": [],
                "source_logic_summary": "根据 currentFilter 过滤 todos",
                "san_strategy": "迁移为 San computed，内部使用 this.data.get('field') 读取依赖"
            }
        ],
        "watchers": [
            {
                "watched_expression": "todos",
                "deep": True,
                "immediate": False,
                "handler_name": "saveToLocal 或 inline handler",
                "side_effects": ["localStorage.setItem"],
                "san_strategy": "在 inited 中 this.watch('todos', handler)；深度监听需要在写入时整体 set 或拆分触发"
            }
        ],
        "binding_edges": [
            {
                "from": "data.todos | computed.filteredTodos | props.title",
                "to": "template.node_id | method.methodName | computed.name | watcher.name",
                "binding_type": "text | attr | class | style | conditional | loop | model | event_arg | method_read | method_write",
                "expression": "原始绑定表达式",
                "san_expression": "迁移后的 San 表达式"
            }
        ],
        "external_state": [
            {
                "name": "localStorage key 或 timer id",
                "kind": "localStorage | timer | async_request | browser_api",
                "read_points": ["mounted/loadFromLocal"],
                "write_points": ["watch/saveToLocal"],
                "san_lifecycle_owner": "inited | attached | disposed"
            }
        ]
    },
    "event_interaction_table": {
        "description": "记录 DOM 事件监听、自定义事件触发、父子组件通信、修饰符和处理函数签名。",
        "dom_events": [
            {
                "node_id": "触发事件的模板节点 id",
                "element_or_component": "button | input | task-item",
                "source_event": "@click | @input | @keyup.enter | @dragstart | @drop.stop",
                "dom_event_name": "click | input | keyup | dragstart | drop",
                "modifiers": ["stop", "prevent", "self", "enter"],
                "handler_expression": "addTodo 或 onStatClick(stat)",
                "handler_name": "addTodo",
                "handler_signature": "addTodo(event?: Event, payload?: any): void",
                "arguments": ["stat", "$event"],
                "reads": ["newTitle", "newPriority"],
                "writes": ["todos", "currentFilter"],
                "side_effects": ["localStorage", "timer", "this.fire", "console", "async request"],
                "san_event_syntax": "on-click=\"addTodo\"",
                "migration_note": "Vue @click 转 San on-click；修饰符需改为显式逻辑或 San 支持语法"
            }
        ],
        "custom_events": [
            {
                "direction": "child_to_parent | parent_to_child | outward_emit",
                "source_component": "TaskItem",
                "target_component": "TaskManager",
                "event_name": "toggle",
                "source_emit": "$emit('toggle', task.id)",
                "san_emit": "this.fire('toggle', taskId)",
                "listener_syntax": "@toggle=\"toggleTaskStatus\" -> on-toggle=\"toggleTaskStatus\"",
                "payload_schema": {
                    "type": "number | string | object | array | none",
                    "fields": ["id", "task", "index"]
                },
                "handler_name": "toggleTaskStatus",
                "handler_signature": "toggleTaskStatus(taskId: number | string): void",
                "state_impact": ["tasks"]
            }
        ],
        "method_table": [
            {
                "name": "methodName",
                "signature": "methodName(arg1: Type, event?: Event): ReturnType",
                "called_by": ["template.node_id", "watcher.todos", "lifecycle.attached", "method.otherMethod"],
                "reads": ["data/props/computed 字段"],
                "writes": ["data 字段"],
                "fires_events": ["自定义事件名"],
                "side_effects": ["localStorage", "setInterval", "clearTimeout", "fetch", "Date.now"],
                "san_data_access_plan": "所有 this.xxx 状态访问改为 this.data.get/set；纯工具方法保留普通方法"
            }
        ]
    },
    "style_feature_set": {
        "description": "捕获静态类名、动态类名绑定、动态样式、作用域样式和影响结构生成的视觉语义。",
        "scoped": True,
        "style_language": "css | less | scss | unknown",
        "static_class_names": [
            {
                "class_name": "todo-app",
                "used_by_node_ids": ["root"],
                "semantic_role": "组件根容器",
                "important_rules": ["display", "padding", "background", "border-radius"]
            }
        ],
        "dynamic_class_bindings": [
            {
                "node_id": "root",
                "source_syntax": ":class=\"{ 'dark-mode': isDarkMode }\"",
                "expression": "{ 'dark-mode': isDarkMode }",
                "dependencies": ["isDarkMode"],
                "possible_classes": ["dark-mode"],
                "san_strategy": "class=\"todo-app {{isDarkMode ? 'dark-mode' : ''}}\""
            }
        ],
        "dynamic_style_bindings": [
            {
                "node_id": "chart_bar",
                "source_syntax": ":style=\"{ width: percent + '%' }\"",
                "expression": "{ width: percent + '%' }",
                "dependencies": ["percent"],
                "san_strategy": "style=\"width: {{percent}}%;\""
            }
        ],
        "css_rules": [
            {
                "selector": ".notification-card:hover",
                "declarations": {
                    "transform": "translateY(-2px)",
                    "box-shadow": "0 4px 12px rgba(0, 0, 0, 0.12)"
                },
                "related_node_ids": ["root"],
                "state_or_pseudo": "hover",
                "migration_keep": True
            }
        ],
        "style_tokens": [
            {
                "token_type": "color | spacing | radius | shadow | font | transition",
                "source_value": "#3b82f6",
                "usage": "primary color / unread icon background",
                "target_value": "保持原值或映射到 San 组件主题变量"
            }
        ],
        "layout_features": ["flex", "grid", "absolute-position", "svg", "responsive", "modal-overlay"]
    },
    "script_model": {
        "description": "归纳 Vue script 中的组件定义、子组件、生命周期、异步逻辑与 San 生成约束。",
        "component_definition": {
            "export_style": "module.exports | export default",
            "name": "组件 name",
            "components_registered": ["子组件注册表"],
            "emits_declared": ["Vue emits 中声明的事件"]
        },
        "sub_components": [
            {
                "name": "TodoItem",
                "source_definition": "inline | imported",
                "props": ["todo"],
                "data_fields": [],
                "computed_props": ["itemClass", "priorityText"],
                "methods": ["handleToggle", "handleDelete"],
                "emits": ["toggle", "delete"],
                "template_summary": "子组件 DOM 树与事件摘要",
                "san_registration": "components: { 'todo-item': TodoItem }"
            }
        ],
        "lifecycle_hooks": [
            {
                "vue_hook": "created | mounted | beforeDestroy | destroyed",
                "san_hook": "inited | attached | disposed",
                "responsibilities": ["初始化 props 派生状态", "启动定时器", "读取本地存储", "清理副作用"],
                "state_reads": [],
                "state_writes": [],
                "cleanup_required": True
            }
        ],
        "async_logic": [
            {
                "method_name": "refreshData",
                "triggered_by": ["mounted", "manualRefresh", "timer"],
                "loading_fields": ["isLoading"],
                "success_writes": ["chartData", "statistics"],
                "error_handling": "记录错误、展示通知或 fire error",
                "san_strategy": "async 方法保留，状态读写改为 this.data.get/set"
            }
        ]
    },
    "migration_knowledge": {
        "description": "沉淀 migration_notes.json 中的经验，作为生成 San 代码时的强约束。",
        "known_challenges": ["从 migration_notes.json 抽取的 challenges"],
        "recommended_solutions": ["从 migration_notes.json 抽取的 solutions"],
        "validation_reference": {
            "structure_score": "历史结构验证分数",
            "functional_test": "passed | not_run | manual_fix_in_progress | failed",
            "visual_test": "passed | not_run | failed"
        },
        "vue_to_san_rules": [
            {
                "source_pattern": "@click / v-on:click",
                "target_pattern": "on-click",
                "applies_to": ["DOM event", "component custom event"],
                "example": "@click=\"addTodo\" -> on-click=\"addTodo\""
            },
            {
                "source_pattern": "v-if",
                "target_pattern": "s-if",
                "applies_to": ["conditional rendering"],
                "example": "v-if=\"isLoading\" -> s-if=\"isLoading\""
            },
            {
                "source_pattern": "v-for",
                "target_pattern": "s-for",
                "applies_to": ["list rendering"],
                "example": "v-for=\"item in list\" -> s-for=\"item in list\""
            },
            {
                "source_pattern": "v-model",
                "target_pattern": "value={= field =} 或 checked={= field =}",
                "applies_to": ["form input", "select", "checkbox"],
                "example": "v-model=\"searchQuery\" -> value={= searchQuery =}"
            },
            {
                "source_pattern": ":class object/array",
                "target_pattern": "字符串类名拼接或 computed class 字符串",
                "applies_to": ["dynamic class"],
                "example": ":class=\"{ active: isActive }\" -> class=\"{{isActive ? 'active' : ''}}\""
            },
            {
                "source_pattern": "$emit",
                "target_pattern": "this.fire",
                "applies_to": ["custom event"],
                "example": "this.$emit('read', title) -> this.fire('read', title)"
            },
            {
                "source_pattern": "this.xxx reactive access",
                "target_pattern": "this.data.get('xxx') / this.data.set('xxx', value)",
                "applies_to": ["data", "props", "computed dependency access"],
                "example": "this.todos -> this.data.get('todos')"
            },
            {
                "source_pattern": "mounted / beforeDestroy",
                "target_pattern": "attached / disposed",
                "applies_to": ["timer", "DOM side effects", "async initialization"],
                "example": "beforeDestroy clearInterval -> disposed clearInterval"
            }
        ]
    },
    "generation_contract": {
        "description": "约束大模型基于 SSM 生成 San 组件时必须满足的条件。",
        "must_preserve": [
            "根节点与主要 DOM 层级语义",
            "子组件拆分、注册名和父子通信事件",
            "props/data/computed 在模板中的可见行为",
            "DOM 事件与自定义事件的触发时机和 payload",
            "动态类名、动态样式、scoped CSS 和关键视觉状态",
            "定时器、localStorage、异步刷新等副作用的生命周期清理"
        ],
        "san_output_requirements": [
            "使用 san.defineComponent 或项目既有 San 写法",
            "props 使用 dataTypes 声明",
            "data 使用 initData 返回默认值",
            "基于 props 派生内部状态时优先在 inited 中同步",
            "模板指令统一使用 San 语法：s-if、s-for、on-event、value={= =}",
            "状态访问统一使用 this.data.get()/set()",
            "子组件标签使用短横线命名并在 components 中显式注册",
            "清理 timer、timeout、外部监听等副作用"
        ],
        "quality_checks": [
            "template_structure_tree 中的 component_references 均已注册",
            "data_binding_graph 中每条模板依赖都能在 props/data/computed 中找到来源",
            "event_interaction_table 中每个 handler 都存在于 method_table 或子组件事件转发中",
            "style_feature_set 中的动态类名/样式依赖都存在于绑定图",
            "migration_knowledge 中标记的模式都有对应 San 转换策略"
        ]
    }
}
