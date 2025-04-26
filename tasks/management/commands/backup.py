import os
import sys
import json
import time
import datetime
import tarfile
import shutil
import tempfile
import hashlib
import logging
import subprocess
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, DEFAULT_DB_ALIAS
from django.apps import apps

# Set up logger
logger = logging.getLogger('tasks.backup')

class Command(BaseCommand):
    help = 'Creates a comprehensive backup of the database and media files'

    def add_arguments(self, parser):
        # Basic arguments
        parser.add_argument(
            '--output-dir',
            default=os.path.join(settings.BASE_DIR, 'backups'),
            help='Directory where backups will be stored'
        )
        parser.add_argument(
            '--filename',
            help='Custom backup filename (without extension)'
        )
        
        # Compression options
        parser.add_argument(
            '--compress',
            action='store_true',
            default=True,
            help='Compress the backup (default: True)'
        )
        parser.add_argument(
            '--compression-level',
            type=int,
            choices=range(1, 10),
            default=6,
            help='Compression level (1-9, default: 6)'
        )
        
        # Exclusion options
        parser.add_argument(
            '--skip-media',
            action='store_true',
            help='Skip media files backup'
        )
        parser.add_argument(
            '--skip-database',
            action='store_true',
            help='Skip database backup'
        )
        
        # Database options
        parser.add_argument(
            '--database',
            default=DEFAULT_DB_ALIAS,
            help='Database to backup (default: default)'
        )
        
        # Encryption option (for sensitive data)
        parser.add_argument(
            '--encrypt',
            action='store_true',
            help='Encrypt the backup using gpg (requires gpg to be installed)'
        )
        parser.add_argument(
            '--encrypt-key',
            help='GPG key for encryption'
        )
        
        # Extra options
        parser.add_argument(
            '--include-fixtures',
            action='store_true',
            help='Include fixtures in backup'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Suppress output'
        )

    def handle(self, *args, **options):
        # Start timing
        start_time = time.time()
        
        # Setup output directory
        output_dir = options['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        
        # Setup logging
        self.quiet = options['quiet']
        self.verbosity = options['verbosity']
        
        # Generate backup filename
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = options['filename'] or f"backup_{timestamp}"
        self.backup_path = os.path.join(output_dir, filename)
        
        # Create a temporary directory for building the backup
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = {
                'timestamp': timestamp,
                'django_version': settings.INSTALLED_APPS,
                'created_at': datetime.datetime.now().isoformat(),
                'components': {},
                'checksums': {}
            }
            
            try:
                # Backup database if not skipped
                if not options['skip_database']:
                    self._backup_database(temp_dir, options['database'], manifest)
                
                # Backup media if not skipped
                if not options['skip_media']:
                    self._backup_media(temp_dir, manifest)
                
                # Backup fixtures if requested
                if options['include_fixtures']:
                    self._backup_fixtures(temp_dir, manifest)
                
                # Write manifest file
                manifest_path = os.path.join(temp_dir, 'manifest.json')
                with open(manifest_path, 'w') as f:
                    json.dump(manifest, f, indent=2)
                
                # Calculate checksum for manifest
                manifest['checksums']['manifest'] = self._calculate_checksum(manifest_path)
                
                # Update manifest with final checksums
                with open(manifest_path, 'w') as f:
                    json.dump(manifest, f, indent=2)
                
                # Create archive
                if options['compress']:
                    self._create_compressed_archive(temp_dir, options['compression_level'])
                else:
                    self._create_uncompressed_archive(temp_dir)
                
                # Encrypt if requested
                if options['encrypt']:
                    self._encrypt_backup(options['encrypt_key'])
            
            except Exception as e:
                logger.error(f"Backup failed: {str(e)}", exc_info=True)
                raise CommandError(f"Backup failed: {str(e)}")
        
        # Calculate execution time
        execution_time = time.time() - start_time
        self.log(f"Backup completed in {execution_time:.2f} seconds", 1)
        self.log(f"Backup saved to: {self.backup_path}", 1)
        
        # Return the path to the backup file for potential further processing
        return self.backup_path

    def _backup_database(self, temp_dir, database, manifest):
        """Backup the database"""
        self.log("Backing up database...", 1)
        db_dir = os.path.join(temp_dir, 'database')
        os.makedirs(db_dir, exist_ok=True)
        
        db_settings = settings.DATABASES[database]
        db_engine = db_settings['ENGINE']
        
        # Output file for SQL dump
        sql_file = os.path.join(db_dir, f"{database}_dump.sql")
        
        # Handle different database engines
        if 'sqlite3' in db_engine:
            # For SQLite, we can just copy the file
            db_file = db_settings['NAME']
            if not os.path.isabs(db_file):
                db_file = os.path.join(settings.BASE_DIR, db_file)
            
            # Copy the database file
            db_copy = os.path.join(db_dir, os.path.basename(db_file))
            shutil.copy2(db_file, db_copy)
            
            # Add to manifest
            manifest['components']['database'] = {
                'engine': 'sqlite3',
                'file': os.path.basename(db_file),
                'size': os.path.getsize(db_copy)
            }
            manifest['checksums']['database'] = self._calculate_checksum(db_copy)
            
            self.log(f"SQLite database backed up: {os.path.basename(db_file)}", 2)
        
        elif 'postgresql' in db_engine:
            # Use pg_dump for PostgreSQL
            self._pg_dump(db_settings, sql_file)
            
            # Add to manifest
            manifest['components']['database'] = {
                'engine': 'postgresql',
                'file': os.path.basename(sql_file),
                'size': os.path.getsize(sql_file)
            }
            manifest['checksums']['database'] = self._calculate_checksum(sql_file)
            
            self.log(f"PostgreSQL database dumped to: {os.path.basename(sql_file)}", 2)
        
        elif 'mysql' in db_engine:
            # Use mysqldump for MySQL/MariaDB
            self._mysql_dump(db_settings, sql_file)
            
            # Add to manifest
            manifest['components']['database'] = {
                'engine': 'mysql',
                'file': os.path.basename(sql_file),
                'size': os.path.getsize(sql_file)
            }
            manifest['checksums']['database'] = self._calculate_checksum(sql_file)
            
            self.log(f"MySQL database dumped to: {os.path.basename(sql_file)}", 2)
        
        else:
            # For unsupported engines, use Django's dumpdata
            self._django_dumpdata(db_dir, database)
            
            # Add to manifest
            manifest['components']['database'] = {
                'engine': 'django_json',
                'format': 'json',
                'files': []
            }
            
            # Calculate checksums for all JSON files
            for app_label in os.listdir(db_dir):
                if app_label.endswith('.json'):
                    file_path = os.path.join(db_dir, app_label)
                    manifest['components']['database']['files'].append(app_label)
                    manifest['checksums'][f"database_{app_label}"] = self._calculate_checksum(file_path)
            
            self.log("Database exported using Django's dumpdata", 2)

    def _pg_dump(self, db_settings, sql_file):
        """Export PostgreSQL database using pg_dump"""
        try:
            cmd = [
                'pg_dump',
                '--no-owner',
                '--no-acl',
                '--format=p',  # plain text format
                f"--username={db_settings['USER']}",
                f"--host={db_settings.get('HOST', 'localhost')}",
                f"--port={db_settings.get('PORT', '5432')}",
                f"--file={sql_file}",
                db_settings['NAME']
            ]
            
            # Set PGPASSWORD environment variable for password
            env = os.environ.copy()
            if 'PASSWORD' in db_settings and db_settings['PASSWORD']:
                env['PGPASSWORD'] = db_settings['PASSWORD']
            
            self.log(f"Running pg_dump...", 2)
            subprocess.run(cmd, env=env, check=True, capture_output=not self.verbosity > 2)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"pg_dump failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise CommandError(f"PostgreSQL backup failed: {e}")
        except FileNotFoundError:
            logger.error("pg_dump command not found")
            raise CommandError("pg_dump command not found. Make sure PostgreSQL client tools are installed.")

    def _mysql_dump(self, db_settings, sql_file):
        """Export MySQL database using mysqldump"""
        try:
            cmd = [
                'mysqldump',
                '--single-transaction',
                '--routines',
                '--events',
                '--triggers',
                f"--user={db_settings['USER']}",
                f"--host={db_settings.get('HOST', 'localhost')}",
                f"--port={db_settings.get('PORT', '3306')}",
                f"--result-file={sql_file}",
                db_settings['NAME']
            ]
            
            # Set MYSQL_PWD environment variable for password
            env = os.environ.copy()
            if 'PASSWORD' in db_settings and db_settings['PASSWORD']:
                env['MYSQL_PWD'] = db_settings['PASSWORD']
            
            self.log(f"Running mysqldump...", 2)
            subprocess.run(cmd, env=env, check=True, capture_output=not self.verbosity > 2)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"mysqldump failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise CommandError(f"MySQL backup failed: {e}")
        except FileNotFoundError:
            logger.error("mysqldump command not found")
            raise CommandError("mysqldump command not found. Make sure MySQL client tools are installed.")

    def _django_dumpdata(self, db_dir, database):
        """Export database using Django's dumpdata management command"""
        from django.core.management import call_command
        
        for app_config in apps.get_app_configs():
            app_label = app_config.label
            
            # Skip some built-in apps that don't need to be backed up
            if app_label in ('contenttypes', 'auth.permission', 'sessions', 'admin'):
                continue
            
            self.log(f"Dumping data for app: {app_label}", 2)
            output_file = os.path.join(db_dir, f"{app_label}.json")
            
            try:
                with open(output_file, 'w') as f:
                    call_command('dumpdata', app_label, '--database', database, 
                                 '--indent', '2', stdout=f)
            except Exception as e:
                # If an app fails, log it but continue with other apps
                logger.warning(f"Failed to dump data for {app_label}: {e}")
                self.log(f"Warning: Failed to dump data for {app_label}: {e}", 2)

    def _backup_media(self, temp_dir, manifest):
        """Backup media files"""
        self.log("Backing up media files...", 1)
        media_root = settings.MEDIA_ROOT
        
        if not os.path.exists(media_root):
            self.log("Media directory doesn't exist. Creating empty directory for backup.", 2)
            os.makedirs(media_root, exist_ok=True)
        
        # Copy media files to temp directory
        media_dir = os.path.join(temp_dir, 'media')
        
        # Track total files and size
        total_files = 0
        total_size = 0
        
        # Walk through the media directory and copy files
        for root, dirs, files in os.walk(media_root):
            # Skip .thumbnails and other cache directories
            if '.thumbnails' in dirs:
                dirs.remove('.thumbnails')
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            
            # Create relative path structure
            rel_path = os.path.relpath(root, media_root)
            target_dir = os.path.join(media_dir, rel_path)
            os.makedirs(target_dir, exist_ok=True)
            
            # Copy files
            for file in files:
                src_file = os.path.join(root, file)
                dst_file = os.path.join(target_dir, file)
                
                # Skip temporary files
                if file.startswith('.') or file.endswith('~'):
                    continue
                
                # Copy the file
                shutil.copy2(src_file, dst_file)
                total_files += 1
                total_size += os.path.getsize(src_file)
        
        # Add to manifest
        manifest['components']['media'] = {
            'path': 'media',
            'total_files': total_files,
            'total_size': total_size
        }
        
        # Log completion
        self.log(f"Media backup complete: {total_files} files, {self._format_size(total_size)}", 2)

    def _backup_fixtures(self, temp_dir, manifest):
        """Backup fixtures from all apps"""
        self.log("Backing up fixtures...", 1)
        fixtures_dir = os.path.join(temp_dir, 'fixtures')
        os.makedirs(fixtures_dir, exist_ok=True)
        
        fixtures_found = 0
        
        # Go through all installed apps
        for app_config in apps.get_app_configs():
            app_fixtures_dir = os.path.join(app_config.path, 'fixtures')
            if os.path.exists(app_fixtures_dir):
                # Copy fixtures to backup
                app_target_dir = os.path.join(fixtures_dir, app_config.label)
                os.makedirs(app_target_dir, exist_ok=True)
                
                # Copy all fixture files
                for fixture_file in os.listdir(app_fixtures_dir):
                    if fixture_file.endswith(('.json', '.xml', '.yaml', '.yml')):
                        src_file = os.path.join(app_fixtures_dir, fixture_file)
                        dst_file = os.path.join(app_target_dir, fixture_file)
                        shutil.copy2(src_file, dst_file)
                        fixtures_found += 1
        
        # Add to manifest
        if fixtures_found > 0:
            manifest['components']['fixtures'] = {
                'path': 'fixtures',
                'total_files': fixtures_found
            }
            self.log(f"Fixtures backup complete: {fixtures_found} files", 2)
        else:
            self.log("No fixtures found", 2)

    def _create_compressed_archive(self, temp_dir, compression_level):
        """Create a compressed tar archive of the backup"""
        self.log("Creating compressed archive...", 1)
        
        # Add .tar.gz extension to backup path
        archive_path = f"{self.backup_path}.tar.gz"
        
        try:
            with tarfile.open(archive_path, f"w:gz", compresslevel=compression_level) as tar:
                # Add all files in temp_dir to the archive
                tar.add(temp_dir, arcname='')
            
            # Update backup path
            self.backup_path = archive_path
            self.log(f"Compressed archive created: {os.path.basename(archive_path)}", 2)
            
        except Exception as e:
            logger.error(f"Failed to create compressed archive: {str(e)}")
            raise CommandError(f"Compression failed: {str(e)}")

    def _create_uncompressed_archive(self, temp_dir):
        """Create an uncompressed tar archive of the backup"""
        self.log("Creating uncompressed archive...", 1)
        
        # Add .tar extension to backup path
        archive_path = f"{self.backup_path}.tar"
        
        try:
            with tarfile.open(archive_path, "w") as tar:
                # Add all files in temp_dir to the archive
                tar.add(temp_dir, arcname='')
            
            # Update backup path
            self.backup_path = archive_path
            self.log(f"Uncompressed archive created: {os.path.basename(archive_path)}", 2)
            
        except Exception as e:
            logger.error(f"Failed to create uncompressed archive: {str(e)}")
            raise CommandError(f"Archive creation failed: {str(e)}")

    def _encrypt_backup(self, encrypt_key):
        """Encrypt the backup file using GPG"""
        self.log("Encrypting backup...", 1)
        
        if not shutil.which('gpg'):
            logger.error("GPG not found. Cannot encrypt backup.")
            raise CommandError(
                "GPG command not found. Please install GPG or disable encryption."
            )
        
        try:
            # Output file path
            encrypted_path = f"{self.backup_path}.gpg"
            
            # Build command
            cmd = ['gpg', '--batch', '--yes', '--output', encrypted_path]
            
            # Add recipient if key is provided
            if encrypt_key:
                cmd.extend(['--recipient', encrypt_key])
            else:
                # Symmetric encryption if no key provided
                cmd.append('--symmetric')
            
            # Add input file
            cmd.extend(['--encrypt', self.backup_path])
            
            # Run GPG
            subprocess.run(cmd, check=True, capture_output=not self.verbosity > 2)
            
            # If successful, remove unencrypted file and update path
            os.unlink(self.backup_path)
            self.backup_path = encrypted_path
            
            self.log(f"Backup encrypted: {os.path.basename(encrypted_path)}", 2)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"GPG encryption failed: {e.stderr.decode() if e.stderr else str(e)}")
            raise CommandError(f"Encryption failed: {str(e)}")
        except Exception as e:
            logger.error(f"Encryption failed: {str(e)}")
            raise CommandError(f"Encryption failed: {str(e)}")

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
        if not self.quiet and self.verbosity >= verbosity_level:
            self.stdout.write(message)
