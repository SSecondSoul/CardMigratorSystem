// Syntax lowering, source contracts and browser comparison share ONE proof.
// No dependency outside the self-contained bundle; no component is executed.
export function nativeSelectPlan(source,code,require){
  return require('./migration_pipeline/utils/native_select_semantics.cjs').nativeSelectPlan(source,code,require)
}
