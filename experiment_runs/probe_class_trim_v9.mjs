// Read-only parser probe. No component execution, model or database access.
import {createRequire} from 'node:module'
import {attributeEdits} from '../migration_system/browser/attribute-syntax.mjs'
import {nonNullableRootState} from '../migration_system/browser/native-value.mjs'
const require=createRequire(process.cwd()+'/migration_system/engine/package.json')
for(const prefix of ['zone ',' ']){
 const source=`<template><div :class="'${prefix}' + (busy ? 'busy' : '')"><button @click="toggle">toggle</button></div></template><script>export default {data(){return {busy:false}},methods:{toggle(){this.busy=!this.busy}}}</script>`
 const code=`<template><div class="${prefix}{{busy ? 'busy' : ''}}"><button on-click="toggle">toggle</button></div></template><script>const san=require('san');module.exports=san.defineComponent({initData(){return {busy:false}},toggle(){this.data.set('busy',!this.data.get('busy'))}})</script>`
 const s=require('@vue/compiler-sfc').parse(source).descriptor.template.content
 const c=require('@vue/compiler-sfc').parse(code).descriptor.template.content
 console.log(JSON.stringify({prefix,nonnull:nonNullableRootState(source,'busy',require),source:require('@vue/compiler-dom').parse(s).children[0].props,target:require('@vue/compiler-dom').parse(c).children[0].props,edits:attributeEdits(source,code,require)}))
}
