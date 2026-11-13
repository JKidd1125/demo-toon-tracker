## Process Recovery Testing

I simulated an application crash by stopping the tracker's Python process. Systemd automatically restarted the service and created a new process without requiring manual action.

After the restart, I confirmed the application was healthy and responding normally through the `/healthz` endpoint.

This test demonstrated that the application could recover from a process failure automatically.
