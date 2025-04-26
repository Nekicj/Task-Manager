import os
import json
import tempfile
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import path
from django.shortcuts import render
from django.contrib import messages
from django.core.management import call_command
from django.conf import settings
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

from .models import (
    CustomUser, 
    Category, 
    Project, 
    Task, 
    TaskComment, 
    TaskAttachment
)


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'display_theme')
    list_filter = ('is_staff', 'is_active', 'theme_preference')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'bio', 'profile_picture')}),
        (_('Preferences'), {'fields': ('theme_preference',)}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    def display_theme(self, obj):
        if obj.theme_preference == 'dark':
            return format_html('<span style="color: white; background-color: #333; padding: 2px 6px; border-radius: 3px;">Dark</span>')
        return format_html('<span style="color: #333; background-color: #f8f9fa; padding: 2px 6px; border-radius: 3px;">Light</span>')
    
    display_theme.short_description = _('Theme')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'color_display', 'task_count', 'created_at')
    list_filter = ('parent',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    def color_display(self, obj):
        """Display the category color as a colored box."""
        return format_html(
            '<span style="background-color: {}; width: 20px; height: 20px; display: inline-block; border-radius: 3px;"></span> {}',
            obj.color, obj.color
        )
    
    color_display.short_description = _('Color')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'start_date', 'end_date', 'completion_percentage', 'is_archived', 'created_at')
    list_filter = ('is_archived', 'start_date')
    search_fields = ('title', 'description', 'owner__username')
    readonly_fields = ('created_at', 'updated_at', 'completion_percentage')
    filter_horizontal = ('members',)
    
    fieldsets = (
        (None, {'fields': ('title', 'description')}),
        (_('Relationships'), {'fields': ('owner', 'members')}),
        (_('Dates'), {'fields': ('start_date', 'end_date')}),
        (_('Status'), {'fields': ('is_archived',)}),
        (_('System information'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def completion_percentage(self, obj):
        percentage = obj.completion_percentage
        color = '#28a745'  # Green for completed
        if percentage < 25:
            color = '#dc3545'  # Red for early stages
        elif percentage < 75:
            color = '#ffc107'  # Yellow for in progress
        
        return format_html(
            '''
            <div style="width: 100px; background-color: #e9ecef; height: 20px; border-radius: 3px;">
                <div style="width: {}%; background-color: {}; height: 100%; border-radius: 3px; text-align: center; color: white;">
                    {}%
                </div>
            </div>
            ''',
            percentage, color, percentage
        )
    
    completion_percentage.short_description = _('Completion')


class TaskCommentInline(admin.TabularInline):
    model = TaskComment
    extra = 0
    readonly_fields = ('created_at',)


class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 0
    readonly_fields = ('uploaded_at',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status_display', 'priority_display', 
                   'assigned_to', 'deadline', 'is_overdue', 'created_at')
    list_filter = ('status', 'priority', 'project', 'category')
    search_fields = ('title', 'description', 'assigned_to__username', 'created_by__username')
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    inlines = [TaskCommentInline, TaskAttachmentInline]
    
    fieldsets = (
        (None, {'fields': ('title', 'description')}),
        (_('Status & Priority'), {'fields': ('status', 'priority')}),
        (_('Relationships'), {'fields': ('project', 'category', 'assigned_to', 'created_by')}),
        (_('Dates'), {'fields': ('deadline', 'completed_at')}),
        (_('Progress'), {'fields': ('estimated_hours', 'actual_hours')}),
        (_('System information'), {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    
    def status_display(self, obj):
        """Display the task status with a color-coded badge."""
        status_colors = {
            'todo': '#6c757d',        # Gray
            'in_progress': '#007bff',  # Blue
            'review': '#fd7e14',      # Orange
            'completed': '#28a745',   # Green
            'archived': '#343a40',    # Dark Gray
        }
        
        color = status_colors.get(obj.status, '#6c757d') 
        status_text = dict(obj._meta.get_field('status').choices)[obj.status]
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px;">{}</span>',
            color, status_text
        )
    
    status_display.short_description = _('Status')
    
    def priority_display(self, obj):
        priority_colors = {
            'low': '#28a745',       # Green
            'medium': '#ffc107',    # Yellow
            'high': '#fd7e14',      # Orange
            'urgent': '#dc3545',    # Red
        }
        
        color = priority_colors.get(obj.priority, '#6c757d') 
        priority_text = dict(obj._meta.get_field('priority').choices)[obj.priority]
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, priority_text
        )
    
    priority_display.short_description = _('Priority')
    
    def is_overdue(self, obj):
        """Display if a task is overdue as a boolean icon."""
        if obj.is_overdue:
            return format_html('<span style="color: #dc3545;">&#10008;</span>')  # Red X
        if obj.deadline:
            return format_html('<span style="color: #28a745;">&#10004;</span>')  # Green check
        return '-'
    
    is_overdue.short_description = _('Overdue')
    is_overdue.boolean = True


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'text_preview', 'created_at')
    list_filter = ('task__status', 'created_at')
    search_fields = ('text', 'task__title', 'user__username')
    readonly_fields = ('created_at',)
    
    def text_preview(self, obj):
        """Display a preview of the comment text."""
        max_length = 50
        if len(obj.text) > max_length:
            return f"{obj.text[:max_length]}..."
        return obj.text
    
    text_preview.short_description = _('Comment')


@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'task', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at', 'task__status')
    search_fields = ('name', 'task__title', 'uploaded_by__username')
    readonly_fields = ('uploaded_at',)


# Admin site customization for backup/restore
class BackupRestoreAdminSite(admin.AdminSite):
    """Custom admin site with backup/restore functionality."""
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('backup/', self.admin_view(self.backup_view), name='backup'),
            path('restore/', self.admin_view(self.restore_view), name='restore'),
            path('perform-backup/', self.admin_view(self.perform_backup_view), name='perform_backup'),
            path('perform-restore/', self.admin_view(self.perform_restore_view), name='perform_restore'),
        ]
        return custom_urls + urls
    
    @method_decorator(staff_member_required)
    @method_decorator(csrf_protect)
    def backup_view(self, request):
        """View for backup configuration."""
        # Get list of existing backups
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        backups = []
        if os.path.exists(backup_dir):
            for file in os.listdir(backup_dir):
                if file.endswith('.tar.gz') or file.endswith('.tar') or file.endswith('.gpg'):
                    file_path = os.path.join(backup_dir, file)
                    stats = os.stat(file_path)
                    backups.append({
                        'name': file,
                        'path': file_path,
                        'size': self._format_size(stats.st_size),
                        'modified': timezone.datetime.fromtimestamp(stats.st_mtime),
                    })
        
        # Sort backups by modification time (newest first)
        backups.sort(key=lambda x: x['modified'], reverse=True)
        
        context = {
            'title': 'Backup System',
            'backups': backups,
            'has_backups': len(backups) > 0,
            'backup_dir': backup_dir,
            'opts': {
                'app_label': 'admin',
                'verbose_name_plural': 'Backups',
            },
        }
        
        return render(request, 'admin/backup.html', context)
    
    @method_decorator(staff_member_required)
    @method_decorator(csrf_protect)
    def restore_view(self, request):
        """View for restore configuration."""
        # Get list of existing backups
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        backups = []
        if os.path.exists(backup_dir):
            for file in os.listdir(backup_dir):
                if file.endswith('.tar.gz') or file.endswith('.tar') or file.endswith('.gpg'):
                    file_path = os.path.join(backup_dir, file)
                    stats = os.stat(file_path)
                    backups.append({
                        'name': file,
                        'path': file_path,
                        'size': self._format_size(stats.st_size),
                        'modified': timezone.datetime.fromtimestamp(stats.st_mtime),
                    })
        
        # Sort backups by modification time (newest first)
        backups.sort(key=lambda x: x['modified'], reverse=True)
        
        context = {
            'title': 'Restore System',
            'backups': backups,
            'has_backups': len(backups) > 0,
            'opts': {
                'app_label': 'admin',
                'verbose_name_plural': 'Backups',
            },
        }
        
        return render(request, 'admin/restore.html', context)
    
    @method_decorator(staff_member_required)
    @method_decorator(csrf_protect)
    def perform_backup_view(self, request):
        """Perform backup with specified options."""
        if request.method != 'POST':
            return HttpResponseRedirect('../backup/')
        
        # Get options from form
        options = {
            'output_dir': os.path.join(settings.BASE_DIR, 'backups'),
            'filename': request.POST.get('filename') or f"backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
            'compress': 'compress' in request.POST,
            'compression_level': int(request.POST.get('compression_level', 6)),
            'skip_media': 'skip_media' in request.POST,
            'skip_database': 'skip_database' in request.POST,
            'include_fixtures': 'include_fixtures' in request.POST,
            'encrypt': 'encrypt' in request.POST,
            'encrypt_key': request.POST.get('encrypt_key', ''),
            'verbosity': 1,
        }
        
        try:
            # Call backup command
            from io import StringIO
            output = StringIO()
            
            # Run the backup command
            backup_path = call_command(
                'backup',
                **options,
                stdout=output
            )
            
            # Get command output
            command_output = output.getvalue()
            
            # Check result
            if os.path.exists(backup_path):
                result_msg = f"Backup created successfully: {os.path.basename(backup_path)}"
                messages.success(request, result_msg)
            else:
                messages.error(request, "Backup failed: File not created")
            
            # Log some info from the output
            for line in command_output.splitlines():
                if 'error' in line.lower():
                    messages.error(request, line)
                elif 'warning' in line.lower():
                    messages.warning(request, line)
                elif line.strip():
                    messages.info(request, line)
        
        except Exception as e:
            messages.error(request, f"Backup failed: {str(e)}")
        
        return HttpResponseRedirect('../backup/')
    
    @method_decorator(staff_member_required)
    @method_decorator(csrf_protect)
    def perform_restore_view(self, request):
        """Perform restore with specified options."""
        if request.method != 'POST':
            return HttpResponseRedirect('../restore/')
        
        # Get options from form
        backup_file = request.POST.get('backup_file')
        
        if not backup_file:
            messages.error(request, "No backup file selected")
            return HttpResponseRedirect('../restore/')
        
        options = {
            'skip_media': 'skip_media' in request.POST,
            'skip_database': 'skip_database' in request.POST,
            'skip_fixtures': 'skip_fixtures' in request.POST,
            'media_strategy': request.POST.get('media_strategy', 'replace'),
            'force': True,  # Skip confirmation in automated restore
            'verbosity': 1,
        }
        
        # Add passphrase if provided
        if 'passphrase' in request.POST and request.POST['passphrase']:
            options['passphrase'] = request.POST['passphrase']
        
        try:
            # Call restore command
            from io import StringIO
            output = StringIO()
            
            # Run the restore command
            call_command(
                'restore',
                backup_file,
                **options,
                stdout=output
            )
            
            # Get command output
            command_output = output.getvalue()
            
            # Log the success message
            messages.success(request, "Restoration completed successfully!")
            
            # Log some info from the output
            for line in command_output.splitlines():
                if 'error' in line.lower():
                    messages.error(request, line)
                elif 'warning' in line.lower():
                    messages.warning(request, line)
                elif line.strip() and not line.startswith(' '):
                    messages.info(request, line)
        
        except Exception as e:
            messages.error(request, f"Restoration failed: {str(e)}")
        
        return HttpResponseRedirect('../restore/')
    
    def _format_size(self, size_bytes):
        """Format file size in a human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

# Custom admin site
admin_site = BackupRestoreAdminSite(name='task_manager_admin')

# Register the same models with our custom admin site
admin_site.register(CustomUser, CustomUserAdmin)
admin_site.register(Category, CategoryAdmin)
admin_site.register(Project, ProjectAdmin)
admin_site.register(Task, TaskAdmin)
admin_site.register(TaskComment, TaskCommentAdmin)
admin_site.register(TaskAttachment, TaskAttachmentAdmin)

# Add an admin action for backup
@admin.action(description="Create backup of selected data")
def create_backup(modeladmin, request, queryset):
    """Admin action to create a backup."""
    try:
        # For tasks, we might want to back up related data
        if modeladmin.model == Task:
            task_ids = list(queryset.values_list('id', flat=True))
            task_filter = f"--task-ids={','.join(map(str, task_ids))}"
            backup_path = call_command('backup', filename=f"task_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}")
        # For projects, back up everything related to the selected projects
        elif modeladmin.model == Project:
            project_ids = list(queryset.values_list('id', flat=True))
            project_filter = f"--project-ids={','.join(map(str, project_ids))}"
            backup_path = call_command('backup', filename=f"project_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}")
        # Otherwise do a full backup
        else:
            backup_path = call_command('backup', filename=f"full_backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}")
        
        messages.success(request, f"Backup created successfully: {os.path.basename(backup_path)}")
    except Exception as e:
        messages.error(request, f"Backup failed: {str(e)}")


# Add the action to relevant model admins
TaskAdmin.actions = [create_backup]
ProjectAdmin.actions = [create_backup]
