const fs = require('fs');
const path = require('path');
const san = require('san');

const root = path.resolve(__dirname, '..');
const dataRoot = path.join(root, 'data', 'datasets');
const design = JSON.parse(fs.readFileSync(path.join(dataRoot, 'features', 'design_matrix_2026-09-02_batch_30.json'), 'utf8'));
const manifest = JSON.parse(fs.readFileSync(path.join(dataRoot, 'dataset_manifest.json'), 'utf8'));
const complexity = JSON.parse(fs.readFileSync(path.join(dataRoot, 'features', 'complexity_tags.json'), 'utf8'));
const patterns = JSON.parse(fs.readFileSync(path.join(dataRoot, 'features', 'pattern_tags.json'), 'utf8'));
const notes = JSON.parse(fs.readFileSync(path.join(dataRoot, 'features', 'migration_notes.json'), 'utf8'));
const errors = [];
const warnings = [];
const levelDirs = { simple: '01_simple', medium: '02_medium', complex: '03_complex' };

function kebab(name) {
  return name.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
}

function extract(source, tag) {
  const match = source.match(new RegExp(`<${tag}(?: [^>]*)?>([\\s\\S]*?)</${tag}>`));
  return match ? match[1] : '';
}

function loadScript(source, file, sanMode) {
  const script = extract(source, 'script');
  const module = { exports: {} };
  try {
    new Function('require', 'module', 'exports', script)(name => name === 'san' ? san : require(name), module, module.exports);
  }
  catch (error) {
    errors.push(`${file}: script load failed: ${error.message}`);
    return null;
  }
  if (!module.exports || typeof module.exports !== (sanMode ? 'function' : 'object')) {
    errors.push(`${file}: unexpected module export`);
  }
  return module.exports;
}

function tokenSet(template) {
  const tokens = template.toLowerCase().match(/<\/?[a-z][a-z0-9-]*|v-[a-z-]+|s-[a-z-]+|@[a-z-]+|on-[a-z-]+|:[a-z-]+/g) || [];
  return new Set(tokens);
}

function normalizedSkeleton(template) {
  return template
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/\{\{[\s\S]*?\}\}/g, '{{}}')
    .replace(/>[^<]+</g, '><')
    .replace(/\s+(?:class|style|id|placeholder|title|value|checked|disabled|type|min|max)="[^"]*"/g, '')
    .replace(/\s+:key="[^"]*"/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function jaccard(left, right) {
  const union = new Set([...left, ...right]);
  const intersection = [...left].filter(item => right.has(item));
  return union.size ? intersection.length / union.size : 1;
}

if (design.batch_size !== 30 || design.components.length !== 30) errors.push('Design matrix must contain 30 components.');
for (const level of Object.keys(levelDirs)) {
  const count = design.components.filter(item => item.level === level).length;
  if (count !== 10) errors.push(`${level}: expected 10 design records, found ${count}`);
}
if (manifest.total_components !== manifest.components.length) errors.push('Manifest total_components does not match record count.');
if (new Set(manifest.components.map(item => item.id)).size !== manifest.components.length) errors.push('Manifest contains duplicate ids.');
const componentDirectories = Object.values(levelDirs).reduce((total, directory) => {
  return total + fs.readdirSync(path.join(dataRoot, 'components', directory), { withFileTypes: true }).filter(entry => entry.isDirectory()).length;
}, 0);
if (componentDirectories !== manifest.total_components) errors.push(`Component directory count ${componentDirectories} does not match manifest total ${manifest.total_components}.`);

const batchNames = new Set(design.components.map(item => item.component_name));
const signatures = new Set();
const templates = [];
for (const item of design.components) {
  const signature = [item.data_model, item.core_workflow, item.template_structure].join('|');
  if (signatures.has(signature)) errors.push(`${item.component_name}: duplicate design signature`);
  signatures.add(signature);
  const id = kebab(item.component_name).replace(/-/g, '_');
  const key = id.replace(/_/g, '-');
  const record = manifest.components.find(entry => entry.id === id);
  if (!record) {
    errors.push(`${item.component_name}: missing manifest record`);
    continue;
  }
  const componentRoot = path.join(dataRoot, 'components', levelDirs[item.level], item.component_name);
  const vueFile = path.join(componentRoot, 'vue', `${item.component_name}.vue`);
  const sanFile = path.join(componentRoot, 'san', `${item.component_name}.san`);
  const expectedPath = `components/${levelDirs[item.level]}/${item.component_name}/`;
  if (record.path !== expectedPath || record.vue_file !== `${item.component_name}.vue` || record.san_file !== `${item.component_name}.san` || record.complexity !== item.level) {
    errors.push(`${item.component_name}: manifest path/file/level mismatch`);
  }
  for (const file of [vueFile, sanFile]) if (!fs.existsSync(file)) errors.push(`${item.component_name}: missing ${file}`);
  if (!fs.existsSync(vueFile) || !fs.existsSync(sanFile)) continue;
  const vueSource = fs.readFileSync(vueFile, 'utf8');
  const sanSource = fs.readFileSync(sanFile, 'utf8');
  const vueExport = loadScript(vueSource, vueFile, false);
  const sanExport = loadScript(sanSource, sanFile, true);
  if (vueExport && vueExport.name !== item.component_name) errors.push(`${item.component_name}: Vue name mismatch`);
  if (sanExport && sanExport.prototype && sanExport.prototype.name && sanExport.prototype.name !== item.component_name) warnings.push(`${item.component_name}: inspect San component name`);
  if (vueExport && sanExport) {
    const vueProps = Object.keys(vueExport.props || {}).sort();
    const sanProps = Object.keys(sanExport.prototype.dataTypes || {}).sort();
    if (JSON.stringify(vueProps) !== JSON.stringify(sanProps)) errors.push(`${item.component_name}: Vue props and San dataTypes differ`);
  }
  const vueTemplate = extract(vueSource, 'template');
  const sanTemplate = extract(sanSource, 'template');
  templates.push({ name: item.component_name, level: item.level, tokens: tokenSet(vueTemplate) });
  try {
    const parsed = san.parseTemplate(sanTemplate.trim());
    if (!parsed || !parsed.children || parsed.children.length !== 1) errors.push(`${item.component_name}: San template must have one root node`);
  }
  catch (error) {
    errors.push(`${item.component_name}: San template parse failed: ${error.message}`);
  }
  if (sanExport) {
    try {
      sanExport.prototype.template = sanTemplate.trim();
      const instance = new sanExport();
      Object.keys(sanExport.prototype.computed || {}).forEach(name => instance.data.get(name));
      instance.dispose();
    }
    catch (error) {
      errors.push(`${item.component_name}: San initialization/computed evaluation failed: ${error.message}`);
    }
  }
  if (/\bv-|@[a-z]+|:key=|methods\s*:/.test(sanTemplate)) errors.push(`${item.component_name}: Vue syntax leaked into San template`);
  if (/\.(indexOf|slice|filter|map|reduce|join|toFixed|toLocaleString|trim|find|some|includes|padStart)\s*\(|\bMath\./.test(sanTemplate)) errors.push(`${item.component_name}: unsupported member/global call in San template`);
  if (/\b(?:GET|SET)_[A-Za-z]|\bEMIT\s*\(/.test(vueSource + sanSource)) errors.push(`${item.component_name}: unresolved generator macro`);
  const vueStyle = extract(vueSource, 'style').trim();
  const sanStyle = extract(sanSource, 'style').trim();
  if (vueStyle !== sanStyle) errors.push(`${item.component_name}: Vue/San styles differ`);
  for (const [label, source] of [['Vue', vueSource], ['San', sanSource]]) {
    const style = extract(source, 'style');
    const opens = (style.match(/\{/g) || []).length;
    const closes = (style.match(/\}/g) || []).length;
    if (opens !== closes) errors.push(`${item.component_name}: ${label} CSS brace mismatch`);
  }
  if (!/<style scoped>/.test(vueSource) || !/<style>/.test(sanSource)) errors.push(`${item.component_name}: style block mismatch`);
  const score = complexity.find(entry => entry.component_name === item.component_name);
  if (!score) errors.push(`${item.component_name}: missing complexity record`);
  else {
    const sum = Object.values(score.complexity_score).reduce((total, value) => total + value, 0);
    if (sum !== score.total_score || score.level !== item.level) errors.push(`${item.component_name}: invalid score metadata`);
  }
  if (!patterns[key]) errors.push(`${item.component_name}: missing pattern metadata`);
  if (!notes[key]) errors.push(`${item.component_name}: missing migration notes`);
}

for (let i = 0; i < templates.length; i += 1) {
  for (let j = i + 1; j < templates.length; j += 1) {
    const score = jaccard(templates[i].tokens, templates[j].tokens);
    if (score >= 0.96 && templates[i].level === templates[j].level) warnings.push(`High template-token similarity ${score.toFixed(2)}: ${templates[i].name} / ${templates[j].name}`);
  }
}

const existingVueFiles = [];
for (const directory of Object.values(levelDirs)) {
  const levelRoot = path.join(dataRoot, 'components', directory);
  for (const entry of fs.readdirSync(levelRoot, { withFileTypes: true })) {
    if (!entry.isDirectory() || batchNames.has(entry.name)) continue;
    const vueDir = path.join(levelRoot, entry.name, 'vue');
    if (!fs.existsSync(vueDir)) continue;
    for (const file of fs.readdirSync(vueDir).filter(name => name.endsWith('.vue'))) existingVueFiles.push(path.join(vueDir, file));
  }
}
const existingSkeletons = existingVueFiles.map(file => ({ file, skeleton: normalizedSkeleton(extract(fs.readFileSync(file, 'utf8'), 'template')) }));
for (const item of design.components) {
  const file = path.join(dataRoot, 'components', levelDirs[item.level], item.component_name, 'vue', `${item.component_name}.vue`);
  const skeleton = normalizedSkeleton(extract(fs.readFileSync(file, 'utf8'), 'template'));
  for (const existing of existingSkeletons) {
    if (skeleton === existing.skeleton) errors.push(`${item.component_name}: normalized template duplicates existing ${path.basename(existing.file, '.vue')}`);
  }
}

const result = {
  batch: design.components.length,
  byLevel: design.components.reduce((out, item) => { out[item.level] = (out[item.level] || 0) + 1; return out; }, {}),
  manifestTotal: manifest.total_components,
  scriptsLoaded: design.components.length * 2,
  errors,
  warnings
};
console.log(JSON.stringify(result, null, 2));
if (errors.length) process.exitCode = 1;
