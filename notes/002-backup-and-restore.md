## Backup and Recovery Testing

I tested the application's backup and recovery process using SQLite's backup functionality. After creating a backup, I restored it to a separate test instance and verified that the application could successfully load and use the stored data.

I also used the AWS CLI with Moto to simulate storing backups in an S3-compatible environment and confirmed file integrity after download.

The testing showed that application data could be backed up, restored, and recovered successfully.

