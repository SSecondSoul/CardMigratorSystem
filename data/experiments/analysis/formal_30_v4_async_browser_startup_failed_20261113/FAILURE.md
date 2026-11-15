# Isolated Edge startup attempt failed (2026-11-13)

The runner returned exit 1 before any browser observation report. Do not count a browser pass or a canonical component failure. No model requests, production changes, or original score changes.

```
Isolated temporary profile cleanup failed: Error: EPERM, Permission denied:
C:\Users\soul\AppData\Local\Temp\cardmig-browser-audit-QItqP4
Error: CDP connection closed
    at WebSocket.<anonymous> (migration_pipeline/run_async_watcher_browser_v1.cjs:59:77)
    at WebSocket.dispatchEvent (node:internal/event_target:789:26)
    at #onSocketClose (node:internal/deps/undici/undici:14403:14)
```

The private generated profile may remain; it is not the user's everyday browser profile. Exact failure stage/cause was not recorded by this first runner. Investigate launch/CDP diagnostics before attributing the failure to framework or component behavior.
