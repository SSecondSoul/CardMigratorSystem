{
  "component_name": "string",
  "template": {
    "root_tag": "string",
    "nodes": [
      {
        "tag": "string",
        "attrs": { "属性名": "属性值" },
        "directives": {
          "v-if": "表达式",
          "v-for": "item in list",
          "v-bind:prop": "表达式",
          "v-on:event": "handler"
        },
        "children": [],
        "text": "文本内容"
      }
    ]
  },
  "script": {
    "data_fields": [
      { "name": "字段名", "default": "默认值或null" }
    ],
    "computed_props": [
      { "name": "计算属性名", "expression": "函数体或描述" }
    ],
    "methods": ["方法名1", "方法名2"],
    "props": [
      { "name": "属性名", "type": "类型", "required": false, "default": null }
    ],
    "events": [
      { "name": "自定义事件名", "is_custom": true }
    ]
  },
  "styles": {
    "scoped": true,
    "css_rules": ["CSS规则字符串"]
  },
  "search_extensions": {
    "component_constraints": [
      {
        "name": "系统组件名",
        "usage": "在模板中的引用位置或描述"
      }
    ],
    "style_token_mapping": [
      {
        "source_token": "--source-color",
        "target_token": "--target-color",
        "description": "颜色映射说明"
      }
    ]
  }
}