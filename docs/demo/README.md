# Demo notes

The [project preview](../../README.md#preview) shows all 16 slides. You can also [download the slideshow](slideshow.zip?raw=true), unzip it, and open `index.html` in your browser. The slideshow works offline.

## What I tested

I sent test requests to a separate raid simulator. As CPU use increased, Kubernetes added simulator pods. After the test traffic stopped, Kubernetes removed the extra pods. The slides show the full sequence from one pod to three and back to one.

| Test | Successful requests | Failures reported by the test client |
| --- | ---: | ---: |
| Scaling | 10,192 | 0 |
| Pod replacement | 10,107 | 0 |

The totals come from two earlier test runs. The staged screenshots show a later run. All tests ran on a single local Kubernetes node. The results describe those runs.

## Backup and recovery

The tracker saves character history in SQLite. The backup job exports the running database, checks its structure, and keeps up to five copies. I tested a restore in a separate copy of the app and checked that it could read the saved character history.
