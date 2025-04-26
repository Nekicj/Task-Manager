from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .choices import TaskStatus, TaskPriority
from .utils import cached_property

class CustomUser(AbstractUser):
    bio = models.TextField(blank=True, null=True, help_text=_("User's bio or description"))
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    theme_preference = models.CharField(max_length=20, default='light', choices=[('light', 'Light'), ('dark', 'Dark')])
    
    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
    
    def __str__(self):
        return self.username
    
    def get_absolute_url(self):
        return reverse('user_profile', kwargs={'username': self.username})
    
    def get_active_projects_count(self):
        return self.projects.filter(is_archived=False).count()
    
    def get_tasks_due_today(self):
        today = timezone.now().date()
        return self.tasks.filter(deadline__date=today)


class Category(models.Model):
    name = models.CharField(max_length=100, db_index=True, help_text=_("Category name"))
    description = models.TextField(blank=True, null=True, help_text=_("Category description"))
    color = models.CharField(max_length=20, default='#3498db', help_text=_("Color for visual identification"))
    
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, 
                              related_name='children', help_text=_("Parent category if any"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['parent']),
        ]
    
    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.name}"
        return self.name
    
    def get_absolute_url(self):
        return reverse('category_detail', kwargs={'pk': self.pk})
    @cached_property(timeout=3600)  # Cache for 1 hour
    def get_all_children(self):
        """
        Get all child categories recursively, using an efficient query approach.
        This version uses a single query with a recursive CTE when using PostgreSQL,
        or falls back to a more efficient version of the recursive approach.
        """
        from django.db import connection
        
        # Check if using PostgreSQL to use recursive CTE
        if connection.vendor == 'postgresql':
            from django.db import connection
            
            # Use raw SQL for efficient recursive CTE
            with connection.cursor() as cursor:
                cursor.execute("""
                    WITH RECURSIVE category_tree AS (
                        SELECT id, parent_id FROM tasks_category WHERE id = %s
                        UNION ALL
                        SELECT c.id, c.parent_id FROM tasks_category c
                        JOIN category_tree ct ON ct.id = c.parent_id
                    )
                    SELECT id FROM category_tree WHERE id != %s
                """, [self.id, self.id])
                
                # Get all child IDs from the query result
                child_ids = [row[0] for row in cursor.fetchall()]
                
                # Return categories by ID
                if child_ids:
                    return list(Category.objects.filter(id__in=child_ids))
                return []
        else:
            # Optimized version for non-PostgreSQL databases
            # This approach reduces queries by using prefetch_related
            all_categories = Category.objects.prefetch_related('children')
            
            # Use a more efficient recursive approach with a set to track processed IDs
            def get_children_recursive(category_id, processed_ids=None):
                if processed_ids is None:
                    processed_ids = set()
                
                # Get direct children from the prefetched categories
                direct_children = [c for c in all_categories if c.parent_id == category_id and c.id not in processed_ids]
                
                result = []
                for child in direct_children:
                    processed_ids.add(child.id)
                    result.append(child)
                    # Get grandchildren recursively
                    grandchildren = get_children_recursive(child.id, processed_ids)
                    result.extend(grandchildren)
                
                return result
            
            return get_children_recursive(self.id)
        return children
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store initial parent_id for cache invalidation on parent change
        if self.pk:
            self._initial_parent_id = self.parent_id
    
    def clean(self):
        """Prevent circular dependencies in category hierarchy."""
        if self.parent:
            # Check if self is not being set as a parent of itself
            if self.parent.id == self.id:
                raise models.ValidationError(_("A category cannot be a parent of itself."))
            
            # Check if self is not being set as a parent of its ancestors
            parent = self.parent
            while parent:
                if parent.parent and parent.parent.id == self.id:
                    raise models.ValidationError(_("Circular reference detected in category hierarchy."))
                parent = parent.parent
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @property
    def task_count(self):
        return self.tasks.count()
class Project(models.Model):
    title = models.CharField(max_length=200, db_index=True, help_text=_("Project title"))
    description = models.TextField(blank=True, null=True, help_text=_("Project description"))
    
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='projects',
                             help_text=_("Project owner"))
    members = models.ManyToManyField(CustomUser, related_name='member_projects', blank=True,
                                   help_text=_("Project members"))
    
    start_date = models.DateField(default=timezone.now, help_text=_("Project start date"))
    end_date = models.DateField(null=True, blank=True, help_text=_("Expected completion date"))
    
    is_archived = models.BooleanField(default=False, db_index=True, help_text=_("Whether project is archived"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Project')
        verbose_name_plural = _('Projects')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner']),
            models.Index(fields=['start_date']),
            models.Index(fields=['end_date']),
            models.Index(fields=['is_archived']),
        ]
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('project_detail', kwargs={'pk': self.pk})
    
    @cached_property(timeout=1800)  # Cache for 30 minutes
    def task_count(self):
        """Get the count of tasks in this category with caching."""
        return self.tasks.count()
    
    @cached_property(timeout=1800)  # Cache for 30 minutes
    def all_tasks_count(self):
        """
        Get the count of all tasks in this category and its subcategories.
        Uses optimal query approach to minimize database hits.
        """
        # Get IDs of all children categories
        children = self.get_all_children()
        child_ids = [child.id for child in children]
        
        # Include the current category
        category_ids = [self.id] + child_ids
        
        # Count tasks in all categories with a single query
        return Task.objects.filter(category_id__in=category_ids).count()
    
    def invalidate_caches(self):
        """Invalidate all cached properties for this instance."""
        from .utils import invalidate_model_cache
        invalidate_model_cache(self)
        
        # Also invalidate parent's caches since they depend on children
        if self.parent:
            self.parent.invalidate_caches()
    @property
    def completed_task_count(self):
        return self.tasks.filter(status=TaskStatus.COMPLETED).count()
    
    @property
    def completion_percentage(self):
        if self.task_count == 0:
            return 0
        return int((self.completed_task_count / self.task_count) * 100)
    
    @property
    def is_overdue(self):
        if not self.end_date:
            return False

        return self.end_date < timezone.now().date() and self.completion_percentage < 100
    
    def clean(self):
        """Validate project dates."""
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise models.ValidationError({
                'end_date': _("End date cannot be before start date.")
            })
    
    def save(self, *args, **kwargs):
        """Save the model and invalidate relevant caches."""
        self.clean()
        
        # Check if this is an update to an existing record
        is_update = self.pk is not None
        
        # Save the model
        super().save(*args, **kwargs)
        
        # Invalidate caches
        self.invalidate_caches()
        
        # If parent changed, invalidate old parent's cache too
        if is_update and 'parent_id' in kwargs.get('update_fields', []) and self._initial_parent_id:
            try:
                old_parent = Category.objects.get(pk=self._initial_parent_id)
                old_parent.invalidate_caches()
            except (Category.DoesNotExist, AttributeError):
                pass
class Task(models.Model):
    title = models.CharField(max_length=200, db_index=True, help_text=_("Task title"))
    description = models.TextField(blank=True, null=True, help_text=_("Task description"))
    
    status = models.CharField(max_length=20, db_index=True, choices=TaskStatus.CHOICES, 
                             default=TaskStatus.TODO, help_text=_("Current status"))
    priority = models.CharField(max_length=20, db_index=True, choices=TaskPriority.CHOICES,
                              default=TaskPriority.MEDIUM, help_text=_("Task priority"))
    
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, 
                              related_name='tasks', help_text=_("Project this task belongs to"))
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='tasks', help_text=_("Task category"))
    assigned_to = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='tasks', help_text=_("User assigned to this task"))
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_tasks',
                                 help_text=_("User who created this task"))
    
    deadline = models.DateTimeField(null=True, blank=True, db_index=True, help_text=_("Task deadline"))
    
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                        help_text=_("Estimated hours needed"))
    actual_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                     help_text=_("Actual hours spent"))
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = _('Task')
        verbose_name_plural = _('Tasks')
        ordering = ['-priority', 'deadline']
        indexes = [
            models.Index(fields=['created_by']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['project', 'status']),
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['deadline', 'status']),
            models.Index(fields=['completed_at']),
        ]
    def __str__(self):
        return self.title
    
    def get_absolute_url(self):
        return reverse('task_detail', kwargs={'pk': self.pk})
    
    def mark_complete(self):
        self.status = TaskStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save()
    
    @property
    def is_overdue(self):
        if not self.deadline or self.status == TaskStatus.COMPLETED:
            return False
        return self.deadline < timezone.now()
    
    def clean(self):
        """Validate task data."""
        # Ensure project is specified
        if not self.project:
            raise models.ValidationError({
                'project': _("A task must be associated with a project.")
            })
    @property
    def time_remaining(self):
        if not self.deadline or self.status == TaskStatus.COMPLETED:
            return None
        return self.deadline - timezone.now()
    
    @property
    def progress_percentage(self):
        status_progress = {
            TaskStatus.TODO: 0,
            TaskStatus.IN_PROGRESS: 50,
            TaskStatus.REVIEW: 80,
            TaskStatus.COMPLETED: 100,
            TaskStatus.ARCHIVED: 100,
        }
        return status_progress.get(self.status, 0)
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['task']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.task.title}"


class TaskAttachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='task_attachments/')
    name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['task']),
            models.Index(fields=['uploaded_by']),
        ]
    
    def clean(self):
        """Validate the uploaded file."""
        if self.file:
            from .utils import validate_file
            try:
                validate_file(self.file)
            except Exception as e:
                from django.core.exceptions import ValidationError
                raise ValidationError(str(e))
                
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name
        
    def delete(self, *args, **kwargs):
        """Delete the file from storage when the model instance is deleted."""
        # Store the file path
        storage, path = self.file.storage, self.file.path
        
        # Delete the model instance
        super().delete(*args, **kwargs)
        
        # Delete the file after the model instance is deleted
        try:
            storage.delete(path)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error deleting file {path}: {e}")
