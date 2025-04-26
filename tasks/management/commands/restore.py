import os
import sys
import json
import time
import shutil
import tarfile
import tempfile
import hashlib
import logging
import subprocess
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, DEFAULT_DB_ALIAS
from django.apps import apps
from django.core.management import call_command

# Set up logger
logger = logging.getLogger('tasks.restore')

class Command(BaseCommand):
    help = 'Restores the database and media files from a backup'

    def add_arguments(self, parser):
        # Required argument - the backup file to restore
        parser.add_argument(
            'backup_file',
            help='Path to the backup file (.tar, .tar.gz, or .gpg)'
        )
        
        # Database options
        parser.add_argument(
            '--database',
            default=DEFAULT_DB_ALIAS,
            help='Database to restore to (default: default)'
        )
        
        # Selective restore options
        parser.add_argument(
            '--skip-media',
            action='store_true',
            help='Skip media files restoration'
        )
        parser.add_argument(
            '--skip-database',
            action='store_true',
            help='Skip database restoration'
        )
        parser.add_argument(
            '--skip-fixtures',
            action='store_true',
            help='Skip fixtures restoration'
        )
        
        # Safety options
        parser.add_argument(
            '--no-backup-check',
            action='store_true',
            help='Skip backup integrity check (not recommended)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force restoration without confirmation'
        )
        
        # Media replacement option
        parser.add_argument(
            '--media-strategy',
            choices=['replace', 'merge', 'keep-existing'],
            default='replace',
            help='Strategy for handling existing media files'
        )
        
        # Decryption options
        parser.add_argument(
            '--passphrase',
            help='Passphrase for encrypted backups (will prompt if not provided)'
        )

    def handle(self, *args, **options):
        # Start timing
        start_time = time.time()
        
        # Setup
        self.verbosity = options['verbosity']
        self.backup_file = options['backup_file']
        self.database = options['database']
        self.skip_media = options['skip_media']
        self.skip_database = options['skip_database']
        self.skip_fixtures = options['skip_fixtures']
        self.media_strategy = options['media_strategy']
        self.force = options['force']
        
        # Validate the backup file exists
        if not os.path.exists(self.backup_file):
            raise CommandError(f"Backup file not found: {self.backup_file}")
        
        # Get confirmation unless forced
        if not self.force:
            self.stdout.write(self.style.WARNING(
                "WARNING: This will overwrite your current database and media files."
            ))
            self.stdout.write(self.style.WARNING(
                "Make sure you have a recent backup before proceeding."
            ))
            
            confirm = input("Are you sure you want to continue? [y/N]: ")
            if confirm.lower() != 'y':
                self.stdout.write(self.style.NOTICE("Restoration cancelled."))
                return
        
        try:
            # Create a temporary directory for extraction
            with tempfile.TemporaryDirectory() as temp_dir:
                # Handle encrypted backup if needed
                if self.backup_file.endswith('.gpg'):
                    self.backup_file = self._decrypt_backup(self.backup_file, temp_dir, options['passphrase'])
                
                # Extract the backup
                self.log("Extracting backup...", 1)
                extracted_path = self._extract_backup(self.backup_file, temp_dir)
                
                # Validate the backup
                if not options['no_backup_check']:
                    self._validate_backup(extracted_path)
                
                # Load the manifest
                manifest_path = os.path.join(extracted_path, 'manifest.json')
                if not os.path.exists(manifest_path):
                    raise CommandError("Invalid backup: manifest.json not found")
                
                with open(manifest_path) as f:
                    manifest = json.load(f)
                
                # Verify disk space
                self._verify_disk_space(extracted_path, manifest)
                
                # Restore components based on options
                if not self.skip_database and 'database' in manifest['components']:
                    self._restore_database(extracted_path, manifest)
                
                if not self.skip_media and 'media' in manifest['components']:
                    self._restore_media(extracted_path, manifest)
                
                if not self.skip_fixtures and 'fixtures' in manifest['components']:
                    self._restore_fixtures(extracted_path, manifest)
                
                # Cleanup any temporary files
                self.log("Cleaning up...", 1)
        
        except Exception as e:
            logger.error(f"Restoration failed: {str(e)}", exc_info=True)
            self.stderr.write(self.style.ERROR(f"Restoration failed: {str(e)}"))
            return
        
        # Calculate execution time
        execution_time = time.time() - start_time
        self.log(f"Restoration completed in {execution_time:.2f} seconds", 1)
        self.stdout.write(self.style.SUCCESS("Restoration completed successfully!"))

    def _decrypt_backup(self, encrypted_file, temp_dir, passphrase=None):
        """Decrypt a GPG-encrypted backup file"""
        self.log("Decrypting backup...", 1)
        
        if not shutil.which('gpg'):
            raise CommandError(
                "GPG command not found. Please install GPG to decrypt this backup."
            )
        
        # Output file path (in temp directory)
        decrypted_path = os.path.join(temp_dir, 'decrypted_backup')
        if encrypted_file.endswith('.tar.gz.gpg'):
            decrypted_path += '.tar.gz'
        elif encrypted_file.endswith('.tar.gpg'):
            decrypted_path += '.tar'
        else:
            decrypted_path += '.tar'  # Default to .tar
        
        try:
            # Build command
            cmd = ['gpg', '--batch', '--yes', '--output', decrypted_path, '--decrypt', encrypted_file]
            
            # If passphrase is provided, use it
            env = os.environ.copy()
            if passphrase:
                # Create a temporary file with the passphrase
                passphrase_file = os.path.join(temp_dir, 'passphrase.txt')
                with open(passphrase_file, 'w') as f:
                    f.write(passphrase)
                
                cmd.extend(['--passphrase-file', passphrase_file])
            
            # Run GPG
            process = subprocess.run(cmd, env=env, capture_output=True)
            
            # Check for errors
            if process.returncode != 0:
                error_msg = process.stderr.decode() if process.stderr else "Unknown error"
                raise CommandError(f"Decryption failed: {error_msg}")
            
            self.log(f"Backup decrypted successfully", 2)
            
            return decrypted_path
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"GPG decryption failed: {error_msg}")
            raise CommandError(f"Decryption failed: {error_msg}")
        except Exception as e:
            logger.error(f"Decryption failed: {str(e)}")
            raise CommandError(f"Decryption failed: {str(e)}")
            
    def _extract_backup(self, backup_file, temp_dir):
        """Extract the backup archive to a temporary directory"""
        extract_path = os.path.join(temp_dir, 'extracted')
        os.makedirs(extract_path, exist_ok=True)
        
        try:
            with tarfile.open(backup_file) as tar:
                # List all files to be extracted
                members = tar.getmembers()
                
                # Extract files with progress indication
                total_files = len(members)
                for i, member in enumerate(members, 1):
                    if self.verbosity >= 2 and i % 100 == 0:
                        self.log(f"Extracting files... ({i}/{total_files})", 2)
                    tar.extract(member, path=extract_path)
                
            self.log(f"Extracted {total_files} files", 2)
            return extract_path
            
        except tarfile.ReadError:
            logger.error(f"Failed to extract {backup_file}: not a valid tar file")
            raise CommandError(f"Failed to extract {backup_file}: not a valid tar file")
        except Exception as e:
            logger.error(f"Extraction failed: {str(e)}")
            raise CommandError(f"Extraction failed: {str(e)}")

    def _validate_backup(self, extracted_path):
        """Validate the integrity of the backup using checksums"""
        self.log("Validating backup integrity...", 1)
        
        # Check if manifest exists
        manifest_path = os.path.join(extracted_path, 'manifest.json')
        if not os.path.exists(manifest_path):
            raise CommandError("Invalid backup: manifest.json not found")
        
        # Load manifest
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        # Verify component integrity
        if 'checksums' not in manifest:
            self.log("Warning: No checksums found in manifest. Skipping integrity check.", 1)
            return
        
        # Verify database checksums
        if 'database' in manifest['components']:
            db_component = manifest['components']['database']
            
            if db_component['engine'] == 'sqlite3':
                # Verify SQLite file checksum
                db_file = os.path.join(extracted_path, 'database', db_component['file'])
                expected_checksum = manifest['checksums']['database']
                actual_checksum = self._calculate_checksum(db_file)
                
                if expected_checksum != actual_checksum:
                    raise CommandError(f"Database file checksum mismatch. Backup may be corrupted.")
                
                self.log("Database checksum verified", 2)
                
            elif db_component['engine'] in ('postgresql', 'mysql'):
                # Verify SQL dump file checksum
                sql_file = os.path.join(extracted_path, 'database', db_component['file'])
                expected_checksum = manifest['checksums']['database']
                actual_checksum = self._calculate_checksum(sql_file)
                
                if expected_checksum != actual_checksum:
                    raise CommandError(f"Database dump checksum mismatch. Backup may be corrupted.")
                
                self.log("Database dump checksum verified", 2)
                
            elif db_component['engine'] == 'django_json':
                # Verify JSON files checksums
                for json_file in db_component.get('files', []):
                    file_path = os.path.join(extracted_path, 'database', json_file)
                    checksum_key = f"database_{json_file}"
                    
                    if checksum_key in manifest['checksums']:
                        expected_checksum = manifest['checksums'][checksum_key]
                        actual_checksum = self._calculate_checksum(file_path)
                        
                        if expected_checksum != actual_checksum:
                            raise CommandError(f"Database JSON file {json_file} checksum mismatch.")
                
                self.log("Database JSON files checksums verified", 2)
        
        # Verify manifest checksum (should be the last thing verified in the backup process)
        if 'manifest' in manifest['checksums']:
            # We need to verify against the original manifest without its checksum
            original_manifest = manifest.copy()
            del original_manifest['checksums']['manifest']
            
            # Write the original manifest to a temp file
            temp_manifest_path = os.path.join(extracted_path, 'manifest_verify.json')
            with open(temp_manifest_path, 'w') as f:
                json.dump(original_manifest, f, indent=2)
            
            # Calculate and verify checksum
            expected_checksum = manifest['checksums']['manifest']
            actual_checksum = self._calculate_checksum(temp_manifest_path)
            
            # Clean up temp file
            os.unlink(temp_manifest_path)
            
            if expected_checksum != actual_checksum:
                raise CommandError("Manifest checksum mismatch. Backup may be corrupted.")
            
            self.log("Manifest checksum verified", 2)
        
        self.log("Backup integrity validated successfully", 1)

    def _verify_disk_space(self, extracted_path, manifest):
        """Verify there's enough disk space for restoration"""
        self.log("Verifying disk space...", 1)
        
        # Calculate required space
        required_space = 0
        
        # Add database size
        if not self.skip_database and 'database' in manifest['components']:
            db_component = manifest['components']['database']
            if 'size' in db_component:
                required_space += db_component['size']
        
        # Add media size
        if not self.skip_media and 'media' in manifest['components']:
            media_component = manifest['components']['media']
            if 'total_size' in media_component:
                required_space += media_component['total_size']
        
        # Add safety margin (20%)
        required_space = int(required_space * 1.2)
        
        # Check available space
        if self.media_strategy == 'replace' and not self.skip_media:
            # Check media directory space
            media_dir = settings.MEDIA_ROOT
            available_space = shutil.disk_usage(media_dir).free
            
            if available_space < required_space:
                raise CommandError(
                    f"Not enough disk space. Required: {self._format_size(required_space)}, "
                    f"Available: {self._format_size(available_space)}"
                )
        
        # Check database directory space for SQLite
        if not self.skip_database:
            db_settings = settings.DATABASES[self.database]
            if 'sqlite3' in db_settings['ENGINE']:
                db_file = db_settings['NAME']
                if not os.path.isabs(db_file):
                    db_file = os.path.join(settings.BASE_DIR, db_file)
                
                db_dir = os.path.dirname(db_file)
                available_space = shutil.disk_usage(db_dir).free
                
                if available_space < required_space:
                    raise CommandError(
                        f"Not enough disk space for database. Required: {self._format_size(required_space)}, "
                        f"Available: {self._format_size(available_space)}"
                    )
        
        self.log(f"Disk space verification completed. Required: {self._format_size(required_space)}", 2)

    def _restore_database(self, extracted_path, manifest):
        """Restore the database from the backup"""
        self.log("Restoring database...", 1)
        
        if 'database' not in manifest['components']:
            raise CommandError("Database component not found in backup manifest")
        
        db_component = manifest['components']['database']
        db_settings = settings.DATABASES[self.database]
        db_engine = db_settings['ENGINE']
        
        # SQLite restoration
        if 'sqlite3' in db_engine:
            self._restore_sqlite_database(extracted_path, db_component, db_settings)
        
        # PostgreSQL restoration
        elif 'postgresql' in db_engine:
            self._restore_postgresql_database(extracted_path, db_component, db_settings)
        
        # MySQL restoration
        elif 'mysql' in db_engine:
            self._restore_mysql_database(extracted_path, db_component, db_settings)
        
        # JSON data restoration (Django dumpdata format)
        elif db_component['engine'] == 'django_json':
            self._restore_json_database(extracted_path, db_component, db_settings)
        
        else:
            raise CommandError(f"Unsupported database engine: {db_engine}")
        
        self.log("Database restoration completed", 1)
    
    def _restore_sqlite_database(self, extracted_path, db_component, db_settings):
        """Restore SQLite database from backup"""
        self.log("Restoring SQLite database...", 1)
        
        # Source file path
        src_file = os.path.join(extracted_path, 'database', db_component['file'])
        if not os.path.exists(src_file):
            raise CommandError(f"Database file not found in backup: {db_component['file']}")
        
        # Destination file path
        dst_file = db_settings['NAME']
        if not os.path.isabs(dst_file):
            dst_file = os.path.join(settings.BASE_DIR, dst_file)
        
        # Create backup of existing database if it exists
        if os.path.exists(dst_file):
            backup_file = f"{dst_file}.bak"
            self.log(f"Creating backup of existing database: {backup_file}", 2)
            shutil.copy2(dst_file, backup_file)
        
        # Close all database connections
        connections[self.database].close()
        
        try:
            # Copy the database file
            self.log(f"Copying database file from backup...", 2)
            shutil.copy2(src_file, dst_file)
            
            self.log("SQLite database restored successfully", 2)
            
        except Exception as e:
            # Restore from backup if something went wrong
            if os.path.exists(f"{dst_file}.bak"):
                self.log("Restoration failed. Restoring from backup...", 2)
                shutil.copy2(f"{dst_file}.bak", dst_file)
                
            logger.error(f"SQLite restoration failed: {str(e)}")
            raise CommandError(f"SQLite restoration failed: {str(e)}")
    
    def _restore_postgresql_database(self, extracted_path, db_component, db_settings):
        """Restore PostgreSQL database from SQL dump"""
        self.log("Restoring PostgreSQL database...", 1)
        
        # Source file path
        sql_file = os.path.join(extracted_path, 'database', db_component['file'])
        if not os.path.exists(sql_file):
            raise CommandError(f"Database dump file not found in backup: {db_component['file']}")
        
        try:
            # Drop and recreate database if possible
            self.log("Dropping existing database objects...", 2)
            
            # Close all database connections
            connections[self.database].close()
            
            # Use psql to restore
            cmd = [
                'psql',
                f"--username={db_settings['USER']}",
                f"--host={db_settings.get('HOST', 'localhost')}",
                f"--port={db_settings.get('PORT', '5432')}",
                f"--dbname={db_settings['NAME']}",
                '--quiet',
                '--single-transaction',
                '--no-password',
                '--file', sql_file
            ]
            
            # Set PGPASSWORD environment variable for password
            env = os.environ.copy()
            if 'PASSWORD' in db_settings and db_settings['PASSWORD']:
                env['PGPASSWORD'] = db_settings['PASSWORD']
            
            # Run psql command
            self.log("Executing SQL dump...", 2)
            process = subprocess.run(cmd, env=env, capture_output=True)
            
            # Check for errors
            if process.returncode != 0:
                error_msg = process.stderr.decode() if process.stderr else "Unknown error"
                raise CommandError(f"PostgreSQL restoration failed: {error_msg}")
            
            self.log("PostgreSQL database restored successfully", 2)
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"PostgreSQL restoration failed: {error_msg}")
            raise CommandError(f"PostgreSQL restoration failed: {error_msg}")
        except FileNotFoundError:
            logger.error("psql command not found")
            raise CommandError("psql command not found. Make sure PostgreSQL client tools are installed.")
        except Exception as e:
            logger.error(f"PostgreSQL restoration failed: {str(e)}")
            raise CommandError(f"PostgreSQL restoration failed: {str(e)}")
    
    def _restore_mysql_database(self, extracted_path, db_component, db_settings):
        """Restore MySQL database from SQL dump"""
        self.log("Restoring MySQL database...", 1)
        
        # Source file path
        sql_file = os.path.join(extracted_path, 'database', db_component['file'])
        if not os.path.exists(sql_file):
            raise CommandError(f"Database dump file not found in backup: {db_component['file']}")
        
        try:
            # Close all database connections
            connections[self.database].close()
            
            # Use mysql to restore
            cmd = [
                'mysql',
                f"--user={db_settings['USER']}",
                f"--host={db_settings.get('HOST', 'localhost')}",
                f"--port={db_settings.get('PORT', '3306')}",
                db_settings['NAME']
            ]
            
            # Set MYSQL_PWD environment variable for password
            env = os.environ.copy()
            if 'PASSWORD' in db_settings and db_settings['PASSWORD']:
                env['MYSQL_PWD'] = db_settings['PASSWORD']
            
            # Pipe SQL file to mysql command
            self.log("Executing SQL dump...", 2)
            with open(sql_file, 'rb') as f:
                process = subprocess.run(cmd, env=env, stdin=f, capture_output=True)
            
            # Check for errors
            if process.returncode != 0:
                error_msg = process.stderr.decode() if process.stderr else "Unknown error"
                raise CommandError(f"MySQL restoration failed: {error_msg}")
            
            self.log("MySQL database restored successfully", 2)
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"MySQL restoration failed: {error_msg}")
            raise CommandError(f"MySQL restoration failed: {error_msg}")
        except FileNotFoundError:
            logger.error("mysql command not found")
            raise CommandError("mysql command not found. Make sure MySQL client tools are installed.")
        except Exception as e:
            logger.error(f"MySQL restoration failed: {str(e)}")
            raise CommandError(f"MySQL restoration failed: {str(e)}")
    
    def _restore_json_database(self, extracted_path, db_component, db_settings):
        """Restore database from Django dumpdata JSON files"""
        self.log("Restoring database from JSON files...", 1)
        
        # Check if files list is available
        if 'files' not in db_component or not db_component['files']:
            raise CommandError("No JSON files found in backup manifest")
        
        # Directory containing JSON files
        db_dir = os.path.join(extracted_path, 'database')
        
        # Process each JSON file
        for json_file in db_component['files']:
            file_path = os.path.join(db_dir, json_file)
            if not os.path.exists(file_path):
                self.log(f"Warning: JSON file not found in backup: {json_file}", 2)
                continue
            
            # Extract app label from filename
            app_label = os.path.splitext(json_file)[0]
            
            try:
                # Use Django's loaddata command to load the data
                self.log(f"Loading data for {app_label}...", 2)
                call_command('loaddata', file_path, verbosity=self.verbosity, database=self.database)
                
            except Exception as e:
                # Log error but continue with other files
                logger.error(f"Failed to load data for {app_label}: {str(e)}")
                self.log(f"Warning: Failed to load data for {app_label}: {str(e)}", 2)
        
        self.log("Database restoration from JSON files completed", 2)
    
    def _restore_media(self, extracted_path, manifest):
        """Restore media files from backup"""
        self.log("Restoring media files...", 1)
        
        if 'media' not in manifest['components']:
            raise CommandError("Media component not found in backup manifest")
        
        media_component = manifest['components']['media']
        backup_media_dir = os.path.join(extracted_path, 'media')
        
        if not os.path.exists(backup_media_dir):
            raise CommandError("Media directory not found in backup")
        
        # Target directory
        target_dir = settings.MEDIA_ROOT
        
        # Handle different strategies
        if self.media_strategy == 'replace':
            # Delete existing files if directory exists
            if os.path.exists(target_dir):
                self.log("Removing existing media files...", 2)
                for item in os.listdir(target_dir):
                    item_path = os.path.join(target_dir, item)
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.unlink(item_path)
                    except Exception as e:
                        self.log(f"Warning: Failed to remove {item_path}: {str(e)}", 2)
            else:
                os.makedirs(target_dir, exist_ok=True)
            
            # Copy all files from backup
            self._copy_directory(backup_media_dir, target_dir)
            
        elif self.media_strategy == 'merge':
            # Create target directory if it doesn't exist
            os.makedirs(target_dir, exist_ok=True)
            
            # Copy files from backup, overwriting existing files
            self._copy_directory(backup_media_dir, target_dir, overwrite=True)
            
        elif self.media_strategy == 'keep-existing':
            # Create target directory if it doesn't exist
            os.makedirs(target_dir, exist_ok=True)
            
            # Copy only files that don't exist
            self._copy_directory(backup_media_dir, target_dir, overwrite=False)
        
        self.log("Media files restoration completed", 1)
    
    def _copy_directory(self, src_dir, dst_dir, overwrite=True):
        """Copy directory with progress tracking"""
        # Count total files for progress tracking
        total_files = sum([len(files) for _, _, files in os.walk(src_dir)])
        copied_files = 0
        skipped_files = 0
        
        self.log(f"Copying {total_files} files...", 2)
        
        # Walk through source directory
        for root, dirs, files in os.walk(src_dir):
            # Create relative path
            rel_path = os.path.relpath(root, src_dir)
            dst_path = os.path.join(dst_dir, rel_path)
            
            # Create destination directory
            os.makedirs(dst_path, exist_ok=True)
            
            # Copy files
            for file in files:
                src_file = os.path.join(root, file)
                dst_file = os.path.join(dst_path, file)
                
                try:
                    # Check if file exists
                    if os.path.exists(dst_file) and not overwrite:
                        skipped_files += 1
                        continue
                    
                    # Copy the file
                    shutil.copy2(src_file, dst_file)
                    copied_files += 1
                    
                    # Show progress
                    if self.verbosity >= 2 and copied_files % 100 == 0:
                        self.log(f"Copied {copied_files}/{total_files} files...", 2)
                        
                except Exception as e:
                    logger.error(f"Failed to copy {src_file}: {str(e)}")
                    self.log(f"Warning: Failed to copy {file}: {str(e)}", 2)
        
        self.log(f"Files copied: {copied_files}, skipped: {skipped_files}", 2)
    
    def _restore_fixtures(self, extracted_path, manifest):
        """Restore fixtures from backup"""
        self.log("Restoring fixtures...", 1)
        
        if 'fixtures' not in manifest['components']:
            self.log("No fixtures found in backup manifest. Skipping.", 1)
            return
        
        fixtures_component = manifest['components']['fixtures']
        fixtures_dir = os.path.join(extracted_path, 'fixtures')
        
        if not os.path.exists(fixtures_dir):
            raise CommandError("Fixtures directory not found in backup")
        
        total_fixtures = 0
        loaded_fixtures = 0
        
        # Walk through the fixtures directory
        for app_dir in os.listdir(fixtures_dir):
            app_fixtures_path = os.path.join(fixtures_dir, app_dir)
            
            if not os.path.isdir(app_fixtures_path):
                continue
            
            # Process each fixture file
            for fixture_file in os.listdir(app_fixtures_path):
                if not fixture_file.endswith(('.json', '.xml', '.yaml', '.yml')):
                    continue
                
                total_fixtures += 1
                fixture_path = os.path.join(app_fixtures_path, fixture_file)
                
                try:
                    # Use Django's loaddata command to load the fixture
                    self.log(f"Loading fixture: {app_dir}/{fixture_file}", 2)
                    call_command('loaddata', fixture_path, verbosity=self.verbosity, database=self.database)
                    loaded_fixtures += 1
                    
                except Exception as e:
                    # Log error but continue with other fixtures
                    logger.error(f"Failed to load fixture {fixture_file}: {str(e)}")
                    self.log(f"Warning: Failed to load fixture {fixture_file}: {str(e)}", 2)
        
        if total_fixtures > 0:
            self.log(f"Fixtures restoration completed: {loaded_fixtures}/{total_fixtures} loaded", 1)
        else:
            self.log("No fixtures found to restore", 1)
    
    def _calculate_checksum(self, file_path):
        """Calculate SHA-256 checksum of a file"""
        sha256 = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
                    
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {str(e)}")
            return None
    
    def _format_size(self, size_bytes):
        """Format file size in a human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def log(self, message, verbosity_level=1):
        """Log message if verbosity is high enough"""
        if self.verbosity >= verbosity_level:
            if verbosity_level == 1:
                self.stdout.write(message)
            elif verbosity_level == 2:
                self.stdout.write(f"  - {message}")
            else:
                self.stdout.write(f"    > {message}")
