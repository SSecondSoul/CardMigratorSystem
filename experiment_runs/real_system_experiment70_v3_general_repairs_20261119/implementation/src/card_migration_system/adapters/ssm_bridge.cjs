// Trusted parser programs only; uploaded script bodies are parsed, never evaluated.
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
const originalWrite = process.stdout.write.bind(process.stdout);
function finish(value) { originalWrite(JSON.stringify(value)); }
function blocked(code) { finish({ status: 'blocked', error: code }); }
try {
  const repository = process.argv[2];
  const filename = process.argv[3];
  const source = fs.readFileSync(0, 'utf8');
  const localRequire = createRequire(path.join(repository, 'package.json'));
  const lock = JSON.parse(fs.readFileSync(path.join(repository, 'package-lock.json'), 'utf8'));
  const names = ['@vue/compiler-sfc', '@vue/compiler-dom', '@babel/parser', '@babel/traverse'];
  const packages = {};
  for (const name of names) {
    const manifest = localRequire(`${name}/package.json`);
    if (lock.packages?.[`node_modules/${name}`]?.version !== manifest.version) {
      throw new Error('ssm_dependency_version_mismatch');
    }
    packages[name] = manifest.version;
  }
  const sfc = localRequire('@vue/compiler-sfc');
  const dom = localRequire('@vue/compiler-dom');
  const babel = localRequire('@babel/parser');
  const { descriptor, errors } = sfc.parse(source, { filename });
  if (errors.length) throw new Error('ssm_sfc_syntax_error');
  if (!descriptor.template) throw new Error('ssm_template_required');
  // The legacy bridge selects only descriptor.script and the first template root.
  // Reject these cases instead of silently dropping source information.
  if (descriptor.scriptSetup) throw new Error('ssm_script_setup_not_supported');
  if (descriptor.customBlocks.length) throw new Error('ssm_custom_blocks_not_supported');
  const blocks = [descriptor.template, descriptor.script, ...descriptor.styles].filter(Boolean);
  if (blocks.some(block => block.src)) throw new Error('ssm_external_blocks_not_supported');
  if (descriptor.template.lang && descriptor.template.lang !== 'html') throw new Error('ssm_template_language_not_supported');
  if (descriptor.script?.lang && !['js', 'ts', 'jsx', 'tsx'].includes(descriptor.script.lang)) throw new Error('ssm_script_language_not_supported');
  let template;
  try { template = dom.parse(descriptor.template.content); }
  catch { throw new Error('ssm_template_syntax_error'); }
  const roots = template.children.filter(node => node.type !== 3 && !(node.type === 2 && !node.content.trim()));
  if (roots.length !== 1 || roots[0].type !== 1) throw new Error('ssm_single_element_root_required');
  if (descriptor.script) {
    try { babel.parse(descriptor.script.content, { sourceType: 'unambiguous', plugins: ['jsx', 'typescript', 'decorators-legacy', 'classProperties', 'objectRestSpread'] }); }
    catch { throw new Error('ssm_script_syntax_error'); }
  }
  // Reuse the unchanged legacy bridge with the already-read stdin. Only its
  // trusted program is required; imports mentioned inside Vue are not loaded.
  const originalRead = fs.readFileSync;
  let output = '';
  fs.readFileSync = function (file, ...args) { return file === 0 ? source : originalRead.call(fs, file, ...args); };
  process.stdout.write = function (chunk) { output += chunk.toString(); return true; };
  const originalFilename = process.argv[2];
  try {
    process.argv[2] = filename;
    require(path.join(repository, 'SSM/extractors/parse_sfc.cjs'));
  } finally {
    fs.readFileSync = originalRead;
    process.stdout.write = originalWrite;
    process.argv[2] = originalFilename;
  }
  const parsed = JSON.parse(output);
  if (parsed.error || !parsed.analysis?.template || !parsed.analysis?.script) throw new Error('ssm_ast_bridge_invalid');
  const loaded = {};
  for (const name of Object.keys(require.cache).sort()) {
    if (name.startsWith(path.join(repository, 'node_modules') + path.sep)) {
      loaded[path.relative(repository, name).split(path.sep).join('/')] = crypto.createHash('sha256').update(fs.readFileSync(name)).digest('hex');
    }
  }
  finish({ status: 'completed', parsed, runtime: { node: process.version, packages, loaded_module_sha256: loaded } });
} catch (error) {
  const code = error.code === 'MODULE_NOT_FOUND' ? 'ssm_dependency_missing'
    : /^ssm_[a-z_]+$/.test(error.message) ? error.message : 'ssm_ast_bridge_failed';
  blocked(code); // Never echo source, parser excerpts, environment or stack traces.
}
