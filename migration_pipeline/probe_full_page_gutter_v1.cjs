/* Isolated counterfactual for the evaluator, NOT a component repair.
 * Only the controlled html scrollbar-gutter declaration is changed in memory.
 */
'use strict';
const fs=require('fs'),path=require('path'),{createRequire}=require('module');
const runnerPath=path.join(__dirname,'run_controlled_browser_pixel_v2.cjs');
async function probe(payload){
  const original=fs.readFileSync(runnerPath,'utf8');
  if(original.split('scrollbar-gutter:stable').length!==2)throw Error('Counterfactual scope changed');
  const code=original.replace('scrollbar-gutter:stable','scrollbar-gutter:auto');
  const loaded={exports:{}};
  new Function('require','module','__dirname',code)(createRequire(runnerPath),loaded,__dirname);
  const result=await loaded.exports.run(payload);
  fs.writeFileSync(path.join(payload.outputDir,'counterfactual_source.json'),JSON.stringify({
    changedComponentSource:false,changedProductionEvaluator:false,onlyChange:'controlled html scrollbar-gutter stable -> auto',
    recordedEnvironmentGutterIsBaseRunnerMetadataOnly:true,runnerSource:code},null,2),{flag:'wx'});
  return result;
}
if(require.main===module)probe(JSON.parse(fs.readFileSync(0,'utf8'))).then(r=>process.stdout.write(JSON.stringify(r))).catch(e=>{process.stderr.write(e.stack);process.exitCode=2;});
module.exports={probe};
