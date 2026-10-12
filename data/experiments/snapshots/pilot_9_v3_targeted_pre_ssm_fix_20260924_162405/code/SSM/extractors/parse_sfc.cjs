#!/usr/bin/env node

const fs = require('fs');

function safeRequire(name) {
  try {
    return require(name);
  } catch (error) {
    return null;
  }
}

const compilerSfc = safeRequire('@vue/compiler-sfc');
const compilerDom = safeRequire('@vue/compiler-dom');
const babelParser = safeRequire('@babel/parser');
const babelTraversePkg = safeRequire('@babel/traverse');
const babelTraverse = babelTraversePkg && (babelTraversePkg.default || babelTraversePkg);

if (!compilerSfc || !compilerDom || !babelParser || !babelTraverse) {
  process.stdout.write(JSON.stringify({
    error: 'missing_dependencies',
    missing: {
      compilerSfc: !compilerSfc,
      compilerDom: !compilerDom,
      babelParser: !babelParser,
      babelTraverse: !babelTraverse,
    },
  }));
  process.exit(0);
}

const source = fs.readFileSync(0, 'utf8');
const filename = process.argv[2] || 'inline.vue';

function kebabCase(name) {
  return String(name || '').replace(/([a-z0-9])([A-Z])/g, '$1-$2').replace(/_/g, '-').toLowerCase();
}

function isLikelyComponent(tag, tagType) {
  if (!tag) return false;
  if (tagType === 1 || tagType === 2 || tagType === 3) return true;
  return /^[A-Z]/.test(tag) || tag.includes('-');
}

function extractIdentifiers(expression) {
  if (!expression || typeof expression !== 'string') return [];
  const matches = expression.match(/\b[a-zA-Z_$][\w$]*(?:\.[\w$]+)?\b/g) || [];
  const keywords = new Set([
    'true', 'false', 'null', 'undefined', 'this', 'return', 'if', 'else', 'new',
    'typeof', 'void', 'in', 'of', 'Math', 'Date', 'JSON', 'Object', 'Array',
    'String', 'Number', 'Boolean', 'console'
  ]);
  return [...new Set(matches.filter(item => !keywords.has(item) && !/^\d/.test(item)))];
}

function analyzeEventExpression(expression) {
  const result = {
    handler_expression: expression || '',
    handler_type: 'identifier',
    handler_name: expression || '',
    arguments: [],
  };
  if (!expression) return result;
  const match = expression.match(/^([\w$]+)\s*\((.*)\)$/s);
  if (match) {
    result.handler_type = 'method_call';
    result.handler_name = match[1];
    result.arguments = match[2].split(',').map(item => item.trim()).filter(Boolean);
    return result;
  }
  if (/=>/.test(expression) || /^\{/.test(expression.trim())) {
    result.handler_type = 'inline_expression';
    result.handler_name = '';
  }
  return result;
}

function extractStaticAttrs(props) {
  const attrs = {};
  for (const prop of props || []) {
    if (prop.type === 6) {
      attrs[prop.name] = prop.value ? prop.value.content : '';
    }
  }
  return attrs;
}

function extractDirectives(props, nodeId, sourceTag, isComponentEvent) {
  const directives = [];
  const eventBindings = [];
  const dynamicAttrs = [];

  for (const prop of props || []) {
    if (prop.type !== 7) continue;
    const directiveName = `v-${prop.name}`;
    const argument = prop.arg && prop.arg.type === 4 ? prop.arg.content : '';
    const expression = prop.exp && prop.exp.content ? prop.exp.content : '';
    const dependencies = extractIdentifiers(expression);
    const modifiers = Object.keys(prop.modifiers || {});
    const normalizedEventName = prop.name === 'on' ? (argument || 'click') : argument;

    const entry = {
      directive_name: directiveName,
      argument: normalizedEventName,
      modifiers,
      expression,
      dependencies,
      san_equivalent: ({
        'v-if': 's-if',
        'v-else-if': 's-else-if',
        'v-else': 's-else',
        'v-for': 's-for',
        'v-on': 'on-event',
        'v-bind': 'attr 绑定',
        'v-model': 'value={= field =}',
        'v-slot': 'slot',
        'v-show': 's-if 或 display 控制',
      })[directiveName] || directiveName,
      migration_note: `${directiveName} 需要迁移到 San`,
    };
    directives.push(entry);

    if (prop.name === 'on') {
      const analyzed = analyzeEventExpression(expression);
      eventBindings.push({
        node_id: nodeId,
        element_tag: sourceTag,
        event_name: normalizedEventName,
        modifiers,
        handler_expression: analyzed.handler_expression,
        handler_type: analyzed.handler_type,
        handler_name: analyzed.handler_name,
        arguments: analyzed.arguments,
        is_component_event: !!isComponentEvent,
        san_event_syntax: `on-${normalizedEventName}="${analyzed.handler_name || analyzed.handler_expression}"`,
      });
    }

    if (prop.name === 'bind' && argument) {
      dynamicAttrs.push({
        source_attr: `:${argument}`,
        target_attr: argument,
        expression,
        dependencies,
        san_strategy: entry.san_equivalent,
      });
    }
    if (prop.name === 'model') {
      dynamicAttrs.push({
        source_attr: 'v-model',
        target_attr: 'value',
        expression,
        dependencies,
        san_strategy: entry.san_equivalent,
      });
    }
  }

  return { directives, eventBindings, dynamicAttrs };
}

function buildTemplateNode(node, parentId = null, depth = 0, path = '', siblingIndex = 0) {
  if (!node) return null;

  if (node.type === 2) {
    return {
      node_id: `${parentId || 'root'}_text_${siblingIndex}`,
      node_type: 'text',
      source_tag: 'text',
      san_tag: 'text',
      depth,
      parent_id: parentId,
      path: `${path}/text[${siblingIndex}]`,
      semantic_role: '',
      is_root: false,
      is_void: false,
      static_attrs: {},
      dynamic_attrs: [],
      directives: [],
      event_bindings: [],
      text_bindings: [{ raw_text: node.content, is_interpolation: false, expression: null, dependencies: [], san_text: node.content }],
      children: [],
    };
  }

  if (node.type === 5) {
    const expression = node.content && node.content.content ? node.content.content : '';
    return {
      node_id: `${parentId || 'root'}_interp_${siblingIndex}`,
      node_type: 'interpolation',
      source_tag: 'interpolation',
      san_tag: 'interpolation',
      depth,
      parent_id: parentId,
      path: `${path}/interpolation[${siblingIndex}]`,
      semantic_role: '',
      is_root: false,
      is_void: false,
      static_attrs: {},
      dynamic_attrs: [],
      directives: [],
      event_bindings: [],
      text_bindings: [{ raw_text: `{{${expression}}}`, is_interpolation: true, expression, dependencies: extractIdentifiers(expression), san_text: `{{${expression}}}` }],
      children: [],
    };
  }

  if (node.type !== 1) return null;

  const sourceTag = node.tag;
  const tagType = node.tagType;
  const nodeType = sourceTag === 'slot' ? 'slot' : (isLikelyComponent(sourceTag, tagType) ? 'component' : 'element');
  const nodeId = `${parentId || 'root'}_${sourceTag}_${siblingIndex}`;
  const nodePath = `${path || ''}/${sourceTag}[${siblingIndex}]`;
  const staticAttrs = extractStaticAttrs(node.props);
  const analysis = extractDirectives(node.props, nodeId, sourceTag, nodeType === 'component');
  const semanticRole = (staticAttrs.class || '').split(/\s+/).filter(Boolean)[0] || '';

  const built = {
    node_id: nodeId,
    node_type: nodeType,
    source_tag: sourceTag,
    san_tag: nodeType === 'component' ? kebabCase(sourceTag) : sourceTag,
    depth,
    parent_id: parentId,
    path: nodePath,
    semantic_role: semanticRole,
    is_root: !parentId,
    is_void: !!node.isSelfClosing,
    static_attrs: staticAttrs,
    dynamic_attrs: analysis.dynamicAttrs,
    directives: analysis.directives,
    event_bindings: analysis.eventBindings,
    text_bindings: [],
    children: [],
  };

  let childIndex = 0;
  for (const child of node.children || []) {
    const childNode = buildTemplateNode(child, nodeId, depth + 1, nodePath, childIndex++);
    if (!childNode) continue;
    if ((childNode.node_type === 'text' || childNode.node_type === 'interpolation') && !childNode.children.length) {
      built.text_bindings.push(...childNode.text_bindings);
    } else {
      built.children.push(childNode);
    }
  }

  return built;
}

function collectNodes(root, output = []) {
  if (!root) return output;
  output.push(root);
  for (const child of root.children || []) collectNodes(child, output);
  return output;
}

function buildTemplateAnalysis(templateContent) {
  if (!templateContent || !templateContent.trim()) {
    return { dom_tree: {}, component_refs: [], slot_distribution: [], directives_registry: [], event_bindings: [] };
  }

  const ast = compilerDom.parse(templateContent);
  const elementChildren = (ast.children || []).filter(Boolean);
  const rootElement = elementChildren.find(node => node.type === 1) || null;
  const domTree = rootElement ? buildTemplateNode(rootElement, null, 0, '', 0) : {};
  const allNodes = collectNodes(domTree, []);

  const componentRefs = allNodes.filter(node => node.node_type === 'component').map(node => ({
    node_id: node.node_id,
    source_name: node.source_tag,
    source_tag: node.source_tag,
    san_tag: kebabCase(node.source_tag),
    kebab_name: kebabCase(node.source_tag),
    pascal_name: node.source_tag,
    definition_location: 'unknown',
    is_builtin: ['component', 'transition', 'keep-alive', 'transition-group', 'teleport', 'suspense'].includes(String(node.source_tag).toLowerCase()),
    props_bindings: node.dynamic_attrs.map(attr => ({ prop_name: attr.target_attr, binding_type: 'expression', source_expression: attr.expression, dependencies: attr.dependencies })),
    event_bindings: node.event_bindings,
    slot_contents: (node.children || []).map(child => ({ node_id: child.node_id, tag: child.source_tag, type: child.node_type })),
  }));

  const slotDistribution = allNodes.filter(node => node.node_type === 'slot' || node.source_tag === 'slot').map(node => ({
    slot_name: (node.static_attrs && node.static_attrs.name) || 'default',
    node_id: node.node_id,
    owner_component_id: node.parent_id,
    scope_bindings: [],
    fallback_content: (node.children || []).length > 0 || (node.text_bindings || []).length > 0,
    usage_points: [],
  }));

  const registryMap = new Map();
  for (const node of allNodes) {
    for (const directive of node.directives || []) {
      const current = registryMap.get(directive.directive_name) || { directive_name: directive.directive_name, count: 0, example_nodes: [] };
      current.count += 1;
      if (current.example_nodes.length < 3) current.example_nodes.push(node.node_id);
      registryMap.set(directive.directive_name, current);
    }
  }

  const eventBindings = allNodes.flatMap(node => node.event_bindings || []);
  return { dom_tree: domTree || {}, component_refs: componentRefs, slot_distribution: slotDistribution, directives_registry: [...registryMap.values()], event_bindings: eventBindings };
}

function literalValue(node) {
  if (!node) return null;
  if (node.type === 'StringLiteral' || node.type === 'NumericLiteral' || node.type === 'BooleanLiteral') return node.value;
  if (node.type === 'NullLiteral') return null;
  return null;
}

function inferValueType(node) {
  if (!node) return 'unknown';
  switch (node.type) {
    case 'StringLiteral': return 'string';
    case 'NumericLiteral': return 'number';
    case 'BooleanLiteral': return 'boolean';
    case 'NullLiteral': return 'null';
    case 'ArrayExpression': return 'array';
    case 'ObjectExpression': return 'object';
    case 'ArrowFunctionExpression':
    case 'FunctionExpression':
    case 'FunctionDeclaration': return 'function';
    default: return 'unknown';
  }
}

function nodeToCode(node, sourceCode) {
  if (!node || node.start == null || node.end == null) return '';
  return sourceCode.slice(node.start, node.end);
}

function findExportObject(ast) {
  let exportType = 'unknown';
  let objectNode = null;
  for (const stmt of ast.program.body) {
    if (stmt.type === 'ExportDefaultDeclaration' && stmt.declaration.type === 'ObjectExpression') {
      exportType = 'default_export';
      objectNode = stmt.declaration;
      break;
    }
    if (stmt.type === 'ExpressionStatement' && stmt.expression.type === 'AssignmentExpression') {
      const left = stmt.expression.left;
      if (left.type === 'MemberExpression' && left.object.name === 'module' && left.property.name === 'exports' && stmt.expression.right.type === 'ObjectExpression') {
        exportType = 'module_exports';
        objectNode = stmt.expression.right;
        break;
      }
    }
  }
  return { exportType, objectNode };
}

function getObjectPropertyByName(objectNode, name) {
  if (!objectNode || objectNode.type !== 'ObjectExpression') return null;
  return (objectNode.properties || []).find(prop => {
    if (prop.type !== 'ObjectProperty' && prop.type !== 'ObjectMethod') return false;
    if (prop.key.type === 'Identifier') return prop.key.name === name;
    if (prop.key.type === 'StringLiteral') return prop.key.value === name;
    return false;
  }) || null;
}

function propertyName(prop) {
  if (!prop || !prop.key) return '';
  if (prop.key.type === 'Identifier') return prop.key.name;
  if (prop.key.type === 'StringLiteral') return prop.key.value;
  return '';
}

function collectThisReadsWrites(functionNode, sourceCode) {
  const reads = new Set();
  const writes = new Set();
  const emits = new Set();
  const calls = new Set();
  const effects = new Set();

  babelTraverse(functionNode, {
    noScope: true,
    MemberExpression(path) {
      const node = path.node;
      if (node.object && node.object.type === 'ThisExpression' && node.property && node.property.type === 'Identifier') {
        const name = node.property.name;
        if (path.parent && path.parent.type === 'AssignmentExpression' && path.parent.left === node) {
          writes.add(name);
        } else {
          reads.add(name);
        }
      }
    },
    AssignmentExpression(path) {
      const left = path.node.left;
      if (left.type === 'MemberExpression' && left.object.type === 'ThisExpression' && left.property.type === 'Identifier') {
        writes.add(left.property.name);
      }
    },
    UpdateExpression(path) {
      const arg = path.node.argument;
      if (arg.type === 'MemberExpression' && arg.object.type === 'ThisExpression' && arg.property.type === 'Identifier') {
        writes.add(arg.property.name);
      }
    },
    CallExpression(path) {
      const callee = path.node.callee;
      if (callee.type === 'MemberExpression') {
        if (callee.object.type === 'ThisExpression' && callee.property.type === 'Identifier') {
          calls.add(callee.property.name);
        }
        if (callee.object.type === 'MemberExpression' && callee.object.object.type === 'ThisExpression' && callee.object.property.type === 'Identifier' && callee.property.type === 'Identifier') {
          if (callee.object.property.name === 'data' && callee.property.name === 'set') {
            const first = path.node.arguments[0];
            if (first && first.type === 'StringLiteral') writes.add(first.value);
          }
        }
      }
      if (callee.type === 'MemberExpression' && callee.object.type === 'ThisExpression' && callee.property.type === 'Identifier' && callee.property.name === '$emit') {
        const first = path.node.arguments[0];
        if (first && first.type === 'StringLiteral') emits.add(first.value);
      }
      const snippet = nodeToCode(path.node, sourceCode);
      if (/localStorage|sessionStorage/.test(snippet)) effects.add('localStorage');
      if (/setInterval|setTimeout|clearInterval|clearTimeout/.test(snippet)) effects.add('timer');
      if (/fetch\s*\(|axios|XMLHttpRequest/.test(snippet)) effects.add('fetch');
      if (/console\./.test(snippet)) effects.add('console');
    },
    NewExpression(path) {
      const snippet = nodeToCode(path.node, sourceCode);
      if (/Date/.test(snippet)) effects.add('Date');
    }
  });

  return {
    reads_inferred: [...reads],
    writes_inferred: [...writes],
    emits_inferred: [...emits],
    calls_inferred: [...calls],
    side_effects_inferred: [...effects],
  };
}

function extractFunctionInfo(name, functionNode, sourceCode) {
  const params = (functionNode.params || []).map(param => param.type === 'Identifier' ? param.name : nodeToCode(param, sourceCode));
  const wrapper = { type: 'File', program: { type: 'Program', body: [{ type: 'ExpressionStatement', expression: functionNode }] } };
  const usage = collectThisReadsWrites(wrapper, sourceCode);
  return {
    name,
    params,
    body: nodeToCode(functionNode.body || functionNode, sourceCode).slice(0, 500),
    is_async: !!functionNode.async,
    ...usage,
  };
}

function extractLifecycleResponsibilities(body) {
  const result = [];
  if (/this\.|this\.data\.set/.test(body)) result.push('init_state');
  if (/setInterval|setTimeout/.test(body)) result.push('start_timer');
  if (/clearInterval|clearTimeout/.test(body)) result.push('cleanup');
  if (/localStorage|sessionStorage/.test(body)) result.push('read_storage');
  if (/fetch\(|axios|await /.test(body)) result.push('async_init');
  return result.length ? result : ['unknown'];
}

function buildScriptAnalysis(scriptContent) {
  if (!scriptContent || !scriptContent.trim()) {
    return { export_info: { export_type: 'unknown', has_export: false }, options: {}, imports: [], top_level_declarations: [] };
  }

  const ast = babelParser.parse(scriptContent, {
    sourceType: 'unambiguous',
    plugins: ['jsx', 'typescript', 'decorators-legacy', 'classProperties', 'objectRestSpread'],
  });

  const imports = [];
  const topLevelDeclarations = [];
  babelTraverse(ast, {
    ImportDeclaration(path) {
      imports.push({
        kind: 'import',
        source: path.node.source.value,
        specifiers: path.node.specifiers.map(spec => spec.local.name),
        is_default: path.node.specifiers.some(spec => spec.type === 'ImportDefaultSpecifier'),
      });
    },
    VariableDeclaration(path) {
      if (path.parent.type !== 'Program') return;
      for (const decl of path.node.declarations) {
        if (decl.id.type === 'Identifier') topLevelDeclarations.push({ name: decl.id.name, kind: path.node.kind, is_used_in_component: false });
      }
    },
    FunctionDeclaration(path) {
      if (path.parent.type !== 'Program' || !path.node.id) return;
      topLevelDeclarations.push({ name: path.node.id.name, kind: 'function', is_used_in_component: false });
    }
  });

  const { exportType, objectNode } = findExportObject(ast);
  const exportInfo = { export_type: exportType, has_export: !!objectNode };
  if (!objectNode) return { export_info: exportInfo, options: {}, imports, top_level_declarations: topLevelDeclarations };

  const options = {
    name: null,
    components: [],
    props: [],
    data: [],
    computed: [],
    watch: [],
    methods: [],
    lifecycle_hooks: [],
    emits: [],
    filters: [],
    provide_keys: [],
    inject_keys: [],
    mixins: [],
    extends: [],
  };

  const nameProp = getObjectPropertyByName(objectNode, 'name');
  if (nameProp && nameProp.value && nameProp.value.type === 'StringLiteral') options.name = nameProp.value.value;

  const componentsProp = getObjectPropertyByName(objectNode, 'components');
  if (componentsProp && componentsProp.value && componentsProp.value.type === 'ObjectExpression') {
    for (const prop of componentsProp.value.properties || []) {
      if (prop.type !== 'ObjectProperty' && prop.type !== 'ObjectMethod') continue;
      const key = propertyName(prop);
      const sourceName = prop.type === 'ObjectProperty' && prop.value.type === 'Identifier' ? prop.value.name : `inline_${key}`;
      options.components.push({
        registered_name: key,
        registered_tag: kebabCase(key),
        source_name: sourceName,
        definition_location: prop.type === 'ObjectProperty' && prop.value.type === 'ObjectExpression' ? 'inline' : 'unknown',
        inline_definition: null,
      });
    }
  }

  const propsProp = getObjectPropertyByName(objectNode, 'props');
  if (propsProp) {
    const value = propsProp.value;
    if (value.type === 'ArrayExpression') {
      for (const item of value.elements || []) {
        if (item && item.type === 'StringLiteral') options.props.push({ name: item.value, type: 'unknown', required: false, default: null, validator: false });
      }
    } else if (value.type === 'ObjectExpression') {
      for (const prop of value.properties || []) {
        if (prop.type !== 'ObjectProperty') continue;
        const propName = propertyName(prop);
        let type = 'unknown';
        let required = false;
        let validator = false;
        let defaultValue = null;
        if (prop.value.type === 'ObjectExpression') {
          for (const inner of prop.value.properties || []) {
            if (inner.type !== 'ObjectProperty') continue;
            const innerName = propertyName(inner);
            if (innerName === 'type') type = nodeToCode(inner.value, scriptContent) || 'unknown';
            if (innerName === 'required' && inner.value.type === 'BooleanLiteral') required = inner.value.value;
            if (innerName === 'validator') validator = true;
            if (innerName === 'default') defaultValue = nodeToCode(inner.value, scriptContent) || null;
          }
        }
        options.props.push({ name: propName, type, required, default: defaultValue, validator });
      }
    }
  }

  const dataProp = getObjectPropertyByName(objectNode, 'data');
  if (dataProp) {
    let returnedObject = null;
    if (dataProp.type === 'ObjectMethod') {
      for (const stmt of dataProp.body.body || []) {
        if (stmt.type === 'ReturnStatement' && stmt.argument && stmt.argument.type === 'ObjectExpression') {
          returnedObject = stmt.argument;
          break;
        }
      }
    } else if (dataProp.value && dataProp.value.type === 'ObjectExpression') {
      returnedObject = dataProp.value;
    }
    if (returnedObject) {
      for (const prop of returnedObject.properties || []) {
        if (prop.type !== 'ObjectProperty') continue;
        const fieldName = propertyName(prop);
        options.data.push({ name: fieldName, default_value_summary: nodeToCode(prop.value, scriptContent).slice(0, 50), value_type_inferred: inferValueType(prop.value) });
      }
    }
  }

  const computedProp = getObjectPropertyByName(objectNode, 'computed');
  if (computedProp && computedProp.value && computedProp.value.type === 'ObjectExpression') {
    for (const prop of computedProp.value.properties || []) {
      const name = propertyName(prop);
      let fnNode = null;
      let hasSetter = false;
      if (prop.type === 'ObjectMethod') fnNode = prop;
      if (prop.type === 'ObjectProperty' && prop.value.type === 'ObjectExpression') {
        for (const inner of prop.value.properties || []) {
          const innerName = propertyName(inner);
          if (innerName === 'get' && inner.type === 'ObjectMethod') fnNode = inner;
          if (innerName === 'set') hasSetter = true;
        }
      }
      if (!fnNode && prop.type === 'ObjectProperty' && (prop.value.type === 'FunctionExpression' || prop.value.type === 'ArrowFunctionExpression')) fnNode = prop.value;
      const getterBody = fnNode ? nodeToCode(fnNode.body || fnNode, scriptContent) : nodeToCode(prop, scriptContent);
      options.computed.push({ name, has_setter: hasSetter, getter_body: (getterBody || '').slice(0, 200), dependencies_inferred: extractIdentifiers(getterBody || ''), return_type_inferred: null });
    }
  }

  const watchProp = getObjectPropertyByName(objectNode, 'watch');
  if (watchProp && watchProp.value && watchProp.value.type === 'ObjectExpression') {
    for (const prop of watchProp.value.properties || []) {
      if (prop.type !== 'ObjectProperty' && prop.type !== 'ObjectMethod') continue;
      const expression = propertyName(prop);
      let deep = false;
      let immediate = false;
      let handlerName = '';
      let handlerBody = '';
      if (prop.type === 'ObjectMethod') {
        handlerBody = nodeToCode(prop.body, scriptContent);
      } else if (prop.value.type === 'Identifier') {
        handlerName = prop.value.name;
      } else if (prop.value.type === 'ObjectExpression') {
        for (const inner of prop.value.properties || []) {
          const innerName = propertyName(inner);
          if (innerName === 'deep' && inner.value.type === 'BooleanLiteral') deep = inner.value.value;
          if (innerName === 'immediate' && inner.value.type === 'BooleanLiteral') immediate = inner.value.value;
          if (innerName === 'handler') {
            handlerName = inner.value.type === 'Identifier' ? inner.value.name : handlerName;
            handlerBody = nodeToCode(inner.value, scriptContent);
          }
        }
      }
      options.watch.push({ expression, deep, immediate, handler_type: handlerName ? 'method_name' : 'object_config', handler_name: handlerName, handler_body: (handlerBody || '').slice(0, 200) });
    }
  }

  const methodsProp = getObjectPropertyByName(objectNode, 'methods');
  if (methodsProp && methodsProp.value && methodsProp.value.type === 'ObjectExpression') {
    for (const prop of methodsProp.value.properties || []) {
      if (prop.type === 'ObjectMethod') {
        options.methods.push(extractFunctionInfo(propertyName(prop), prop, scriptContent));
      } else if (prop.type === 'ObjectProperty' && (prop.value.type === 'FunctionExpression' || prop.value.type === 'ArrowFunctionExpression')) {
        options.methods.push(extractFunctionInfo(propertyName(prop), prop.value, scriptContent));
      }
    }
  }

  const lifecycleNames = ['beforeCreate','created','beforeMount','mounted','beforeUpdate','updated','beforeDestroy','destroyed','activated','deactivated','errorCaptured'];
  for (const lifecycleName of lifecycleNames) {
    const lifecycleProp = getObjectPropertyByName(objectNode, lifecycleName);
    if (!lifecycleProp) continue;
    const fnNode = lifecycleProp.type === 'ObjectMethod' ? lifecycleProp : lifecycleProp.value;
    if (!fnNode) continue;
    const body = nodeToCode(fnNode.body || fnNode, scriptContent);
    const wrapper = { type: 'File', program: { type: 'Program', body: [{ type: 'ExpressionStatement', expression: fnNode }] } };
    const usage = collectThisReadsWrites(wrapper, scriptContent);
    options.lifecycle_hooks.push({
      vue_hook: lifecycleName,
      san_hook: ({ beforeCreate: 'compiled', created: 'inited', beforeMount: 'created', mounted: 'attached', updated: 'updated', destroyed: 'disposed', activated: 'attached', deactivated: 'disposed' })[lifecycleName] || null,
      body: (body || '').slice(0, 500),
      responsibilities_inferred: extractLifecycleResponsibilities(body || ''),
      state_reads: usage.reads_inferred,
      state_writes: usage.writes_inferred,
      cleanup_required: ['mounted', 'beforeDestroy', 'destroyed'].includes(lifecycleName),
    });
  }

  const emitsProp = getObjectPropertyByName(objectNode, 'emits');
  if (emitsProp) {
    if (emitsProp.value.type === 'ArrayExpression') {
      options.emits = (emitsProp.value.elements || []).filter(Boolean).filter(item => item.type === 'StringLiteral').map(item => item.value);
    } else if (emitsProp.value.type === 'ObjectExpression') {
      options.emits = (emitsProp.value.properties || []).map(propertyName).filter(Boolean);
    }
  }

  const filtersProp = getObjectPropertyByName(objectNode, 'filters');
  if (filtersProp && filtersProp.value && filtersProp.value.type === 'ObjectExpression') {
    for (const prop of filtersProp.value.properties || []) {
      if (prop.type === 'ObjectMethod') {
        options.filters.push({ name: propertyName(prop), params: (prop.params || []).map(item => item.name || nodeToCode(item, scriptContent)), body: nodeToCode(prop.body, scriptContent).slice(0, 200) });
      }
    }
  }

  for (const listName of ['provide', 'inject', 'mixins']) {
    const prop = getObjectPropertyByName(objectNode, listName);
    if (!prop || !prop.value) continue;
    if (prop.value.type === 'ArrayExpression') {
      options[`${listName}_keys`] = (prop.value.elements || []).filter(Boolean).map(item => literalValue(item)).filter(Boolean);
    }
  }
  const extendsProp = getObjectPropertyByName(objectNode, 'extends');
  if (extendsProp && extendsProp.value) options.extends = [nodeToCode(extendsProp.value, scriptContent)].filter(Boolean);

  return { export_info: exportInfo, options, imports, top_level_declarations: topLevelDeclarations };
}

const { descriptor } = compilerSfc.parse(source, { filename });
const template = descriptor.template;
const script = descriptor.script || descriptor.scriptSetup;
const styles = descriptor.styles || [];

const componentName = (script && /name\s*:\s*['"]([^'"]+)['"]/.exec(script.content || '')?.[1]) || filename.split('/').pop().replace(/\.vue$/i, '');
const result = {
  component_name: componentName,
  blocks: {
    template: template ? { content: template.content, start: template.loc?.start?.offset || 0, end: template.loc?.end?.offset || 0, attrs: template.attrs || {} } : null,
    script: script ? { content: script.content, start: script.loc?.start?.offset || 0, end: script.loc?.end?.offset || 0, attrs: script.attrs || {}, lang: script.lang || 'js' } : null,
    style: styles.map(style => ({ content: style.content, start: style.loc?.start?.offset || 0, end: style.loc?.end?.offset || 0, attrs: style.attrs || {}, lang: style.lang || 'css', scoped: !!style.scoped, module: !!style.module })),
  },
  analysis: {
    template: buildTemplateAnalysis(template ? template.content : ''),
    script: buildScriptAnalysis(script ? script.content : ''),
  },
};

process.stdout.write(JSON.stringify(result));
