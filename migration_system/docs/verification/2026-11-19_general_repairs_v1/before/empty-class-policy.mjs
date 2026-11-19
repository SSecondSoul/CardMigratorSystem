// Conservative, opt-in-by-analysis comparison policy, never a DOM mutation.
// Unknown syntax/dependencies retain exact attribute-presence comparison.
export function emptyClassPolicy(source,target,require){
  const {parse}=require('@vue/compiler-sfc'),parser=require('@babel/parser')
  const traverse=require('@babel/traverse').default,dom=require('@vue/compiler-dom'),postcss=require('postcss')
  const reasons=new Set(),block=reason=>reasons.add(reason)
  const globals=new Set(['undefined','NaN','Infinity','module','exports','String','Number','Boolean','Array','Object','Math','JSON'])
  const forbidden=new Set(['constructor','prototype','__proto__','window','document','globalThis','self','top','parent','frames',
    'eval','Function','Reflect','Proxy','className','classList','attributes','outerHTML','innerHTML','getAttribute','hasAttribute',
    'getAttributeNames','getAttributeNode','setAttribute','removeAttribute','toggleAttribute','querySelector','querySelectorAll',
    'matches','closest','getEl','el','ownerDocument','parentComponent','ref','slot','nodeType','nodeName','target','currentTarget'])
  const pureMethods=new Set(['find','findIndex','filter','map','some','every','includes','indexOf','lastIndexOf','slice','concat',
    'join','split','trim','toLowerCase','toUpperCase','toFixed','toString','reduce','keys','values','entries','fromEntries','assign',
    'freeze','is','isArray','from','abs','min','max','round','floor','ceil','parse','stringify'])
  const safeBindings=new Set(['class','key','value','checked','selected','disabled','title','id'])
  for(const [kind,code] of [['source',source],['target',target]]){
    try{
      const {descriptor,errors}=parse(code)
      if(errors.length||descriptor.scriptSetup||descriptor.script?.lang||descriptor.customBlocks.length)block(kind+':unsupported_sfc')
      if(descriptor.script?.src||descriptor.template?.src||descriptor.styles.some(s=>s.src))block(kind+':external_sfc_block')
      const script=descriptor.script?.content??'',ast=parser.parse(script,{sourceType:'unambiguous'})
      const localMethods=new Set()
      traverse(ast,{ObjectMethod(p){
        const name=p.node.key.name??p.node.key.value
        localMethods.add(name)
        if(p.node.computed||forbidden.has(String(name))||['render','template','mixins','extends','directives'].includes(name))block(kind+':runtime_extension_method')
      }})
      traverse(ast,{
        ReferencedIdentifier(p){
          const name=p.node.name
          if(forbidden.has(name)||(!p.scope.hasBinding(name,true)&&!globals.has(name)&&name!=='require'))block(kind+':unknown_or_dom_global')
        },
        ThisExpression(p){if(p.parent.type!=='MemberExpression'||p.parent.object!==p.node)block(kind+':instance_reflection')},
        MemberExpression(p){
          const n=p.node,key=n.computed?n.property.value:n.property.name
          if(n.computed&&!['StringLiteral','NumericLiteral'].includes(n.property.type))block(kind+':dynamic_member')
          if(forbidden.has(String(key))||(String(key).startsWith('$')&&key!=='$emit'))block(kind+':dom_or_reflective_member')
        },
        OptionalMemberExpression(){block(kind+':optional_member')},
        OptionalCallExpression(){block(kind+':optional_call')},
        ImportDeclaration(){block(kind+':import')},
        NewExpression(){block(kind+':constructor_call')},
        TaggedTemplateExpression(){block(kind+':tagged_template')},
        ObjectProperty(p){
          const key=p.node.key.name??p.node.key.value
          if(p.node.computed||forbidden.has(String(key)))block(kind+':reflective_property')
          if(key==='components'&&(p.node.value.type!=='ObjectExpression'||p.node.value.properties.length))block(kind+':inline_components')
          if(['directives','render','template','mixins','extends','setup','inject','provide'].includes(key))block(kind+':runtime_or_template_extension')
        },
        StringLiteral(p){if(forbidden.has(p.node.value)||/attr\s*\(/i.test(p.node.value))block(kind+':reflective_string')},
        CallExpression(p){
          const c=p.node.callee
          if(c.type==='Identifier'){
            if(c.name==='require'){
              if(kind!=='target'||p.node.arguments.length!==1||p.node.arguments[0].value!=='san')block(kind+':external_require')
            }else if(['String','Number','Boolean'].includes(c.name)){
              // Data-only primitive conversions are allowed.
            }else{
              const binding=p.scope.getBinding(c.name),n=binding?.path.node
              if(!n||!(n.type==='FunctionDeclaration'||(n.type==='VariableDeclarator'&&['ArrowFunctionExpression','FunctionExpression'].includes(n.init?.type))))block(kind+':unknown_call')
            }
          }else if(c.type==='MemberExpression'){
            const name=c.computed?c.property.value:c.property.name
            const receiver=c.object
            const data=receiver.type==='MemberExpression'&&receiver.object.type==='ThisExpression'&&receiver.property.name==='data'
            const san=kind==='target'&&receiver.type==='Identifier'&&receiver.name==='san'&&name==='defineComponent'
            const instance=receiver.type==='ThisExpression'&&(localMethods.has(name)||['$emit','fire'].includes(name))
            if(!san&&!(data&&['get','set'].includes(name))&&!instance&&!pureMethods.has(name))block(kind+':unknown_member_call')
          }else block(kind+':indirect_call')
        },
      })
      const template=dom.parse(descriptor.template?.content??'')
      function expression(text){
        try{
          const value=parser.parseExpression(text)
          traverse({type:'File',program:{type:'Program',sourceType:'module',body:[{type:'ExpressionStatement',expression:value}]}},{
            noScope:true,
            Identifier(p){if(forbidden.has(p.node.name))block(kind+':reflective_template_expression')},
            MemberExpression(p){if(p.node.computed&&!['StringLiteral','NumericLiteral'].includes(p.node.property.type))block(kind+':dynamic_template_member')},
            StringLiteral(p){if(forbidden.has(p.node.value))block(kind+':reflective_template_string')},
            OptionalMemberExpression(){block(kind+':optional_template_member')},
            OptionalCallExpression(){block(kind+':optional_template_call')},
            NewExpression(){block(kind+':template_constructor')},
            CallExpression(p){const c=p.node.callee,name=c.type==='Identifier'?c.name:c.type==='MemberExpression'?(c.computed?c.property.value:c.property.name):null
              if(!localMethods.has(name)&&!pureMethods.has(name)&&!['String','Number','Boolean'].includes(name))block(kind+':unknown_template_call')},
          })
        }catch(_){block(kind+':template_expression_unavailable')}
      }
      function visit(node){
        if(node.type===5)expression(node.content.content)
        if(node.type===1){
          if(['script','style','link','iframe','object','embed','component','slot'].includes(node.tag))block(kind+':active_template_element')
          for(const p of node.props){
            if(p.type===6&&(/^(?:on[a-z]|ref$|style$|href$|src$|srcdoc$|is$)/i.test(p.name)))block(kind+':active_template_attribute')
            if(p.type===7){
              if(!['bind','on','for','if','else-if','else','model','show'].includes(p.name))block(kind+':unknown_directive')
              if(p.name==='bind'&&(!p.arg?.isStatic||!safeBindings.has(p.arg.content)))block(kind+':unknown_bound_attribute')
              if(p.exp)expression(p.exp.content)
            }
            if(kind==='target'&&p.type===6&&p.value){
              if(p.name==='s-for'){
                if(!/^\s*[\w$]+(?:\s*,\s*[\w$]+)?\s+in\s+[\w$.]+(?:\s+trackby\s+[\w$.]+)?\s*$/.test(p.value.content))block(kind+':unknown_target_loop')
              }else if(p.name.startsWith('on-')||['s-if','s-else-if'].includes(p.name))expression(p.value.content.replace(/^(?:(?:stop|prevent):)+/,''))
              else if(p.value.content.includes('{{')){
                // Split only simple interpolations; braces in object literals
                // are rejected on analysis failure rather than guessed.
                const parts=p.value.content.matchAll(/\{\{([\s\S]*?)\}\}/g)
                for(const part of parts)expression(part[1])
              }
            }
          }
        }
        for(const child of node.children??[])visit(child)
      }
      visit(template)
      for(const style of descriptor.styles){
        if(style.lang&&style.lang!=='css')block(kind+':style_preprocessor')
        // Escaped selectors / attribute selectors / attr() are deliberately not
        // guessed. Blocking all attribute selectors is conservative, not complete.
        if(/[\\\[]/.test(style.content)||/attr\s*\(/i.test(style.content))block(kind+':css_attribute_observation')
        const css=postcss.parse(style.content)
        css.walkAtRules(rule=>{if(!['media','supports','keyframes'].includes(rule.name.toLowerCase()))block(kind+':css_external_or_unknown_at_rule')})
      }
    }catch(_){block(kind+':analysis_unavailable')}
  }
  return {version:'class_serialization_v2',approved:reasons.size===0,reasons:[...reasons].sort(),
    operations:['empty_class_presence','html_class_token_whitespace_order_duplicates'],
    scope:'comparison_only_self_contained_data_components_without_detected_DOM_or_CSS_attribute_observation',
    limitations:['raw_DOM_and_attribute_presence_retained','unknown_dependencies_keep_strict_comparison','not_arbitrary_external_DOM_observer_equivalence']}
}
