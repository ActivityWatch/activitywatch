# Windows ActivityWatch install

This watcher is intended for Windows machines that already have ActivityWatch installed.

## Install from this checkout

```powershell
py -3.12 -m pipx install . --python "C:\Users\Projeto2\AppData\Local\Programs\Python\Python312\python.exe"
```

The watcher command is installed as a GUI script, so ActivityWatch can start it without opening a console window:

```text
C:\Users\Projeto2\.local\bin\aw-watcher-cursor-busy.exe
```

The report command remains a console script:

```text
C:\Users\Projeto2\.local\bin\aw-cursor-busy-report.exe
```

## ActivityWatch autostart

Add the module name to:

```text
C:\Users\Projeto2\AppData\Local\activitywatch\activitywatch\aw-qt\aw-qt.toml
```

Expected setting:

```toml
[aw-qt]
autostart_modules = ["aw-server", "aw-watcher-afk", "aw-watcher-window", "aw-watcher-ask-away", "aw-watcher-cursor-busy"]
```

## Verify

```powershell
C:\Users\Projeto2\.local\bin\aw-cursor-busy-report.exe --today
```

