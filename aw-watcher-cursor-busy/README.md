# aw-watcher-cursor-busy

ActivityWatch watcher for Windows that records time spent with the cursor in a busy/loading state.

It creates a bucket named `aw-watcher-cursor-busy_<hostname>` with event type `cursor.busy`.

## Usage

```powershell
aw-watcher-cursor-busy
```

Default behavior:

- polls the cursor every 250 ms;
- counts `IDC_WAIT` and `IDC_APPSTARTING`;
- attributes time to the window under the cursor;
- ignores busy periods shorter than 500 ms;
- sends ActivityWatch heartbeats with a 1 second pulsetime.

## Report

```powershell
aw-cursor-busy-report --today
```

The report groups recorded busy time by application.

