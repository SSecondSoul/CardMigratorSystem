import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SanCompileResult:
    passed: bool
    skipped: bool = False
    reason: str = ""
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SanCompileChecker:
    def __init__(self, node_bin: str = "node", timeout: int = 20):
        self.node_bin = node_bin
        self.timeout = timeout

    def check_file(self, san_file_path: str | Path) -> SanCompileResult:
        path = Path(san_file_path)
        if not path.exists():
            return SanCompileResult(
                passed=False,
                reason="san_file_not_found",
                diagnostics=[{
                    "code": "san_file_not_found",
                    "message": f"San 文件不存在：{path}",
                    "severity": "error",
                }],
            )
        return self.check_source(path.read_text(encoding="utf-8"), source_name=str(path))

    def check_source(self, san_source: str, source_name: str = "inline.san") -> SanCompileResult:
        if not shutil.which(self.node_bin):
            return SanCompileResult(
                passed=True,
                skipped=True,
                reason="node_not_found",
                diagnostics=[{
                    "code": "node_not_found",
                    "message": f"未找到 Node 可执行文件：{self.node_bin}，已跳过 San 编译校验。",
                    "severity": "warning",
                }],
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            runner_path = Path(temp_dir) / "san_compile_check.js"
            input_path = Path(temp_dir) / "input.san"
            input_path.write_text(san_source, encoding="utf-8")
            runner_path.write_text(self._runner_script(), encoding="utf-8")

            try:
                completed = subprocess.run(
                    [self.node_bin, str(runner_path), str(input_path), source_name],
                    check=False,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                return SanCompileResult(
                    passed=False,
                    reason="san_compile_timeout",
                    stdout=exc.stdout or "",
                    stderr=exc.stderr or "",
                    diagnostics=[{
                        "code": "san_compile_timeout",
                        "message": f"San 编译校验超时：{self.timeout}s。",
                        "severity": "error",
                    }],
                )

        return self._parse_result(completed.stdout, completed.stderr, completed.returncode)

    def _parse_result(self, stdout: str, stderr: str, return_code: int) -> SanCompileResult:
        stdout = stdout or ""
        stderr = stderr or ""
        lines = [line for line in stdout.splitlines() if line.strip()]
        payload = None
        if lines:
            try:
                payload = json.loads(lines[-1])
            except json.JSONDecodeError:
                payload = None

        if not payload:
            return SanCompileResult(
                passed=False,
                reason="san_compile_runner_error",
                stdout=stdout,
                stderr=stderr,
                diagnostics=[{
                    "code": "san_compile_runner_error",
                    "message": "San 编译校验脚本没有返回合法 JSON。",
                    "severity": "error",
                    "detail": stderr or stdout,
                }],
            )

        diagnostics = payload.get("diagnostics", [])
        passed = bool(payload.get("passed")) and return_code == 0
        return SanCompileResult(
            passed=passed,
            skipped=bool(payload.get("skipped", False)),
            reason=payload.get("reason", ""),
            diagnostics=diagnostics,
            stdout=stdout,
            stderr=stderr,
        )

    def _runner_script(self) -> str:
        return r'''
const fs = require('fs');
const vm = require('vm');

const filePath = process.argv[2];
const sourceName = process.argv[3] || filePath;
const source = fs.readFileSync(filePath, 'utf8');

function emit(result) {
  process.stdout.write(JSON.stringify(result) + '\n');
}

function extractBlock(source, tag) {
  const pattern = new RegExp(`<${tag}\\b[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
  const match = source.match(pattern);
  return match ? match[1] : '';
}

function createSanStub() {
  const DataTypes = new Proxy({}, {
    get(target, prop) {
      if (!target[prop]) {
        target[prop] = { type: String(prop) };
      }
      return target[prop];
    }
  });

  return {
    DataTypes,
    defineComponent(definition) {
      if (!definition || typeof definition !== 'object') {
        throw new Error('san.defineComponent expects an object definition');
      }
      return definition;
    }
  };
}

const diagnostics = [];
const template = extractBlock(source, 'template');
const script = extractBlock(source, 'script');

if (!template.trim()) {
  diagnostics.push({
    code: 'missing_template_block',
    message: 'San 文件缺少可编译的 <template> 块。',
    severity: 'error'
  });
}

if (!script.trim()) {
  diagnostics.push({
    code: 'missing_script_block',
    message: 'San 文件缺少可执行的 <script> 块。',
    severity: 'error'
  });
}

if (script.trim()) {
  try {
    const sandbox = {
      module: { exports: {} },
      exports: {},
      require(name) {
        if (name === 'san') {
          return createSanStub();
        }
        return {};
      },
      console,
      setTimeout,
      clearTimeout,
      setInterval,
      clearInterval,
      Date,
      Math,
      JSON,
      Array,
      Object,
      String,
      Number,
      Boolean,
      RegExp,
      Promise
    };
    sandbox.exports = sandbox.module.exports;
    vm.createContext(sandbox);
    new vm.Script(script, { filename: sourceName + '#script' }).runInContext(sandbox, { timeout: 1000 });

    const component = sandbox.module.exports;
    if (!component || typeof component !== 'object') {
      diagnostics.push({
        code: 'invalid_module_exports',
        message: 'San script 没有导出组件对象。',
        severity: 'error'
      });
    }
  } catch (error) {
    diagnostics.push({
      code: 'san_script_compile_error',
      message: error.message,
      severity: 'error',
      stack: error.stack
    });
  }
}

const passed = diagnostics.filter(item => item.severity === 'error').length === 0;
emit({
  passed,
  skipped: false,
  reason: passed ? 'san_compile_passed' : 'san_compile_failed',
  diagnostics
});
process.exit(passed ? 0 : 1);
'''


def check_san_compile(
    san_source: str | None = None,
    san_file_path: str | Path | None = None,
    node_bin: str = "node",
    timeout: int = 20,
) -> SanCompileResult:
    checker = SanCompileChecker(node_bin=node_bin, timeout=timeout)
    if san_source is not None:
        return checker.check_source(san_source, source_name=str(san_file_path or "inline.san"))
    if san_file_path is not None:
        return checker.check_file(san_file_path)
    raise ValueError("check_san_compile requires san_source or san_file_path")
