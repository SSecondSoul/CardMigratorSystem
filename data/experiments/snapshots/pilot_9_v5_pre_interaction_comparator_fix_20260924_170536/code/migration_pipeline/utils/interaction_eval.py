"""Deterministic, lightweight post-action comparison for Vue/San components.

This is intentionally not a browser automation layer. It executes the component
options against small in-memory Vue/San-compatible contexts so interaction
state and emitted payloads can be compared before a real-browser check.
"""

from dataclasses import dataclass, field
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


@dataclass
class InteractionEvalResult:
    passed: bool
    skipped: bool = False
    reason: str = ""
    scenarios: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)


def evaluate_interaction_scenario(
    vue_file_path: str | Path,
    san_file_path: str | Path,
    scenarios: list[dict[str, Any]],
    node_bin: str = "node",
    timeout: int = 20,
) -> InteractionEvalResult:
    if not shutil.which(node_bin):
        return InteractionEvalResult(
            passed=True,
            skipped=True,
            reason="node_not_found",
            diagnostics=[{"code": "node_not_found", "severity": "warning"}],
        )

    with tempfile.TemporaryDirectory() as temp_dir:
        runner = Path(temp_dir) / "interaction_eval.cjs"
        config = Path(temp_dir) / "interaction_config.json"
        runner.write_text(_runner_script(), encoding="utf-8")
        config.write_text(json.dumps({
            "vue": str(Path(vue_file_path).resolve()),
            "san": str(Path(san_file_path).resolve()),
            "scenarios": scenarios,
        }, ensure_ascii=False), encoding="utf-8")
        completed = subprocess.run(
            [node_bin, str(runner), str(config)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

    lines = [line for line in (completed.stdout or "").splitlines() if line.strip()]
    payload = json.loads(lines[-1]) if lines else {}
    return InteractionEvalResult(
        passed=bool(payload.get("passed")) and completed.returncode == 0,
        reason=payload.get("reason", ""),
        scenarios=payload.get("scenarios", []),
        diagnostics=payload.get("diagnostics", []),
    )


def _runner_script() -> str:
    return r'''
const fs = require('fs');
const vm = require('vm');
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

function block(source, tag) {
  const match = source.match(new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i'));
  return match ? match[1] : '';
}
function loadSource(file, san) {
  const source = fs.readFileSync(file, 'utf8');
  const script = block(source, 'script');
  const sandbox = {
    module: {exports: {}}, exports: {}, console, Date, Math, JSON, Array, Object,
    String, Number, Boolean, RegExp, Promise, setTimeout, clearTimeout,
    require(name) {
      if (san && name === 'san') {
        return {DataTypes: new Proxy({}, {get: (_, p) => ({type: String(p)})}),
          defineComponent(definition) { return definition; }};
      }
      return {};
    }
  };
  sandbox.exports = sandbox.module.exports;
  vm.createContext(sandbox);
  new vm.Script(script, {filename: file}).runInContext(sandbox, {timeout: 1000});
  return sandbox.module.exports;
}
function clone(value) { return JSON.parse(JSON.stringify(value)); }
function pathSet(target, path, value) {
  const parts = String(path).split('.'); let cursor = target;
  for (let i = 0; i < parts.length - 1; i++) cursor = cursor[parts[i]];
  cursor[parts[parts.length - 1]] = value;
}
function vueRuntime(component) {
  const data = {};
  if (component.props && typeof component.props === 'object' && !Array.isArray(component.props)) {
    Object.keys(component.props).forEach(name => {
      const d = component.props[name] && component.props[name].default;
      data[name] = typeof d === 'function' ? d() : d;
    });
  }
  const context = new Proxy(data, {get(t, p) {
    if (component.computed && component.computed[p]) return typeof component.computed[p] === 'function' ? component.computed[p].call(context) : component.computed[p].get.call(context);
    if (component.methods && component.methods[p]) return component.methods[p].bind(context);
    return t[p];
  }, set(t, p, v) { t[p] = v; return true; }});
  Object.assign(data, component.data ? component.data.call(context) : {});
  return {data, context, computed() { const out = {}; Object.keys(component.computed || {}).forEach(name => { out[name] = context[name]; }); return out; }, fired: []};
}
function sanRuntime(component) {
  const data = Object.assign({}, component.initData ? component.initData.call({data: {get: n => data[n], set: (n, v) => data[n] = v}}) : {});
  const fired = [];
  const store = {get: n => data[n], set: (n, v) => data[n] = v};
  const context = {data: store, fire: (name, payload) => fired.push({name, payload})};
  Object.keys(component || {}).forEach(name => { if (typeof component[name] === 'function') context[name] = component[name].bind(context); });
  return {data, context, computed() { const out = {}; Object.keys(component.computed || {}).forEach(name => { out[name] = component.computed[name].call(context); data[name] = out[name]; }); return out; }, fired};
}
function runRuntime(type, component, scenario) {
  const runtime = type === 'vue' ? vueRuntime(component) : sanRuntime(component);
  const snapshots = [];
  for (const step of scenario.steps || []) {
    if (step.op === 'set') pathSet(runtime.data, step.path, step.value);
    if (step.op === 'call') {
      const args = (step.args || []).map(arg => arg && arg.__event ? {preventDefault() {}} : arg);
      runtime.context[step.method](...args);
    }
    snapshots.push({data: clone(runtime.data), computed: clone(runtime.computed()), fired: clone(runtime.fired)});
  }
  return snapshots;
}
const vue = loadSource(config.vue, false);
const san = loadSource(config.san, true);
const scenarios = (config.scenarios || []).map(scenario => {
  const vueSnapshots = runRuntime('vue', vue, scenario);
  const sanSnapshots = runRuntime('san', san, scenario);
  const equal = JSON.stringify(vueSnapshots) === JSON.stringify(sanSnapshots);
  return {name: scenario.name || 'unnamed', passed: equal, vue: vueSnapshots, san: sanSnapshots};
});
const passed = scenarios.every(item => item.passed);
process.stdout.write(JSON.stringify({passed, reason: passed ? 'interaction_scenarios_passed' : 'interaction_scenarios_mismatch', scenarios}) + '\n');
'''
