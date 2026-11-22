// Source-bound native SELECT property lowering. No source execution, new user
// inputs, wrapper elements, private San APIs or dropped DOM observations.
// San sets value before options attach; Vue sets it afterwards. A public
// attached/updated hook restores that ordering, using an internal San ref.
function nativeSelectPlan(source,code,require){
  try{
    if(!/<select\b/i.test(source)||!/<select\b/i.test(code))return null
    const {parse}=require('@vue/compiler-sfc'),dom=require('@vue/compiler-dom'),babel=require('@babel/parser'),
      t=require('@babel/types'),traverse=require('@babel/traverse').default,generate=require('@babel/generator').default
    const a=parse(source).descriptor,b=parse(code).descriptor
    if(!a.template||!b.template||!b.script)return null
    const key=p=>!p.computed&&(p.key?.name??p.key?.value),one=(o,k)=>o?.properties?.filter(p=>key(p)===k).length===1?o.properties.find(p=>key(p)===k):null
    const script=babel.parse(b.script.content,{sourceType:'unambiguous'}),parents=[]
    traverse(script,{AssignmentExpression(p){const n=p.node
      if(n.operator==='='&&t.isMemberExpression(n.left)&&!n.left.computed&&n.left.object.name==='module'&&n.left.property.name==='exports'
          &&t.isCallExpression(n.right)&&t.isMemberExpression(n.right.callee)&&!n.right.callee.computed
          &&n.right.callee.object.name==='san'&&n.right.callee.property.name==='defineComponent'&&n.right.arguments.length===1&&t.isObjectExpression(n.right.arguments[0]))parents.push(n.right.arguments[0])
    }})
    if(parents.length!==1)return null
    const owner=parents[0],methodName='__migrationSyncSelectValues',prefix='__migrationNativeSelect'
    if(owner.properties.some(p=>!key(p))||new Set(owner.properties.map(key)).size!==owner.properties.length
        ||['ref','data','mixins','extends'].some(k=>one(owner,k))||source.includes(methodName)||source.includes(prefix))return null
    const nodes=text=>{const rows=[]
      const walk=(n,path,loop=false)=>{let index=0
        for(const c of n.children??[])if(c.type===1){const route=path+'/'+c.tag+'['+index+++']',inLoop=loop||c.props.some(p=>p.type===7&&p.name==='for'||p.type===6&&p.name==='s-for')
          rows.push({node:c,path:route,loop:inLoop});walk(c,route,inLoop)
        }
      };walk(dom.parse(text),'');return rows
    }
    const expected=nodes(a.template.content),actual=nodes(b.template.content),items=[]
    for(const row of expected){const n=row.node
      if(n.tag!=='select'||n.ns!==0||row.loop||n.props.some(p=>p.type===7&&p.name==='model'))continue
      const bindings=n.props.filter(p=>p.type===7&&p.name==='bind'&&p.arg?.content==='value'),binding=bindings[0]
      if(bindings.length!==1||binding.modifiers.length||!/^[A-Za-z_$][\w$]*$/.test(binding.exp?.content.trim()??''))continue
      const target=actual.filter(x=>x.path===row.path&&x.node.tag==='select'&&!x.loop)
      if(target.length!==1)continue
      const node=target[0].node,values=node.props.filter(p=>p.type===6&&p.name==='value'),field=binding.exp.content.trim(),value=values[0]?.value?.content.replace(/\s+/g,'')
      if(values.length!==1||!['{{'+field+'}}','{='+field+'=}'].includes(value))continue
      const ref=prefix+items.length,refs=node.props.filter(p=>p.type===6&&p.name==='s-ref')
      if(refs.length>1||refs.length===1&&refs[0].value?.content!==ref)continue
      items.push({node,field,ref,root:row.path==='/select[0]',hasRef:refs.length===1,value:values[0]})
    }
    if(!items.length)return null
    const normalize=n=>generate(JSON.parse(JSON.stringify(n,(k,v)=>['loc','start','end','extra','leadingComments','trailingComments','innerComments'].includes(k)?undefined:v)),{compact:true,comments:false}).code
    const body=items.map((item,i)=>{
      const ref='this.ref('+JSON.stringify(item.ref)+')'
      const lookup=item.root?ref+'||(this.el&&this.el.tagName==="SELECT"?this.el:null)':ref
      return 'const node'+i+'='+lookup+';if(node'+i+')node'+i+'.value=this.data.get('+JSON.stringify(item.field)+')==null?"":this.data.get('+JSON.stringify(item.field)+');'
    }).join('')
    const helper=babel.parseExpression('({'+methodName+'(){'+body+'}})').properties[0],existing=one(owner,methodName)
    const call=babel.parse('this.'+methodName+'();').program.body[0],edits=[],scriptBase=b.script.loc.start.offset
    const rule='source_native_select_post_option_value_v1'
    const add=(start,end,replacement)=>edits.push({start,end,replacement,rule})
    if(existing&&normalize(existing)!==normalize(helper))return null
    if(!existing&&(code.includes(methodName)||code.includes(prefix)))return null
    const hooks=['attached','updated'].map(name=>({name,method:one(owner,name)}))
    for(const hook of hooks){const n=hook.method
      if(n&&(!t.isObjectMethod(n)||n.kind!=='method'||n.params.length||n.async||n.generator))return null
      if(existing&&(!n||normalize(n.body.body[0])!==normalize(call)))return null
    }
    if(existing){
      let references=0,unsafe=false
      traverse(script,{MemberExpression(p){const n=p.node
        if(t.isThisExpression(n.object)&&!n.computed&&n.property.name===methodName){
          if(!hooks.some(h=>h.method.body.body[0]?.expression?.callee===n))unsafe=true
          references++
        }
      },AssignmentExpression(p){let n=p.node.left;while(t.isMemberExpression(n)&&t.isMemberExpression(n.object))n=n.object
        if(t.isMemberExpression(n)&&t.isThisExpression(n.object)&&['ref','el','data'].includes(n.property.name))unsafe=true
      }})
      if(unsafe||references!==2||items.some(i=>!i.hasRef||actual.filter(row=>row.node.props.some(p=>p.type===6&&p.name==='s-ref'&&p.value?.content===i.ref)).length!==1))return null
    }else{
      add(scriptBase+owner.start+1,scriptBase+owner.start+1,generate(helper).code+',\n')
      for(const hook of hooks){if(hook.method)add(scriptBase+hook.method.body.start+1,scriptBase+hook.method.body.start+1,'this.'+methodName+'();\n')
        else add(scriptBase+owner.start+1,scriptBase+owner.start+1,hook.name+'(){this.'+methodName+'();},\n')}
    }
    for(const item of items){let attributes=''
      if(!item.hasRef)attributes+=' s-ref="'+item.ref+'"'
      const reflected=item.node.props.filter(p=>p.type===6&&p.name==='VALUE')
      if(reflected.length>1||reflected.length===1&&reflected[0].value?.content.replace(/\s+/g,'')!=='{{'+item.field+'}}')return null
      if(!reflected.length)attributes+=' VALUE="{{'+item.field+'}}"'
      if(attributes){const at=b.template.loc.start.offset+item.value.loc.end.offset;add(at,at,attributes)}
    }
    return {edits,hasHelper:!!existing,methodName,methodStart:existing?.start,refs:items.map(i=>i.ref)}
  }catch{return null}
}
module.exports={nativeSelectPlan};
