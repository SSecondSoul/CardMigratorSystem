# v7 adapter preflight failure (2026-11-13)

The first isolated adapter preflight failed before candidate generation/native runtime execution.
No model call, production modification, or batch score change.

```
ReferenceError: unknown node of type undefined with constructor "Array"
    at Printer.print (node_modules/@babel/generator/lib/printer.js:366:13)
    at Printer.generate (node_modules/@babel/generator/lib/printer.js:93:10)
    at generate (node_modules/@babel/generator/lib/index.js:104:18)
    at print (migration_pipeline/utils/source_render_call_semantics.cjs:9:16)
    at same (migration_pipeline/utils/source_render_call_semantics.cjs:13:19)
    at visit (migration_pipeline/probe_async_watcher_scope_adapter_v7.cjs:35:31)
    at run (migration_pipeline/probe_async_watcher_scope_adapter_v7.cjs:39:3)
```

This is an adapter implementation failure, not a canonical TaskManager defect.
Cause: schedule AST comparison attempted on an array instead of a CallExpression.
The frozen adapter records the failing implementation; restrict comparison to CallExpression before retrying.
