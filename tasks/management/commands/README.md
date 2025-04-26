# Task Manager Backup and Restore Commands

This directory contains custom Django management commands for backing up and restoring your Task Manager application's data.

## Overview

These commands allow you to:
- Create comprehensive backups of your database, media files, and fixtures
- Restore data from previously created backups
- Encrypt backups for sensitive data
- Verify backup integrity with checksum validation

## Prerequisites

### For Basic Functionality
- Python 3.8+
- Django 4.0+
- Access to the database (with appropriate permissions)
- Sufficient disk space

### For Advanced Features
- For PostgreSQL backups/restores: `pg_dump` and `psql` command-line tools
- For MySQL backups/restores: `mysqldump` and `mysql` command-line tools
- For encrypted backups: `gpg` command-line tool
- For compression: Python's built-in `tarfile` module (no additional installation required)

## Backup Command

### Basic Usage

```bash
python manage.py backup
```

This creates a compressed backup of the database and media files in the `backups` directory.

### Options

```
--output-dir OUTPUT_DIR    Directory where backups will be stored (default: project_root/backups)
--filename FILENAME        Custom backup filename (without extension)
--compress                 Compress the backup (default: True)
--compression-level [1-9]  Compression level (default: 6)
--skip-media               Skip media files backup
--skip-database            Skip database backup
--database DATABASE        Database to backup (default: default)
--encrypt                  Encrypt the backup using GPG (requires GPG installation)
--encrypt-key ENCRYPT_KEY  GPG key for encryption
--include-fixtures         Include fixtures in backup
--quiet                    Suppress output
--verbosity {0,1,2,3}      Verbosity level (default: 1)
```

### Examples

#### Create a simple backup
```bash
python manage.py backup
```

#### Create a backup with a custom filename in a specific directory
```bash
python manage.py backup --output-dir /path/to/backups --filename my_backup_2025_04_26
```

#### Backup only the database with high compression
```bash
python manage.py backup --skip-media --compression-level 9
```

#### Create an encrypted backup
```bash
python manage.py backup --encrypt
```

#### Create a backup including fixtures with detailed output
```bash
python manage.py backup --include-fixtures --verbosity 2
```

## Restore Command

### Basic Usage

```bash
python manage.py restore path/to/backup_file.tar.gz
```

### Options

```
backup_file                Path to the backup file (.tar, .tar.gz, or .gpg)
--database DATABASE        Database to restore to (default: default)
--skip-media               Skip media files restoration
--skip-database            Skip database restoration
--skip-fixtures            Skip fixtures restoration
--no-backup-check          Skip backup integrity check (not recommended)
--force                    Force restoration without confirmation
--media-strategy {replace,merge,keep-existing}
                          Strategy for handling existing media files (default: replace)
--passphrase PASSPHRASE    Passphrase for encrypted backups
--verbosity {0,1,2,3}      Verbosity level (default: 1)
```

### Examples

#### Restore a backup with confirmation prompt
```bash
python manage.py restore backups/backup_20250426_123456.tar.gz
```

#### Force restore without confirmation
```bash
python manage.py restore backups/backup_20250426_123456.tar.gz --force
```

#### Restore only media files, merging with existing files
```bash
python manage.py restore backups/backup_20250426_123456.tar.gz --skip-database --media-strategy merge
```

#### Restore an encrypted backup
```bash
python manage.py restore backups/backup_20250426_123456.tar.gz.gpg --passphrase mysecretpassword
```

## Backup Strategies

### Database Backup Strategies

1. **SQLite databases**: The entire database file is copied.
2. **PostgreSQL databases**: `pg_dump` is used to create a SQL dump file.
3. **MySQL/MariaDB databases**: `mysqldump` is used to create a SQL dump file.
4. **Other databases**: Django's `dumpdata` command is used to create JSON files for each app.

### Media Backup Strategy

The command copies all files from the `MEDIA_ROOT` directory, preserving the directory structure. Temporary files (starting with `.` or ending with `~`) are excluded.

### Restore Strategies

For the `--media-strategy` option:

1. **replace** (default): All existing media files are deleted before restoring.
2. **merge**: Files from backup are copied over, overwriting any existing files with the same name.
3. **keep-existing**: Only files that don't already exist are copied from the backup.

## Best Practices

1. **Regular Backups**: Schedule regular backups using cron jobs (Linux/Mac) or Task Scheduler (Windows).
2. **Off-Site Storage**: Store backup files in a different physical location or cloud storage.
3. **Encryption**: Use encryption for backups containing sensitive user data.
4. **Verification**: Regularly test restoring from backups to ensure they're valid.
5. **Retention Policy**: Implement a policy for how long to keep backups.

## Troubleshooting

### Backup Issues

1. **Insufficient Disk Space**:
   - Free up disk space or specify a different output directory with `--output-dir`.

2. **Database Dump Fails**:
   - Ensure you have proper database permissions.
   - For PostgreSQL/MySQL, make sure the client tools are installed and in your PATH.

3. **GPG Encryption Fails**:
   - Ensure GPG is installed and available in your PATH.
   - Make sure the specified key is available in your GPG keyring.

### Restore Issues

1. **Checksum Validation Fails**:
   - The backup may be corrupted; try using a different backup file.
   - Use `--no-backup-check` to skip validation (use with caution).

2. **Database Restore Fails**:
   - Check permissions on the database.
   - For PostgreSQL/MySQL, ensure the database exists and the user has appropriate permissions.

3. **Media Files Restore Fails**:
   - Check write permissions on the `MEDIA_ROOT` directory.
   - Ensure there's enough disk space available.

4. **Decryption Fails**:
   - Ensure you provided the correct passphrase.
   - Check if the GPG key used for encryption is available in your keyring.

## Performance Considerations

1. **Large Media Directories**: For sites with many media files, the backup process might be slow. Use `--skip-media` for quick database-only backups when needed.

2. **Compression Levels**: Higher compression levels (7-9) result in smaller files but take longer to create.

3. **Database Size**: For very large databases, restoration might take a significant amount of time.

## Security Notes

1. Backup files may contain sensitive information. Store them securely.
2. Use the `--encrypt` option for sensitive data.
3. Be careful with backup file permissions; restrict access to authorized users only.
4. When using PostgreSQL or MySQL, passwords might be passed via environment variables. This is a standard practice but should be considered in your security assessment.

