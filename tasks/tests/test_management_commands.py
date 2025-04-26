import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest import mock
from io import StringIO
from pathlib import Path
from django.test import TestCase, override_settings
from django.core.management import call_command
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from tasks.models import Project, Task, Category, TaskAttachment
from tasks.choices import TaskStatus, TaskPriority
from tasks.management.commands.backup import Command as BackupCommand
from tasks.management.commands.restore import Command as RestoreCommand

User = get_user_model()


class BaseBackupRestoreTestCase(TestCase):
    """Base test case for backup and restore tests with common setup."""
    
    def setUp(self):
        # Create temp dirs for tests
        self.test_backup_dir = tempfile.mkdtemp()
        self.test_media_dir = tempfile.mkdtemp()
        self.original_media_root = settings.MEDIA_ROOT
        
        # Override media root for tests
        self._override_media_root = override_settings(MEDIA_ROOT=self.test_media_dir)
        self._override_media_root.enable()
        
        # Create test data
        self.create_test_data()
        
        # Mock subprocess for database dumps
        self.subprocess_mock = mock.patch('subprocess.run')
        self.subprocess_run_mock = self.subprocess_mock.start()
        self.subprocess_run_mock.return_value.returncode = 0
        
        # Redirect stdout/stderr for command output capture
        self.stdout = StringIO()
        self.stderr = StringIO()
        self.old_stdout, sys.stdout = sys.stdout, self.stdout
        self.old_stderr, sys.stderr = sys.stderr, self.stderr
    
    def tearDown(self):
        # Clean up temp dirs
        shutil.rmtree(self.test_backup_dir, ignore_errors=True)
        shutil.rmtree(self.test_media_dir, ignore_errors=True)
        
        # Restore settings
        self._override_media_root.disable()
        
        # Stop mocks
        self.subprocess_mock.stop()
        
        # Restore stdout/stderr
        sys.stdout, sys.stderr = self.old_stdout, self.old_stderr
    
    def create_test_data(self):
        """Create test data for backup/restore tests."""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        # Create test categories
        self.category1 = Category.objects.create(
            name="Test Category 1",
            description="Test description 1"
        )
        self.category2 = Category.objects.create(
            name="Test Category 2",
            description="Test description 2",
            parent=self.category1
        )
        
        # Create test projects
        self.project1 = Project.objects.create(
            title="Test Project 1",
            description="Test project description 1",
            owner=self.user
        )
        self.project1.members.add(self.user)
        
        self.project2 = Project.objects.create(
            title="Test Project 2",
            description="Test project description 2",
            owner=self.user
        )
        
        # Create test tasks
        self.task1 = Task.objects.create(
            title="Test Task 1",
            description="Test task description 1",
            status=TaskStatus.TODO,
            priority=TaskPriority.HIGH,
            project=self.project1,
            category=self.category1,
            created_by=self.user,
            assigned_to=self.user
        )
        
        self.task2 = Task.objects.create(
            title="Test Task 2",
            description="Test task description 2",
            status=TaskStatus.IN_PROGRESS,
            priority=TaskPriority.MEDIUM,
            project=self.project2,
            category=self.category2,
            created_by=self.user
        )
        
        # Create test media files
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'task_attachments'), exist_ok=True)
        
        # Create a test file attachment
        test_file_content = b'Test file content'
        uploaded_file = SimpleUploadedFile(
            name='test_file.txt',
            content=test_file_content,
            content_type='text/plain'
        )
        
        self.attachment = TaskAttachment.objects.create(
            task=self.task1,
            file=uploaded_file,
            name="Test Attachment",
            uploaded_by=self.user
        )
    
    def count_test_objects(self):
        """Count test objects to compare before and after restore."""
        return {
            'users': User.objects.count(),
            'categories': Category.objects.count(),
            'projects': Project.objects.count(),
            'tasks': Task.objects.count(),
            'attachments': TaskAttachment.objects.count(),
        }


class BasicBackupRestoreTests(BaseBackupRestoreTestCase):
    """Test basic backup and restore functionality."""
    
    def test_basic_backup_command(self):
        """Test basic backup command creates a backup file."""
        # Run backup command
        backup_path = call_command(
            'backup',
            output_dir=self.test_backup_dir,
            filename='test_backup',
            verbosity=2
        )
        
        # Check if backup file exists
        expected_path = os.path.join(self.test_backup_dir, 'test_backup.tar.gz')
        self.assertTrue(os.path.exists(expected_path))
        
        # Check command output
        output = self.stdout.getvalue()
        self.assertIn("Backing up database", output)
        self.assertIn("Backing up media files", output)
        self.assertIn("Backup completed", output)
    
    @mock.patch('tarfile.open')
    @mock.patch('os.path.exists')
    def test_basic_restore_command(self, mock_exists, mock_tarfile):
        """Test basic restore command."""
        # Mock tarfile and extraction
        mock_exists.return_value = True
        mock_tar = mock.MagicMock()
        mock_tarfile.return_value.__enter__.return_value = mock_tar
        
        # Mock extracted path and manifest
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create fake manifest
            manifest = {
                'components': {
                    'database': {'engine': 'sqlite3', 'file': 'db.sqlite3'},
                    'media': {'path': 'media', 'total_files': 1}
                },
                'checksums': {'database': '1234567890abcdef'}
            }
            
            manifest_path = os.path.join(temp_dir, 'manifest.json')
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f)
            
            # Create database and media dirs
            os.makedirs(os.path.join(temp_dir, 'database'), exist_ok=True)
            os.makedirs(os.path.join(temp_dir, 'media'), exist_ok=True)
            
            # Mock extraction to use our temp directory
            with mock.patch('tempfile.TemporaryDirectory') as mock_tempdir:
                mock_tempdir.return_value.__enter__.return_value = temp_dir
                
                # Run restore command with --force to skip confirmation
                with mock.patch('tasks.management.commands.restore.Command._validate_backup'):
                    with mock.patch('tasks.management.commands.restore.Command._extract_backup') as mock_extract:
                        mock_extract.return_value = temp_dir
                        
                        # Mock restore methods
                        with mock.patch('tasks.management.commands.restore.Command._restore_database'):
                            with mock.patch('tasks.management.commands.restore.Command._restore_media'):
                                
                                # Call the restore command
                                call_command(
                                    'restore',
                                    os.path.join(self.test_backup_dir, 'test_backup.tar.gz'),
                                    force=True,
                                    verbosity=2
                                )
                                
                                # Check command output
                                output = self.stdout.getvalue()
                                self.assertIn("Extracting backup", output)
                                self.assertIn("Restoration completed", output)


class DatabaseBackupRestoreTests(BaseBackupRestoreTestCase):
    """Test database backup and restore functionality."""
    
    @mock.patch('tasks.management.commands.backup.Command._pg_dump')
    def test_postgresql_backup(self, mock_pg_dump):
        """Test PostgreSQL database backup."""
        # Override settings to use PostgreSQL
        with override_settings(DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': 'test_db',
                'USER': 'test_user',
                'PASSWORD': 'test_password',
                'HOST': 'localhost',
                'PORT': '5432',
            }
        }):
            # Run backup command
            call_command(
                'backup',
                output_dir=self.test_backup_dir,
                filename='pg_backup',
                skip_media=True  # Skip media to focus on DB backup
            )
            
            # Check if pg_dump was called
            mock_pg_dump.assert_called_once()
            
            # Check command output
            output = self.stdout.getvalue()
            self.assertIn("Backing up database", output)
    
    @mock.patch('tasks.management.commands.backup.Command._mysql_dump')
    def test_mysql_backup(self, mock_mysql_dump):
        """Test MySQL database backup."""
        # Override settings to use MySQL
        with override_settings(DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': 'test_db',
                'USER': 'test_user',
                'PASSWORD': 'test_password',
                'HOST': 'localhost',
                'PORT': '3306',
            }
        }):
            # Run backup command
            call_command(
                'backup',
                output_dir=self.test_backup_dir,
                filename='mysql_backup',
                skip_media=True  # Skip media to focus on DB backup
            )
            
            # Check if mysqldump was called
            mock_mysql_dump.assert_called_once()
            
            # Check command output
            output = self.stdout.getvalue()
            self.assertIn("Backing up database", output)
    
    @mock.patch('django.core.management.call_command')
    def test_json_database_restore(self, mock_call_command):
        """Test restoration from JSON files for unsupported database engines."""
        # Mock extracted path and manifest
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create fake manifest for JSON database backup
            manifest = {
                'components': {
                    'database': {
                        'engine': 'django_json',
                        'format': 'json',
                        'files': ['tasks.json', 'auth.json']
                    }
                }
            }
            
            # Create database directory with JSON files
            db_dir = os.path.join(temp_dir, 'database')
            os.makedirs(db_dir, exist_ok=True)
            
            # Create dummy JSON files
            with open(os.path.join(db_dir, 'tasks.json'), 'w') as f:
                f.write('{"tasks": []}')
            with open(os.path.join(db_dir, 'auth.json'), 'w') as f:
                f.write('{"users": []}')
            
            # Call the restore method directly
            restore_command = RestoreCommand()
            restore_command.database = 'default'
            restore_command.verbosity = 1
            restore_command.stdout = sys.stdout
            restore_command._restore_json_database(temp_dir, manifest['components']['database'], {})
            
            # Verify loaddata was called for each JSON file
            self.assertEqual(mock_call_command.call_count, 2)
            expected_calls = [
                mock.call('loaddata', os.path.join(db_dir, 'tasks.json'), verbosity=1, database='default'),
                mock.call('loaddata', os.path.join(db_dir, 'auth.json'), verbosity=1, database='default')
            ]
            mock_call_command.assert_has_calls(expected_calls, any_order=True)


class MediaBackupRestoreTests(BaseBackupRestoreTestCase):
    """Test media file backup and restore functionality."""
    
    def test_media_backup(self):
        """Test media files are properly backed up."""
        # Create additional test files in media directory
        test_dirs = ['test_dir1', 'test_dir2', 'test_dir1/subdir']
        for dir_name in test_dirs:
            os.makedirs(os.path.join(settings.MEDIA_ROOT, dir_name), exist_ok=True)
        
        test_files = [
            'test1.txt',
            'test_dir1/test2.txt',
            'test_dir1/subdir/test3.txt',
            'test_dir2/test4.txt'
        ]
        
        for file_path in test_files:
            full_path = os.path.join(settings.MEDIA_ROOT, file_path)
            with open(full_path, 'w') as f:
                f.write(f"Content for {file_path}")
        
        # Run backup command
        call_command(
            'backup',
            output_dir=self.test_backup_dir,
            filename='media_backup',
            skip_database=True  # Skip database to focus on media backup
        )
        
        # Check output
        output = self.stdout.getvalue()
        self.assertIn("Backing up media files", output)
        self.assertIn("Media backup complete", output)
    
    def test_media_restore_strategies(self):
        """Test different media restore strategies."""
        # Setup source and destination directories for testing restore strategies
        with tempfile.TemporaryDirectory() as source_dir:
            with tempfile.TemporaryDirectory() as dest_dir:
                # Create test files in source directory
                test_files = {
                    'file1.txt': 'Source content 1',
                    'file2.txt': 'Source content 2',
                    'subdir/file3.txt': 'Source content 3'
                }
                
                for file_path, content in test_files.items():
                    full_path = os.path.join(source_dir, file_path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, 'w') as f:
                        f.write(content)
                
                # Create test files in destination directory (some overlap)
                dest_files = {
                    'file2.txt': 'Dest content 2',  # Same name, different content
                    'file4.txt': 'Dest content 4',  # Unique to dest
                    'subdir/file5.txt': 'Dest content 5'  # Unique to dest
                }
                for file_path, content in dest_files.items():
                    full_path = os.path.join(dest_dir, file_path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, 'w') as f:
                        f.write(content)
                
                # Test 'replace' strategy
                restore_command = RestoreCommand()
                restore_command.media_strategy = 'replace'
                restore_command.verbosity = 2
                restore_command.stdout = sys.stdout
                
                manifest = {'components': {'media': {'path': 'media'}}}
                restore_command._copy_directory(source_dir, dest_dir)
                
                # Verify all source files exist in destination and dest-only files don't
                for file_path in test_files:
                    self.assertTrue(os.path.exists(os.path.join(dest_dir, file_path)))
                    with open(os.path.join(dest_dir, file_path)) as f:
                        self.assertEqual(f.read(), test_files[file_path])
                
                # Verify dest-only files no longer exist (were replaced)
                self.assertFalse(os.path.exists(os.path.join(dest_dir, 'file4.txt')))
                self.assertFalse(os.path.exists(os.path.join(dest_dir, 'subdir/file5.txt')))
    
    def test_media_edge_cases(self):
        """Test edge cases in media file handling."""
        # Create a temporary directory structure for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Edge case 1: Empty media directory
            backup_dir = os.path.join(temp_dir, 'backup')
            empty_media_dir = os.path.join(temp_dir, 'empty_media')
            os.makedirs(backup_dir, exist_ok=True)
            os.makedirs(empty_media_dir, exist_ok=True)
            
            # Create backup command and test empty media backup
            backup_command = BackupCommand()
            backup_command.stdout = sys.stdout
            backup_command.verbosity = 2
            
            # Override settings for test
            with override_settings(MEDIA_ROOT=empty_media_dir):
                with mock.patch('django.conf.settings.MEDIA_ROOT', empty_media_dir):
                    manifest = {}
                    backup_command._backup_media(backup_dir, manifest)
                    
                    # Check that media component was added to manifest
                    self.assertIn('media', manifest.get('components', {}))
                    # Check that total_files is 0
                    self.assertEqual(manifest['components']['media']['total_files'], 0)
            
            # Edge case 2: Missing permissions (simulate with read-only directory)
            readonly_dir = os.path.join(temp_dir, 'readonly')
            os.makedirs(readonly_dir, exist_ok=True)
            
            # Simulate permission error during file copy
            with mock.patch('shutil.copy2', side_effect=PermissionError("Permission denied")):
                with mock.patch('os.makedirs', return_value=None):  # Don't fail on makedirs
                    # Setup test file structure
                    test_file = os.path.join(readonly_dir, 'test.txt')
                    with open(test_file, 'w') as f:
                        f.write("Test content")
                    
                    # Test restore with permission errors
                    restore_command = RestoreCommand()
                    restore_command.stdout = sys.stdout
                    restore_command.verbosity = 2
                    
                    # Should not raise exception, but log the error
                    restore_command._copy_directory(readonly_dir, temp_dir)
                    
                    # Check output for warning
                    output = self.stdout.getvalue()
                    self.assertIn("Warning: Failed to copy", output)


class EncryptionBackupRestoreTests(BaseBackupRestoreTestCase):
    """Test backup encryption and decryption functionality."""
    
    @mock.patch('shutil.which')
    @mock.patch('subprocess.run')
    def test_backup_encryption(self, mock_subprocess_run, mock_which):
        """Test encrypting a backup file."""
        # Mock GPG availability
        mock_which.return_value = '/usr/bin/gpg'  # Simulate GPG being installed
        
        # Mock successful encryption
        mock_subprocess_run.return_value.returncode = 0
        
        # Create a temporary backup file to encrypt
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as temp_file:
            temp_file.write(b'Test backup content')
            backup_path = temp_file.name
        
        try:
            # Create backup command and test encryption
            backup_command = BackupCommand()
            backup_command.stdout = sys.stdout
            backup_command.backup_path = backup_path
            backup_command.verbosity = 2
            
            # Encrypt the backup
            backup_command._encrypt_backup('test@example.com')
            
            # Check that subprocess.run was called with gpg command
            mock_subprocess_run.assert_called_once()
            # Check that gpg command included --recipient
            self.assertIn('--recipient', mock_subprocess_run.call_args[0][0])
            self.assertIn('test@example.com', mock_subprocess_run.call_args[0][0])
            # Check that gpg command included --encrypt
            self.assertIn('--encrypt', mock_subprocess_run.call_args[0][0])
        finally:
            # Clean up
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    @mock.patch('shutil.which')
    @mock.patch('subprocess.run')
    def test_backup_encryption_without_key(self, mock_subprocess_run, mock_which):
        """Test encrypting a backup file without a specific key (symmetric encryption)."""
        # Mock GPG availability
        mock_which.return_value = '/usr/bin/gpg'
        
        # Mock successful encryption
        mock_subprocess_run.return_value.returncode = 0
        
        # Create a temporary backup file to encrypt
        with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as temp_file:
            temp_file.write(b'Test backup content')
            backup_path = temp_file.name
        
        try:
            # Create backup command and test encryption
            backup_command = BackupCommand()
            backup_command.stdout = sys.stdout
            backup_command.backup_path = backup_path
            backup_command.verbosity = 2
            
            # Encrypt the backup without a key (symmetric)
            backup_command._encrypt_backup(None)
            
            # Check that subprocess.run was called with gpg command
            mock_subprocess_run.assert_called_once()
            # Check that gpg command included --symmetric
            self.assertIn('--symmetric', mock_subprocess_run.call_args[0][0])
            # Check that gpg command included --encrypt
            self.assertIn('--encrypt', mock_subprocess_run.call_args[0][0])
        finally:
            # Clean up
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    @mock.patch('shutil.which')
    @mock.patch('subprocess.run')
    def test_backup_decrypt(self, mock_subprocess_run, mock_which):
        """Test decrypting an encrypted backup file."""
        # Mock GPG availability
        mock_which.return_value = '/usr/bin/gpg'
        
        # Mock successful decryption
        mock_subprocess_run.return_value.returncode = 0
        
        # Create a temporary encrypted backup file
        with tempfile.NamedTemporaryFile(suffix='.tar.gz.gpg', delete=False) as temp_file:
            temp_file.write(b'Fake encrypted content')
            encrypted_path = temp_file.name
        
        # Create temporary directory for decryption
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Create restore command
                restore_command = RestoreCommand()
                restore_command.stdout = sys.stdout
                restore_command.verbosity = 2
                
                # Decrypt the backup with a passphrase
                passphrase = "test_passphrase"
                decrypted_path = restore_command._decrypt_backup(encrypted_path, temp_dir, passphrase)
                
                # Check that subprocess.run was called with gpg command
                mock_subprocess_run.assert_called_once()
                # Check that gpg command included --decrypt
                self.assertIn('--decrypt', mock_subprocess_run.call_args[0][0])
                # Check that passphrase file was created (since we provided a passphrase)
                self.assertIn('--passphrase-file', mock_subprocess_run.call_args[0][0])
                
                # Check that decrypted path was returned
                self.assertTrue(decrypted_path.endswith('.tar.gz'))
            finally:
                # Clean up
                if os.path.exists(encrypted_path):
                    os.unlink(encrypted_path)
    
    @mock.patch('shutil.which')
    @mock.patch('subprocess.run')
    def test_encryption_error_handling(self, mock_subprocess_run, mock_which):
        """Test error handling during encryption/decryption."""
        # Test case 1: GPG not installed
        mock_which.return_value = None  # Simulate GPG not being installed
        
        backup_command = BackupCommand()
        backup_command.stdout = sys.stdout
        backup_command.backup_path = 'test_backup.tar.gz'
        
        # Should raise CommandError about GPG not being found
        with self.assertRaises(Exception) as context:
            backup_command._encrypt_backup('test@example.com')
        
        self.assertIn('GPG command not found', str(context.exception))
        
        # Test case 2: GPG encryption fails
        mock_which.return_value = '/usr/bin/gpg'  # GPG is installed
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stderr = b'GPG error: bad passphrase'
        
        # Should raise CommandError with the GPG error
        with self.assertRaises(Exception) as context:
            backup_command._encrypt_backup('test@example.com')
        
        self.assertIn('Encryption failed', str(context.exception))


class ErrorHandlingTests(BaseBackupRestoreTestCase):
    """Test error handling for both backup and restore operations."""
    
    def test_backup_file_permission_error(self):
        """Test backup handling of file permission errors."""
        # Mock os.makedirs to raise PermissionError
        with mock.patch('os.makedirs', side_effect=PermissionError("Permission denied")):
            # Should raise CommandError
            with self.assertRaises(Exception) as context:
                call_command(
                    'backup',
                    output_dir='/nonexistent/directory',
                    filename='test_backup'
                )
            
            # Check the error contains information about the permission error
            self.assertIn('Permission denied', str(context.exception))
    
    def test_restore_invalid_backup_file(self):
        """Test restore handling of invalid backup files."""
        # Create a temporary invalid backup file
        with tempfile.NamedTemporaryFile(suffix='.tar.gz') as temp_file:
            temp_file.write(b'This is not a valid tar file')
            temp_file.flush()
            
            # Should raise CommandError about invalid tar file
            with self.assertRaises(Exception) as context:
                call_command('restore', temp_file.name, force=True)
            
            # Check the error contains information about the invalid tar file
            self.assertIn('not a valid tar file', str(context.exception))
    
    def test_backup_disk_space_error(self):
        """Test backup handling of disk space errors."""
        # Mock shutil.disk_usage to return very small free space
        with mock.patch('shutil.disk_usage') as mock_disk_usage:
            # Mock very small free space
            mock_disk_usage.return_value = mock.Mock(free=1024)  # Only 1KB free
            
            # Mock database and media size calculation to be larger than available space
            with mock.patch('os.path.getsize', return_value=1024 * 1024):  # 1MB
                # Should raise CommandError about insufficient disk space
                with mock.patch('tasks.management.commands.restore.Command._verify_disk_space') as mock_verify:
                    mock_verify.side_effect = CommandError("Not enough disk space")
                    
                    with self.assertRaises(Exception) as context:
                        # Create a simple manifest to test disk space verification
                        manifest = {
                            'components': {
                                'database': {'size': 1024 * 1024},  # 1MB
                                'media': {'total_size': 1024 * 1024}  # 1MB
                            }
                        }
                        
                        # Create a restore command instance and call verify_disk_space directly
                        restore_command = RestoreCommand()
                        restore_command.media_strategy = 'replace'
                        restore_command.skip_media = False
                        restore_command.skip_database = False
                        
                        # Call the verify_disk_space method with our mocked manifest
                        result = restore_command._verify_disk_space('/fake/path', manifest)
        
    def test_corrupted_manifest(self):
        """Test handling of corrupted manifest files."""
        # Create a temporary directory with an invalid JSON manifest
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = os.path.join(temp_dir, 'manifest.json')
            
            # Write invalid JSON to the manifest file
            with open(manifest_path, 'w') as f:
                f.write('{"this": "is not valid JSON')
            
            # Create restore command and test validation
            restore_command = RestoreCommand()
            restore_command.stdout = sys.stdout
            restore_command.verbosity = 1
            
            # Should raise an exception about invalid JSON
            with self.assertRaises(Exception) as context:
                with mock.patch('tasks.management.commands.restore.Command._extract_backup') as mock_extract:
                    mock_extract.return_value = temp_dir
                    
                    restore_command.handle(
                        os.path.join(self.test_backup_dir, 'test_backup.tar.gz'),
                        force=True,
                        no_backup_check=True,  # Skip validation to get to manifest reading
                        database='default',
                        skip_media=False,
                        skip_database=False,
                        skip_fixtures=True,
                        media_strategy='replace',
                        passphrase=None,
                        verbosity=1
                    )
            
            # Check that the error message mentions JSON
            self.assertIn('JSON', str(context.exception))
    
    def test_incomplete_backup(self):
        """Test handling of incomplete backup files."""
        # Create a temporary directory with a valid manifest but missing components
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = {
                'components': {
                    'database': {'engine': 'sqlite3', 'file': 'db.sqlite3'},
                    'media': {'path': 'media', 'total_files': 10}
                },
                'checksums': {'database': '1234567890abcdef'}
            }
            
            # Write valid manifest
            manifest_path = os.path.join(temp_dir, 'manifest.json')
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f)
            
            # Create empty database directory (but don't add the required file)
            os.makedirs(os.path.join(temp_dir, 'database'), exist_ok=True)
            
            # Create restore command and test restoration with missing files
            restore_command = RestoreCommand()
            restore_command.stdout = sys.stdout
            restore_command.verbosity = 2
            restore_command.database = 'default'
            restore_command.skip_media = False
            restore_command.skip_database = False
            
            # Should raise an exception about missing file
            with self.assertRaises(Exception) as context:
                with mock.patch('tasks.management.commands.restore.Command._validate_backup'):
                    with mock.patch('tasks.management.commands.restore.Command._extract_backup') as mock_extract:
                        mock_extract.return_value = temp_dir
                        
                        # Call _restore_database directly to test the file not found error
                        restore_command._restore_database(temp_dir, manifest)
            
            # Check that the error contains information about the missing file
            self.assertIn('not found', str(context.exception))
    
    def test_invalid_checksum(self):
        """Test handling of invalid checksums during backup validation."""
        # Create a temporary directory with a valid manifest but incorrect checksum
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create database file
            db_dir = os.path.join(temp_dir, 'database')
            os.makedirs(db_dir, exist_ok=True)
            db_file = os.path.join(db_dir, 'db.sqlite3')
            with open(db_file, 'w') as f:
                f.write("This is a test database file")
            
            # Create manifest with incorrect checksum
            manifest = {
                'components': {
                    'database': {'engine': 'sqlite3', 'file': 'db.sqlite3'}
                },
                'checksums': {'database': 'incorrectchecksum123456789'}
            }
            
            manifest_path = os.path.join(temp_dir, 'manifest.json')
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f)
            
            # Create restore command and test validation
            restore_command = RestoreCommand()
            restore_command.stdout = sys.stdout
            restore_command.verbosity = 1
            
            # Should raise an exception about checksum mismatch
            with self.assertRaises(Exception) as context:
                # Mock _calculate_checksum to return a known value
                with mock.patch('tasks.management.commands.restore.Command._calculate_checksum') as mock_checksum:
                    mock_checksum.return_value = "correctchecksum123456789"  # Different from manifest
                    
                    # Call _validate_backup directly
                    restore_command._validate_backup(temp_dir)
            
            # Check that the error contains information about the checksum mismatch
            self.assertIn('checksum mismatch', str(context.exception).lower())
    
    def test_concurrent_access(self):
        """Test handling of concurrent access to database during restore."""
        # Mock connections.close to raise an exception (simulating that connection couldn't be closed)
        with mock.patch('django.db.connections.close') as mock_close:
            mock_close.side_effect = Exception("Database is locked by another process")
            
            # Create a simple manifest for SQLite
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create database directory and file
                db_dir = os.path.join(temp_dir, 'database')
                os.makedirs(db_dir, exist_ok=True)
                db_file = os.path.join(db_dir, 'db.sqlite3')
                with open(db_file, 'w') as f:
                    f.write("Test database content")
                    
                # Create manifest
                manifest = {
                    'components': {
                        'database': {'engine': 'sqlite3', 'file': 'db.sqlite3'}
                    }
                }
                
                # Setup test database settings
                db_settings = {
                    'ENGINE': 'django.db.backends.sqlite3',
                    'NAME': 'test.db'
                }
                
                # Create restore command
                restore_command = RestoreCommand()
                restore_command.stdout = sys.stdout
                restore_command.verbosity = 1
                restore_command.database = 'default'
                
                # Should handle the exception
                with self.assertRaises(Exception) as context:
                    # Call _restore_sqlite_database directly
                    restore_command._restore_sqlite_database(temp_dir, manifest['components']['database'], db_settings)
                
                # Check that the error contains information about the database lock
                self.assertIn('Database is locked', str(context.exception))

if __name__ == '__main__':
    unittest.main()
