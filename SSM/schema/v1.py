{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "component_name": { "type": "string" },
    "template": {
      "type": "object",
      "properties": {
        "root_tag": { "type": "string" },
        "has_v_for": { "type": "boolean" },
        "has_v_if": { "type": "boolean" },
        "has_v_bind": { "type": "boolean" },
        "has_v_on": { "type": "boolean" },
        "has_slot": { "type": "boolean" },
        "events": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "type": { "type": "string" },
              "handler": { "type": "string" }
            }
          }
        }
      }
    },
    "script": {
      "type": "object",
      "properties": {
        "has_props": { "type": "boolean" },
        "has_data": { "type": "boolean" },
        "has_computed": { "type": "boolean" },
        "has_methods": { "type": "boolean" },
        "has_watch": { "type": "boolean" },
        "has_lifecycle": { "type": "boolean" },
        "props_list": { "type": "array" },
        "data_fields": { "type": "object" },
        "computed_fields": { "type": "array" },
        "methods": { "type": "array" }
      }
    },
    "styles": {
      "type": "object",
      "properties": {
        "has_scoped": { "type": "boolean" },
        "has_dynamic_class": { "type": "boolean" },
        "has_dynamic_style": { "type": "boolean" },
        "css_rules": { "type": "array" }
      }
    },
    "migration_patterns": { "type": "array" }
  }
}