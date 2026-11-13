Backed up the SQLLITE3 database of Uther tracker by using SQLite's .backup command.
The application continued to run and the backup was made by read-only access.
The database backup was saved in /home/kidd/cloudops-lab/backups/demo-toon-20261031T125559Z.sqlite3.
The backup directory is restricted to my Linux user.

Integrity check returned ok. Backup contained two live character snapshots and one sample-data snapshot.

I also tested the backup with a live temp application on port 8081 to confirm that not only was the data okay but that the application could run specifically on the backup alone.


The restored instance’s /api/state endpoint returned:

Mode: live.
Live history count: 2.
Character: Uther, Silvermoon.
Level: 90.
Class and specialization: Retribution Paladin.
Item level: 324.
Achievement points: 1,925.

This demonstrated that the application could read and use the restored history. 

I used the AWS CLI with Moto, a local simulator, to practice uploading and downloading a database backup through an S3-compatible endpoint. I compared the checksums to confirm that the downloaded file matched the original. The exercise ran on my laptop.

This test confirms that I was able to take a full backup of the application, upload it to AWS, and download the backup and run the application with it.

