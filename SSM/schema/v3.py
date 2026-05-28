"""
SSM Schema v3 — 通用 Vue 组件结构抽取 Schema

设计目标：
1. 仅依赖源码本身，通过 @vue/compiler-sfc 和 @babel/parser 自动提取，
   不依赖任何外部人工标注文件（如 complexity_tags.json、migration_notes.json 等）。
2. 每个字段都标注明确的 AST/编译产物提取路径，便于工具开发。
3. 输出可直接作为大模型生成等价 San 组件的依据。

提取工具输入：任意 .vue 文件 或 包含 <template><script><style> 的 HTML 片段。
提取工具依赖：@vue/compiler-sfc（解析 SFC 与模板 AST）、@babel/parser（解析 script AST）。
"""

SSM_SCHEMA_VERSION = "3.0"

SSM_SCHEMA = {
    "schema_version": "3.0",
    "schema_name": "San Source Model (Generic)",

    "metadata": {
        "description": "组件元信息，从文件系统与 SFC descriptor 中提取。",
        "fields": {
            "component_name": {
                "type": "string | null",
                "extraction": [
                    "1) @vue/compiler-sfc compileScript() 返回的 name 选项",
                    "2) 若不存在，取文件名（去除 .vue 后缀）"
                ]
            },
            "source_file": {
                "type": "string | null",
                "extraction": ["文件系统路径"]
            },
            "source_framework": {
                "type": "string",
                "value": "Vue",
                "extraction": ["固定值"]
            },
            "target_framework": {
                "type": "string",
                "value": "San",
                "extraction": ["固定值"]
            },
            "sfc_blocks": {
                "type": "object",
                "extraction": [
                    "@vue/compiler-sfc parse() 返回的 descriptor",
                    "descriptor.template / descriptor.script / descriptor.scriptSetup / descriptor.styles"
                ],
                "fields": {
                    "has_template": "bool — descriptor.template 是否存在",
                    "has_script": "bool — descriptor.script 或 descriptor.scriptSetup 是否存在",
                    "has_style": "bool — descriptor.styles 长度 > 0",
                    "style_scoped": "bool — descriptor.styles 中任一项 scoped 为 true",
                    "style_lang": "string | null — descriptor.styles[0].lang（css/scss/less）"
                }
            }
        }
    },

    "template": {
        "description": "模板结构树与指令、组件引用、插槽的完整描述。从 @vue/compiler-sfc compileTemplate() 返回的 ast 中提取。",
        "ast_type": "RootNode — @vue/compiler-core 的 AST 根节点",
        "dom_tree": {
            "description": "递归的 DOM 节点结构，每个节点对应模板 AST 中的一个 ElementNode、ComponentNode、TextNode 或 CommentNode。",
            "node_schema": {
                "node_id": "string — 基于 tag + 同级索引生成的稳定标识，例如 root_0_div",
                "node_type": "enum — element | component | text | comment | interpolation | expression",
                "source_tag": "string — 原始标签名，例如 div、StatCard、slot",
                "san_tag": "string — San 中使用的标签名；组件自动转短横线命名，例如 stat-card",
                "depth": "int — 相对于根节点的深度",
                "parent_id": "string | null",
                "path": "string — 人类可读路径，例如 /div[0]/header[0]/button[0]",
                "semantic_role": "string — 基于 class/语义推断的角色，例如 app-header、task-list、modal-overlay",
                "is_root": "bool",
                "is_void": "bool — 自闭合标签（input、img、component 自闭合写法）",
                "static_attrs": {
                    "type": "object",
                    "description": "静态 HTML 属性。从 AST 节点的 props 中过滤 type=6 (ATTRIBUTE) 的项提取。",
                    "example": {"class": "todo-app", "type": "button"}
                },
                "dynamic_attrs": {
                    "type": "array",
                    "description": "动态属性绑定。从 AST props 中过滤 type=7 (DIRECTIVE) 且 name='bind'、无 arg 或 arg 为静态属性的项提取。",
                    "item_schema": {
                        "source_attr": "string — 原始属性名，例如 :title、:class、:style",
                        "target_attr": "string — 绑定目标属性，例如 title、class、style",
                        "expression": "string — Vue 表达式源码",
                        "ast_expression": "ExpressionNode — @vue/compiler-core 的表达式 AST",
                        "dependencies": ["string — 表达式中引用的标识符，通过遍历 expression AST 的 Identifier 节点收集"],
                        "san_expression": "string — 建议的 San 写法"
                    }
                },
                "directives": {
                    "type": "array",
                    "description": "所有 Vue 指令。从 AST props 中过滤 type=7 (DIRECTIVE) 提取。",
                    "item_schema": {
                        "directive_name": "enum — v-if | v-for | v-show | v-model | v-bind | v-on | v-slot | v-html | v-text | custom",
                        "argument": "string | null — 指令参数，例如 click、class、model 字段名、插槽名",
                        "modifiers": ["string — 修饰符列表，例如 stop、prevent、self、enter、native"],
                        "expression": "string — 指令绑定的表达式源码",
                        "ast_expression": "ExpressionNode | null",
                        "dependencies": ["string — 表达式中的标识符"],
                        "san_equivalent": "string — San 中的对应写法",
                        "migration_note": "string — 迁移提示，由 directive_name 与 argument 组合规则自动生成"
                    }
                },
                "event_bindings": {
                    "type": "array",
                    "description": "事件绑定单独列出，方便事件交互表聚合。从 directives 中过滤 name='on' 提取。",
                    "item_schema": {
                        "event_name": "string — DOM 事件名或自定义事件名，例如 click、input、toggle",
                        "modifiers": ["string"],
                        "handler_expression": "string — 处理函数表达式源码",
                        "handler_type": "enum — identifier | inline_expression | method_call",
                        "handler_name": "string | null — 若是标识符或方法调用，提取方法名",
                        "arguments": ["string — 传入的参数表达式"],
                        "is_component_event": "bool — 是否绑定在组件节点上"
                    }
                },
                "text_bindings": {
                    "type": "array",
                    "description": "文本插值与静态文本。从 AST children 中过滤 type=2 (TEXT) 和 type=5 (INTERPOLATION) 提取。",
                    "item_schema": {
                        "raw_text": "string — 原始文本内容或插值表达式",
                        "is_interpolation": "bool",
                        "expression": "string | null — 插值中的表达式源码",
                        "dependencies": ["string"],
                        "san_text": "string — San 模板中的写法"
                    }
                },
                "children": ["递归引用 node_schema"]
            }
        },
        "component_refs": {
            "type": "array",
            "description": "模板中所有子组件引用。遍历 dom_tree 收集 node_type='component' 的节点。",
            "item_schema": {
                "node_id": "string",
                "source_name": "string — 模板中使用的标签名",
                "source_tag": "string — 同上",
                "san_tag": "string — 短横线命名",
                "kebab_name": "string — 短横线命名",
                "pascal_name": "string — PascalCase 命名",
                "definition_location": "enum — inline | import | unknown",
                "is_builtin": "bool — 是否 Vue 内置组件（slot、component、transition、keep-alive 等）",
                "props_bindings": {
                    "type": "array",
                    "description": "传递给子组件的属性。从该组件节点的 dynamic_attrs 和 static_attrs 中提取。",
                    "item_schema": {
                        "prop_name": "string",
                        "binding_type": "enum — literal | expression | object | array | boolean | handler",
                        "source_expression": "string",
                        "dependencies": ["string"]
                    }
                },
                "event_bindings": {
                    "type": "array",
                    "description": "子组件事件监听。从该组件节点的 event_bindings 中提取 is_component_event=true 的项。"
                },
                "slot_contents": {
                    "type": "array",
                    "description": "传给该子组件的默认插槽或具名插槽内容。从该节点的 children 中过滤掉非插槽参数节点提取。"
                }
            }
        },
        "slot_distribution": {
            "type": "array",
            "description": "插槽分布。遍历 dom_tree 收集 <slot> 节点和 v-slot 指令。",
            "item_schema": {
                "slot_name": "string — default 或具名插槽名",
                "node_id": "string",
                "owner_component_id": "string | null — 该插槽定义在哪个组件内部",
                "scope_bindings": ["string — slot-scope / v-slot 解构变量"],
                "fallback_content": "bool — 是否有默认回退内容",
                "usage_points": ["string — 在哪些组件引用节点上使用了该插槽"]
            }
        },
        "directives_registry": {
            "type": "array",
            "description": "全模板指令汇总，用于快速识别迁移模式。收集 dom_tree 中所有 directives。",
            "item_schema": {
                "directive_name": "string",
                "count": "int",
                "example_nodes": ["string — 出现该指令的 node_id 列表"]
            }
        }
    },

    "script": {
        "description": "脚本层结构。从 @vue/compiler-sfc compileScript() 获取 bindings，从 @babel/parser 获取完整 AST。",
        "ast_type": "File — @babel/parser 返回的 AST 根节点",
        "export_info": {
            "type": "object",
            "extraction": [
                "遍历 Babel AST 查找 ExportDefaultDeclaration 或 AssignmentExpression(module.exports = {...})"
            ],
            "fields": {
                "export_type": "enum — default_export | module_exports | named_export | setup_function | unknown",
                "declaration_ast": "ObjectExpression — 组件选项对象 AST"
            }
        },
        "options": {
            "description": "组件选项对象的各属性。从 declaration_ast 的 properties 中按 key.name 提取。",
            "name": {
                "type": "string | null",
                "extraction": ["查找 key.name === 'name' 的 StringLiteral value"]
            },
            "components": {
                "type": "array",
                "description": "注册的子组件。从 key.name === 'components' 的 ObjectExpression 中提取每个 property。",
                "item_schema": {
                    "registered_name": "string — 注册键名",
                    "registered_tag": "string — 短横线形式，用于 San 注册",
                    "source_name": "string — 值引用的变量名",
                    "definition_location": "enum — inline | import | unknown",
                    "inline_definition": "object | null — 若是内联对象，提取其完整 options"
                }
            },
            "props": {
                "type": "array",
                "description": "props 声明。支持数组语法和对象语法。",
                "extraction": [
                    "数组语法：提取 ArrayExpression 的每个 StringLiteral",
                    "对象语法：提取 ObjectExpression 的每个 property"
                ],
                "item_schema": {
                    "name": "string",
                    "type": "string | array — 从 type 字段提取",
                    "required": "bool | null",
                    "default": "any | null — default 字段的 AST 或值摘要",
                    "validator": "bool — 是否存在 validator 函数",
                    "ast": "ASTNode — 该 prop 定义的完整 AST"
                }
            },
            "data": {
                "type": "array",
                "description": "data 字段声明。支持对象语法和函数返回语法。",
                "extraction": [
                    "对象语法：提取 ObjectExpression 的 properties",
                    "函数语法：提取 ReturnStatement 中的 ObjectExpression properties"
                ],
                "item_schema": {
                    "name": "string",
                    "default_value_summary": "string — 默认值表达式源码或类型描述",
                    "default_ast": "ASTNode — 默认值的 AST",
                    "value_type_inferred": "enum — string | number | boolean | array | object | null | function | unknown"
                }
            },
            "computed": {
                "type": "array",
                "description": "计算属性。从 key.name === 'computed' 的 ObjectExpression 提取。",
                "item_schema": {
                    "name": "string",
                    "has_setter": "bool",
                    "getter_body": "string — getter 函数体源码",
                    "getter_ast": "ASTNode",
                    "dependencies_inferred": ["string — 通过遍历 getter AST 的 Identifier 节点推断"],
                    "return_type_inferred": "string | null"
                }
            },
            "watch": {
                "type": "array",
                "description": "监听器。从 key.name === 'watch' 的 ObjectExpression 提取。",
                "item_schema": {
                    "expression": "string — 被监听的字段或路径",
                    "deep": "bool",
                    "immediate": "bool",
                    "handler_type": "enum — method_name | inline_function | object_config",
                    "handler_name": "string | null",
                    "handler_body": "string | null",
                    "handler_ast": "ASTNode | null"
                }
            },
            "methods": {
                "type": "array",
                "description": "方法表。从 key.name === 'methods' 的 ObjectExpression 提取。",
                "item_schema": {
                    "name": "string",
                    "params": ["string — 形参名称"],
                    "params_ast": ["ASTNode"],
                    "body": "string — 函数体源码",
                    "body_ast": "ASTNode",
                    "is_async": "bool",
                    "reads_inferred": ["string — 函数体中 this.xxx 或 this.data.get 的字段"],
                    "writes_inferred": ["string — 函数体中赋值的目标字段"],
                    "emits_inferred": ["string — 函数体中 $emit / this.fire 的事件名"],
                    "calls_inferred": ["string — 函数体中调用的其他方法名"],
                    "side_effects_inferred": ["enum — localStorage | timer | fetch | Date | Math | DOM | console | none"]
                }
            },
            "lifecycle_hooks": {
                "type": "array",
                "description": "生命周期钩子。遍历 options 查找以下 key：beforeCreate, created, beforeMount, mounted, beforeUpdate, updated, beforeDestroy, destroyed, activated, deactivated, errorCaptured。",
                "item_schema": {
                    "vue_hook": "string",
                    "san_hook": "string — 建议的 San 对应钩子",
                    "body": "string",
                    "body_ast": "ASTNode",
                    "responsibilities_inferred": ["enum — init_state | start_timer | read_storage | cleanup | async_init | unknown"],
                    "state_reads": ["string"],
                    "state_writes": ["string"],
                    "cleanup_required": "bool"
                }
            },
            "emits": {
                "type": "array",
                "description": "显式声明的 emits。Vue 3 的 emits 选项或 Vue 2 的 emits 数组。",
                "extraction": ["从 key.name === 'emits' 提取数组元素或对象 keys"]
            },
            "provide_inject": {
                "type": "object",
                "description": "provide / inject 声明。",
                "fields": {
                    "provide_keys": ["string"],
                    "inject_keys": ["string"]
                }
            },
            "filters": {
                "type": "array",
                "description": "Vue 2 过滤器。",
                "item_schema": {
                    "name": "string",
                    "params": ["string"],
                    "body": "string"
                }
            },
            "mixins_extends": {
                "type": "array",
                "description": "mixins 和 extends。",
                "item_schema": {
                    "type": "enum — mixin | extends",
                    "source": "string — 引用的变量名"
                }
            }
        },
        "imports": {
            "type": "array",
            "description": "script 中的 import/require。遍历 Babel AST 收集 ImportDeclaration 和 CallExpression(require)。",
            "item_schema": {
                "source": "string — 模块路径",
                "specifiers": ["string — 导入的变量名"],
                "is_default": "bool",
                "is_namespace": "bool"
            }
        },
        "top_level_declarations": {
            "type": "array",
            "description": "script 中顶层声明的变量/函数/类。",
            "item_schema": {
                "name": "string",
                "kind": "enum — var | let | const | function | class",
                "is_used_in_component": "bool — 是否在组件选项中被引用"
            }
        }
    },

    "styles": {
        "description": "样式块信息。从 @vue/compiler-sfc descriptor.styles 提取。",
        "style_blocks": {
            "type": "array",
            "item_schema": {
                "content": "string — 完整 CSS 文本",
                "lang": "string — css | scss | less | sass | stylus | postcss",
                "scoped": "bool",
                "module": "bool",
                "attrs": "object — style 标签上的其他属性",
                "source_start": "int — 在源码中的起始位置",
                "source_end": "int"
            }
        },
        "css_rules": {
            "type": "array",
            "description": "CSS 规则摘要。使用通用 CSS parser（如 postcss）解析 content 获得。",
            "item_schema": {
                "selectors": ["string"],
                "declarations": {"属性名": "属性值"},
                "has_pseudo": "bool",
                "has_media": "bool",
                "has_keyframes": "bool",
                "related_classes": ["string — 选择器中提取的类名"]
            }
        },
        "css_variables": {
            "type": "array",
            "description": "CSS 自定义属性（变量）。正则匹配 --* 或从 CSS AST 提取。",
            "item_schema": {
                "name": "string",
                "value": "string",
                "scope_selector": "string | null"
            }
        }
    },

    "binding_graph": {
        "description": "数据绑定关系图。通过交叉分析 template AST 中的依赖标识符与 script options 中的 data/computed/props 自动生成。",
        "nodes": {
            "type": "array",
            "item_schema": {
                "node_id": "string — 唯一标识",
                "kind": "enum — data | prop | computed | method | external | template_node | event_handler | watcher",
                "name": "string — 字段名或节点标识",
                "source_location": "string — 定义位置，例如 script.data.todos 或 template.root_0_div"
            }
        },
        "edges": {
            "type": "array",
            "item_schema": {
                "from": "string — 源 node_id",
                "to": "string — 目标 node_id",
                "edge_type": "enum — reads | writes | binds_to | calls | triggers | depends_on",
                "expression": "string — 关联表达式",
                "san_access": "string | null — San 中的访问方式建议"
            }
        },
        "data_fields_usage": {
            "type": "array",
            "description": "每个 data 字段的全局使用摘要。",
            "item_schema": {
                "field_name": "string",
                "read_in_template_nodes": ["string — template node_id"],
                "read_in_computed": ["string — computed 名称"],
                "read_in_methods": ["string — method 名称"],
                "written_in_methods": ["string — method 名称"],
                "watched_by": ["string — watcher 表达式"],
                "initialized_from_props": "bool",
                "initialized_from_external": "string | null — localStorage | api | timer | none"
            }
        }
    },

    "event_model": {
        "description": "事件交互模型。聚合 template.event_bindings 与 script.methods 生成。",
        "dom_events": {
            "type": "array",
            "item_schema": {
                "node_id": "string",
                "element_tag": "string",
                "dom_event_name": "string — click | input | keyup | dragstart | drop | mouseenter | submit | ...",
                "modifiers": ["string"],
                "handler_name": "string",
                "handler_signature_inferred": "string",
                "handler_method_ref": "string — script.methods 中对应的 method name",
                "arguments": ["string"],
                "reads": ["string — 方法中读取的字段"],
                "writes": ["string — 方法中写入的字段"],
                "side_effects": ["string"],
                "san_event_syntax": "string",
                "is_native": "bool — true 表示原生 DOM 事件"
            }
        },
        "custom_events": {
            "type": "array",
            "item_schema": {
                "event_name": "string",
                "source_component": "string — 发出事件的组件名（子组件）",
                "target_component": "string — 监听事件的组件名（父组件）",
                "emit_points": ["string — script.methods 中触发该事件的方法"],
                "emit_expression": "string — 例如 $emit('toggle', task.id)",
                "san_emit": "string — this.fire('toggle', taskId)",
                "listener_handler": "string — 父组件中的处理方法名",
                "listener_node_id": "string — 模板中的监听节点",
                "payload_schema": {
                    "type": "string — object | string | number | array | none",
                    "fields_inferred": ["string"]
                },
                "state_impact": ["string — 触发后可能变更的状态"]
            }
        }
    },

    "style_model": {
        "description": "样式特征模型。聚合 template 中的 class/style 绑定与 styles 中的 CSS 规则。",
        "scoped": "bool — 来自 styles.style_blocks 中任一项 scoped",
        "static_classes": {
            "type": "array",
            "description": "模板中直接写的 class 值。从 template.dom_tree 各节点的 static_attrs.class 提取。",
            "item_schema": {
                "class_name": "string",
                "node_ids": ["string"],
                "semantic_role": "string — 基于类名和上下文推断"
            }
        },
        "dynamic_class_bindings": {
            "type": "array",
            "description": "动态类名绑定。从 template.dom_tree 各节点的 dynamic_attrs 中 target_attr='class' 的项提取。",
            "item_schema": {
                "node_id": "string",
                "source_expression": "string",
                "expression_type": "enum — object | array | string | ternary | unknown",
                "dependencies": ["string"],
                "possible_classes": ["string — 表达式中可能产生的类名字符串，静态分析提取"],
                "san_strategy": "string"
            }
        },
        "dynamic_style_bindings": {
            "type": "array",
            "description": "动态样式绑定。从 dynamic_attrs 中 target_attr='style' 提取。",
            "item_schema": {
                "node_id": "string",
                "source_expression": "string",
                "expression_type": "enum — object | string | ternary | unknown",
                "dependencies": ["string"],
                "san_strategy": "string"
            }
        },
        "css_rules_summary": {
            "type": "array",
            "description": "与组件类名相关的 CSS 规则摘要。",
            "item_schema": {
                "selector": "string",
                "declarations": "object",
                "pseudo_state": "string | null — hover | focus | active | nth-child | ...",
                "affected_classes": ["string"],
                "migration_keep": "bool"
            }
        },
        "layout_features_inferred": {
            "type": "array",
            "description": "从 CSS 规则中推断的布局特征。",
            "item_schema": {
                "feature": "enum — flex | grid | absolute | fixed | relative | svg | responsive | modal-overlay | transition | transform",
                "evidence": "string — 基于哪些 CSS 属性推断"
            }
        }
    },

    "sub_components": {
        "description": "子组件完整描述。包括内联定义和导入组件。",
        "type": "array",
        "item_schema": {
            "name": "string",
            "is_inline": "bool",
            "is_imported": "bool",
            "import_source": "string | null",
            "template_summary": "object | null — 若是内联定义，递归使用 template.dom_tree 结构摘要",
            "props": ["string — 内联子组件的 props 名称"],
            "data_fields": ["string"],
            "computed_props": ["string"],
            "methods": ["string"],
            "emits": ["string"],
            "events_to_parent": ["string"],
            "san_registration": "string — 例如 components: { 'stat-card': StatCard }"
        }
    },

    "migration_hints": {
        "description": "从源码 AST 特征自动推断的迁移提示，不依赖外部人工标注。",
        "detected_patterns": {
            "type": "array",
            "description": "根据 template.directives_registry 和 script.options 自动标记的迁移模式。",
            "item_schema": {
                "pattern_id": "string",
                "pattern_name": "string",
                "detected_by": "string — 基于哪个 AST 特征检测到的",
                "affected_nodes": ["string — template node_id 或 script 字段"],
                "san_strategy": "string",
                "risk_level": "enum — low | medium | high"
            },
            "auto_detected_list": [
                {
                    "pattern_id": "event_click",
                    "condition": "template 中存在 @click 或 v-on:click",
                    "san_strategy": "on-click",
                    "risk": "low"
                },
                {
                    "pattern_id": "event_input",
                    "condition": "template 中存在 @input",
                    "san_strategy": "on-input",
                    "risk": "low"
                },
                {
                    "pattern_id": "v_if",
                    "condition": "template 中存在 v-if",
                    "san_strategy": "s-if",
                    "risk": "low"
                },
                {
                    "pattern_id": "v_for",
                    "condition": "template 中存在 v-for",
                    "san_strategy": "s-for",
                    "risk": "low"
                },
                {
                    "pattern_id": "v_model",
                    "condition": "template 中存在 v-model",
                    "san_strategy": "value={= field =} 或 checked={= field =}",
                    "risk": "medium"
                },
                {
                    "pattern_id": "dynamic_class_object",
                    "condition": ":class 绑定值为对象字面量",
                    "san_strategy": "字符串拼接或 computed class 字符串",
                    "risk": "medium"
                },
                {
                    "pattern_id": "dynamic_class_array",
                    "condition": ":class 绑定值为数组字面量",
                    "san_strategy": "字符串拼接或 computed class 字符串",
                    "risk": "medium"
                },
                {
                    "pattern_id": "dynamic_style_object",
                    "condition": ":style 绑定值为对象字面量",
                    "san_strategy": "style 字符串绑定",
                    "risk": "medium"
                },
                {
                    "pattern_id": "emit",
                    "condition": "script 中存在 $emit 调用",
                    "san_strategy": "this.fire",
                    "risk": "low"
                },
                {
                    "pattern_id": "data_access_this_dot",
                    "condition": "script methods 中存在 this.xxx 访问响应式数据",
                    "san_strategy": "this.data.get('xxx') / this.data.set('xxx', value)",
                    "risk": "high"
                },
                {
                    "pattern_id": "lifecycle_mounted",
                    "condition": "script 中存在 mounted 钩子",
                    "san_strategy": "attached",
                    "risk": "medium"
                },
                {
                    "pattern_id": "lifecycle_beforeDestroy",
                    "condition": "script 中存在 beforeDestroy 钩子",
                    "san_strategy": "disposed",
                    "risk": "medium"
                },
                {
                    "pattern_id": "watch_deep",
                    "condition": "script 中存在 deep: true 的 watcher",
                    "san_strategy": "San 中避免 deep watch，改用在写入点显式 set 或拆分数据结构",
                    "risk": "high"
                },
                {
                    "pattern_id": "local_storage",
                    "condition": "script 中存在 localStorage 读写",
                    "san_strategy": "在生命周期中管理，读写统一用 localStorage API",
                    "risk": "medium"
                },
                {
                    "pattern_id": "timer",
                    "condition": "script 中存在 setInterval / setTimeout",
                    "san_strategy": "在 attached 中启动，在 disposed 中清理",
                    "risk": "medium"
                },
                {
                    "pattern_id": "pascal_component_tag",
                    "condition": "template中存在 PascalCase 组件标签",
                    "san_strategy": "改为短横线命名并在 components 中显式注册",
                    "risk": "high"
                },
                {
                    "pattern_id": "slot",
                    "condition": "模板中存在 <slot> 或 v-slot",
                    "san_strategy": "San slot 语法，注意 scoped slot 变量传递",
                    "risk": "medium"
                },
                {
                    "pattern_id": "filter",
                    "condition": "Vue 2 过滤器或模板管道语法",
                    "san_strategy": "迁移为 method 或 computed",
                    "risk": "medium"
                },
                {
                    "pattern_id": "svg_drawing",
                    "condition": "模板中存在 <svg>、<circle>、<path> 等 SVG 元素",
                    "san_strategy": "保留 SVG 标签和属性绑定，注意 :cx / :cy 等动态属性转为属性绑定",
                    "risk": "medium"
                },
                {
                    "pattern_id": "async_await",
                    "condition": "script 中存在 async 方法或 await 表达式",
                    "san_strategy": "保留 async/await，状态读写改为 this.data.get/set",
                    "risk": "low"
                }
            ]
        },
        "data_access_conversion_plan": {
            "type": "object",
            "description": "为每个 data/prop/computed 字段生成 San 访问方案。",
            "fields": {
                "read_plan": "string — 例如 this.data.get('todos')",
                "write_plan": "string | null — 例如 this.data.set('todos', nextTodos)",
                "init_plan": "string | null — 例如 initData 中声明，inited 中基于 props 同步"
            }
        }
    },

    "san_generation_contract": {
        "description": "约束大模型基于本 schema 生成 San 组件时必须满足的条件。",
        "must_preserve": [
            "metadata.component_name 和根节点语义",
            "template.dom_tree 的层级结构、节点顺序与语义角色",
            "template.component_refs 中每个子组件的注册名和父子通信事件",
            "binding_graph 中 data/props/computed 到模板节点的可见绑定",
            "event_model 中每个 DOM 事件和自定义事件的触发时机与 payload",
            "style_model 中动态类名、动态样式、scoped CSS 和关键视觉状态",
            "script.lifecycle_hooks 中的副作用初始化与清理逻辑",
            "script.options.data 中所有字段的默认值和外部初始化来源"
        ],
        "san_syntax_requirements": [
            "组件定义使用 san.defineComponent",
            "props 使用 dataTypes 声明，与 script.options.props 一一对应",
            "data 使用 initData 返回默认值，与 script.options.data 一一对应",
            "模板中使用 s-if、s-for、on-event、value={= =}、checked={= =} 等 San 语法",
            "状态访问统一使用 this.data.get() / this.data.set()",
            "子组件标签使用 migration_hints 中生成的短横线命名",
            "子组件在 components 中显式注册",
            "定时器、timeout、外部监听等副作用在 attached/disposed 中管理"
        ],
        "quality_checks": [
            "template.component_refs 中每个子组件都在 script.components 或 san_registration 中有定义",
            "binding_graph.edges 中每条 template 依赖都能在 script.options.props/data/computed 中找到来源",
            "event_model.dom_events 中每个 handler_name 都存在于 script.options.methods 或 lifecycle_hooks",
            "event_model.custom_events 中每个 emit_points 都对应 script.methods 中的 $emit 调用",
            "style_model.dynamic_class_bindings 和 dynamic_style_bindings 的 dependencies 都存在于 binding_graph.nodes",
            "script.options.watch 中的 deep watcher 在 migration_hints 中被标记并给出替代策略"
        ]
    }
}
