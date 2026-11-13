# Demo Notes

The screenshots in the main README were captured from my local K3s lab environment.

## Scaling Tests

I used a separate raid simulator to generate load and test Kubernetes scaling behavior. As CPU usage increased, Kubernetes scaled the deployment from one pod to three pods. After the load stopped, the deployment returned to a single pod.

| Test | Successful Requests | Failed Requests |
|--------|-------------------:|----------------:|
| Scaling | 10,192 | 0 |
| Pod Replacement | 10,107 | 0 |

These totals come from two earlier test runs. The screenshots that show each scaling step come from a later run on the same local K3s cluster.

I also tested pod replacement by removing a running pod and verifying that Kubernetes automatically created a replacement.

## Backup Testing

The application stores data in SQLite on persistent storage. I created scheduled backups and tested restoring the database to verify that character data could be recovered successfully.

## Recovery Notes

- [Process recovery test](../../notes/001-process-crash.md) shows how I verified that systemd restarted the tracker after a process failure.
- [Backup and restore test](../../notes/002-backup-and-restore.md) explains how I restored the SQLite database and verified a backup transfer using Moto.

