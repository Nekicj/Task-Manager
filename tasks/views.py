from django.views.generic import (
    TemplateView, ListView, DetailView, 
    CreateView, UpdateView, DeleteView, FormView,
    View
)
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import login
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from django.db.models import Q, Count, Case, When, IntegerField
from django.urls import reverse_lazy, reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db import transaction
import json
import logging
from datetime import timedelta

from .models import Task, Project, Category, CustomUser, TaskComment, TaskAttachment
from .forms import (
    TaskForm, ProjectForm, CategoryForm, CustomUserCreationForm,
    CustomAuthenticationForm, TaskCommentForm, TaskAttachmentForm, TaskFilterForm
)
from .choices import TaskStatus, TaskPriority
from .utils import custom_ratelimit, check_task_permission, cached_view_data

# Configure loggers
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OwnershipRequiredMixin(UserPassesTestMixin):
    """
    Mixin to ensure that a user can only access/modify objects they own or have permission for.
    
    Extends Django's UserPassesTestMixin to check appropriate ownership or membership
    relationships for different object types.
    """
    
    def test_func(self):
        """
        Test if the user has permission to access the object.
        
        For projects: check if user is owner or member
        For tasks: check ownership, creation, assignment, or project membership
        For other objects: check if user field matches current user
        """
        obj = self.get_object()
        
        if isinstance(obj, Project):
            return (obj.owner == self.request.user or 
                    obj.members.filter(id=self.request.user.id).exists())
        
        elif isinstance(obj, Task):
            return (obj.project.owner == self.request.user or
                    obj.created_by == self.request.user or
                    (obj.assigned_to and obj.assigned_to == self.request.user) or
                    obj.project.members.filter(id=self.request.user.id).exists())
        
        return obj.user == self.request.user


class TaskManagerContextMixin:
    """Mixin to add common context data to views with performance optimizations."""
    
    @cached_view_data(timeout=300)  # Cache for 5 minutes
    def get_user_projects(self, user_id):
        """Get user's projects with optimized query and caching."""
        return list(Project.objects.filter(
            Q(owner_id=user_id) | Q(members=user_id)
        ).select_related('owner').prefetch_related('members').distinct())
    
    @cached_view_data(timeout=60)  # Cache for 1 minute
    def get_due_today_count(self, user_id):
        """Get count of tasks due today with caching."""
        today = timezone.now().date()
        return Task.objects.filter(
            Q(assigned_to_id=user_id) | Q(created_by_id=user_id),
            deadline__date=today,
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).count()
    
    @cached_view_data(timeout=60)  # Cache for 1 minute
    def get_overdue_tasks_count(self, user_id):
        """Get count of overdue tasks with caching."""
        return Task.objects.filter(
            Q(assigned_to_id=user_id) | Q(created_by_id=user_id),
            deadline__lt=timezone.now(),
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).count()
    
    @cached_view_data(timeout=120)  # Cache for 2 minutes
    def get_status_counts(self, user_id):
        """Get task status distribution with caching."""
        status_counts = Task.objects.filter(
            Q(assigned_to_id=user_id) | Q(created_by_id=user_id)
        ).values('status').annotate(count=Count('id'))
        
        return {item['status']: item['count'] for item in status_counts}
    
    @cached_view_data(timeout=300)  # Cache for 5 minutes
    def get_recent_activities(self, user_id):
        """Get recent activities for dashboard with optimized query."""
        # Get user's most recent updated tasks
        recent_tasks = Task.objects.filter(
            Q(assigned_to_id=user_id) | Q(created_by_id=user_id)
        ).select_related(
            'project', 'category', 'assigned_to', 'created_by'
        ).order_by('-updated_at')[:5]
        
        # Get recent comments on user's tasks
        user_task_ids = Task.objects.filter(
            Q(assigned_to_id=user_id) | Q(created_by_id=user_id)
        ).values_list('id', flat=True)
        
        recent_comments = TaskComment.objects.filter(
            task_id__in=user_task_ids
        ).select_related(
            'user', 'task'
        ).order_by('-created_at')[:5]
        
        return {
            'recent_tasks': list(recent_tasks),
            'recent_comments': list(recent_comments),
        }
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.is_authenticated:
            user_id = self.request.user.id
            
            # Use cached methods for expensive computations
            context['user_projects'] = self.get_user_projects(user_id)
            context['due_today'] = self.get_due_today_count(user_id)
            context['overdue_tasks'] = self.get_overdue_tasks_count(user_id)
            context['status_counts'] = self.get_status_counts(user_id)
            
            # Add more context data if this is the dashboard view
            if getattr(self, 'template_name', '') == 'tasks/dashboard.html':
                activities = self.get_recent_activities(user_id)
                context.update({
                    'recent_tasks': activities['recent_tasks'],
                    'recent_comments': activities['recent_comments'],
                })
        
        return context


class CustomLoginView(LoginView):
    form_class = CustomAuthenticationForm
    template_name = 'tasks/auth/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return reverse_lazy('tasks:dashboard')
    
    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().username}!")
        return super().form_valid(form)


class RegisterView(FormView):
    template_name = 'tasks/auth/register.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('tasks:dashboard')
    
    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Account created successfully! Welcome to Task Manager.")
        return super().form_valid(form)
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('tasks:dashboard')
        return super().get(request, *args, **kwargs)


class CustomLogoutView(LogoutView):
    next_page = 'tasks:login'
    
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        messages.success(request, "You've been logged out successfully.")
        return response


class DashboardView(LoginRequiredMixin, TaskManagerContextMixin, TemplateView):
    template_name = 'tasks/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = self.request.user
        today = timezone.now().date()
        
        context['recent_projects'] = Project.objects.filter(
            Q(owner=user) | Q(members=user)
        ).order_by('-updated_at')[:5]
        
        soon = today + timedelta(days=3)
        context['upcoming_tasks'] = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user),
            deadline__date__range=[today, soon],
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).order_by('deadline')[:10]
        
        context['recent_tasks'] = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user) | Q(project__owner=user)
        ).order_by('-updated_at')[:10]
        
        context['priority_tasks'] = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user),
            priority__in=[TaskPriority.HIGH, TaskPriority.URGENT],
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).order_by('-priority', 'deadline')[:5]
        
        tasks_by_status = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user)
        ).values('status').annotate(count=Count('id'))
        
        context['status_data'] = {
            'labels': [dict(TaskStatus.CHOICES)[status['status']] for status in tasks_by_status],
            'data': [status['count'] for status in tasks_by_status],
        }
        
        tasks_by_priority = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user),
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).values('priority').annotate(count=Count('id'))
        
        context['priority_data'] = {
            'labels': [dict(TaskPriority.CHOICES)[priority['priority']] for priority in tasks_by_priority],
            'data': [priority['count'] for priority in tasks_by_priority],
        }
        
        return context


class ProjectListView(LoginRequiredMixin, TaskManagerContextMixin, ListView):
    model = Project
    template_name = 'tasks/project/project_list.html'
    context_object_name = 'projects'
    paginate_by = 10
    
    def get_queryset(self):
        return Project.objects.filter(
            Q(owner=self.request.user) | Q(members=self.request.user)
        ).distinct().order_by('-created_at')


class ProjectDetailView(LoginRequiredMixin, OwnershipRequiredMixin, TaskManagerContextMixin, DetailView):
    model = Project
    template_name = 'tasks/project/project_detail.html'
    context_object_name = 'project'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.get_object()
        
        tasks = project.tasks.all()
        
        context['todo_tasks'] = tasks.filter(status=TaskStatus.TODO)
        context['in_progress_tasks'] = tasks.filter(status=TaskStatus.IN_PROGRESS)
        context['review_tasks'] = tasks.filter(status=TaskStatus.REVIEW)
        context['completed_tasks'] = tasks.filter(status=TaskStatus.COMPLETED)
        
        members = project.members.all()
        member_stats = []
        
        for member in members:
            member_tasks = tasks.filter(assigned_to=member)
            member_stats.append({
                'user': member,
                'task_count': member_tasks.count(),
                'completed': member_tasks.filter(status=TaskStatus.COMPLETED).count()
            })
        
        context['member_stats'] = member_stats
        
        return context


class ProjectCreateView(LoginRequiredMixin, TaskManagerContextMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'tasks/project/project_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        messages.success(self.request, f"Project '{self.object.title}' created successfully!")
        return reverse_lazy('tasks:project_detail', kwargs={'pk': self.object.pk})


class ProjectUpdateView(LoginRequiredMixin, OwnershipRequiredMixin, TaskManagerContextMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'tasks/project/project_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_success_url(self):
        messages.success(self.request, f"Project '{self.object.title}' updated successfully!")
        return reverse_lazy('tasks:project_detail', kwargs={'pk': self.object.pk})


class ProjectDeleteView(LoginRequiredMixin, OwnershipRequiredMixin, TaskManagerContextMixin, DeleteView):
    model = Project
    template_name = 'tasks/project/project_confirm_delete.html'
    success_url = reverse_lazy('tasks:project_list')
    
    def delete(self, request, *args, **kwargs):
        project = self.get_object()
        messages.success(request, f"Project '{project.title}' deleted successfully!")
        return super().delete(request, *args, **kwargs)


class TaskListView(LoginRequiredMixin, TaskManagerContextMixin, ListView):
    model = Task
    template_name = 'tasks/task/task_list.html'
    context_object_name = 'tasks'
    paginate_by = 15
    
    def get_queryset(self):
        user = self.request.user
        
        queryset = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user) | 
            Q(project__owner=user) | Q(project__members=user)
        ).distinct()
        
        form = TaskFilterForm(self.request.GET)
        if form.is_valid():
            status_filters = form.cleaned_data.get('status')
            if status_filters:
                queryset = queryset.filter(status__in=status_filters)
            
            priority_filters = form.cleaned_data.get('priority')
            if priority_filters:
                queryset = queryset.filter(priority__in=priority_filters)
            
            categories = form.cleaned_data.get('category')
            if categories:
                queryset = queryset.filter(category__in=categories)
            
            assigned_to = form.cleaned_data.get('assigned_to')
            if assigned_to:
                queryset = queryset.filter(assigned_to=assigned_to)
            
            deadline_from = form.cleaned_data.get('deadline_from')
            deadline_to = form.cleaned_data.get('deadline_to')
            
            if deadline_from:
                queryset = queryset.filter(deadline__date__gte=deadline_from)
            if deadline_to:
                queryset = queryset.filter(deadline__date__lte=deadline_to)
            
            search_query = form.cleaned_data.get('search')
            if search_query:
                queryset = queryset.filter(
                    Q(title__icontains=search_query) |
                    Q(description__icontains=search_query) |
                    Q(project__title__icontains=search_query)
                )
        
        return queryset.order_by(
            Case(
                When(priority=TaskPriority.URGENT, then=0),
                When(priority=TaskPriority.HIGH, then=1),
                When(priority=TaskPriority.MEDIUM, then=2),
                When(priority=TaskPriority.LOW, then=3),
                default=4,
                output_field=IntegerField(),
            ),
            'deadline',
            '-created_at'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = TaskFilterForm(self.request.GET)
        
        user = self.request.user
        today = timezone.now().date()
        
        context['my_tasks_count'] = Task.objects.filter(assigned_to=user).count()
        context['created_tasks_count'] = Task.objects.filter(created_by=user).count()
        context['due_today_count'] = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user),
            deadline__date=today,
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).count()
        context['overdue_count'] = Task.objects.filter(
            Q(assigned_to=user) | Q(created_by=user),
            deadline__lt=timezone.now(),
            status__in=[TaskStatus.TODO, TaskStatus.IN_PROGRESS]
        ).count()
        
        return context


class TaskDetailView(LoginRequiredMixin, OwnershipRequiredMixin, TaskManagerContextMixin, DetailView):
    model = Task
    template_name = 'tasks/task/task_detail.html'
    context_object_name = 'task'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.get_object()
        
        context['comment_form'] = TaskCommentForm()
        context['attachment_form'] = TaskAttachmentForm()
        
        context['comments'] = task.comments.all().order_by('-created_at')
        context['attachments'] = task.attachments.all().order_by('-uploaded_at')
        
        if task.category:
            context['related_tasks'] = Task.objects.filter(
                Q(project=task.project) | Q(category=task.category)
            ).exclude(id=task.id)[:5]
        else:
            context['related_tasks'] = Task.objects.filter(
                project=task.project
            ).exclude(id=task.id)[:5]
        
        return context


class TaskCreateView(LoginRequiredMixin, TaskManagerContextMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task/task_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_initial(self):
        """Pre-populate the form if project is specified in query string."""
        initial = super().get_initial()
        project_id = self.request.GET.get('project')
        if project_id:
            try:
                initial['project'] = Project.objects.get(pk=project_id)
            except (Project.DoesNotExist, ValueError):
                pass
        return initial
    
    def get_success_url(self):
        messages.success(self.request, f"Task '{self.object.title}' created successfully!")
        return reverse_lazy('tasks:task_detail', kwargs={'pk': self.object.pk})


class TaskUpdateView(LoginRequiredMixin, OwnershipRequiredMixin, TaskManagerContextMixin, UpdateView):
    model = Task
    form_class = TaskForm
    template_name = 'tasks/task/task_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
        
    def get_success_url(self):
        messages.success(self.request, f"Task '{self.object.title}' updated successfully!")
        return reverse_lazy('tasks:task_detail', kwargs={'pk': self.object.pk})


class TaskDeleteView(LoginRequiredMixin, OwnershipRequiredMixin, TaskManagerContextMixin, DeleteView):
    model = Task
    template_name = 'tasks/task/task_confirm_delete.html'
    
    def get_success_url(self):
        messages.success(self.request, f"Task '{self.object.title}' deleted successfully!")
        return reverse_lazy('tasks:task_list')


@method_decorator(require_POST, name='dispatch')
class TaskCommentCreateView(LoginRequiredMixin, FormView):
    form_class = TaskCommentForm
    
    def form_valid(self, form):
        task_id = self.kwargs.get('task_id')
        task = get_object_or_404(Task, pk=task_id)
        
        user = self.request.user
        # Use the centralized permission check from utils
        from .utils import check_task_permission
        if not check_task_permission(user, task):
            # Log unauthorized access attempt
            import logging
            logger = logging.getLogger('security')
            logger.warning(f"Unauthorized comment attempt by {user.username} on task {task.id}")
            
            return JsonResponse({
                'status': 'error',
                'message': 'You do not have permission to comment on this task.'
            }, status=403)
        comment = form.save(commit=False)
        comment.task = task
        comment.user = user
        comment.save()
        
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'comment_id': comment.id,
                'user': user.username,
                'text': comment.text,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
                'message': 'Comment added successfully!'
            })
        
        messages.success(self.request, "Comment added successfully!")
        return redirect('tasks:task_detail', pk=task_id)
    
    def form_invalid(self, form):
        task_id = self.kwargs.get('task_id')
        
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # Log form validation errors
            import logging
            logger = logging.getLogger('error')
            logger.info(f"Comment form validation error: {form.errors}")
            
            return JsonResponse({
                'status': 'error',
                'errors': form.errors,
                'message': 'There was an error adding your comment.'
            }, status=400)
        messages.error(self.request, "There was an error adding your comment.")
        return redirect('tasks:task_detail', pk=task_id)


@method_decorator(require_POST, name='dispatch')
class TaskAttachmentCreateView(LoginRequiredMixin, FormView):
    form_class = TaskAttachmentForm
    
    def form_valid(self, form):
        task_id = self.kwargs.get('task_id')
        task = get_object_or_404(Task, pk=task_id)
        
        user = self.request.user
        if not (task.project.owner == user or 
                task.created_by == user or 
                task.assigned_to == user or
                task.project.members.filter(id=user.id).exists()):
            messages.error(self.request, "You do not have permission to add attachments to this task.")
            return redirect('tasks:task_detail', pk=task_id)
        
        attachment = form.save(commit=False)
        attachment.task = task
        attachment.uploaded_by = user
        attachment.save()
        
        messages.success(self.request, "Attachment added successfully!")
        return redirect('tasks:task_detail', pk=task_id)
    
    def form_invalid(self, form):
        task_id = self.kwargs.get('task_id')
        messages.error(self.request, "There was an error adding your attachment.")
        return redirect('tasks:task_detail', pk=task_id)


@method_decorator(csrf_exempt, name='dispatch')
class TaskStatusUpdateView(LoginRequiredMixin, View):
    
    def post(self, request, pk):
        if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)
        
        try:
            task = Task.objects.get(pk=pk)
        except Task.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Task not found'}, status=404)
        
        user = request.user
        if not (task.project.owner == user or 
                task.created_by == user or 
                task.assigned_to == user or
                task.project.members.filter(id=user.id).exists()):
            return JsonResponse({
                'status': 'error',
                'message': 'You do not have permission to update this task.'
            }, status=403)
        
        try:
            data = json.loads(request.body)
            new_status = data.get('status')
            
            if new_status not in dict(TaskStatus.CHOICES):
                return JsonResponse({'status': 'error', 'message': 'Invalid status'}, status=400)
            
            old_status = task.status
            task.status = new_status
            
            if new_status == TaskStatus.COMPLETED and old_status != TaskStatus.COMPLETED:
                task.completed_at = timezone.now()
            elif new_status != TaskStatus.COMPLETED and old_status == TaskStatus.COMPLETED:
                task.completed_at = None
                
            task.save()

            status_display = dict(TaskStatus.CHOICES)[new_status]
            
            return JsonResponse({
                'status': 'success',
                'task_id': task.id,
                'new_status': new_status,
                'status_display': status_display,
                'message': f"Task status updated to {status_display}"
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class CategoryListView(LoginRequiredMixin, TaskManagerContextMixin, ListView):
    model = Category
    template_name = 'tasks/category/category_list.html'
    context_object_name = 'categories'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        categories = self.get_queryset()
        
        root_categories = categories.filter(parent=None)
        
        hierarchy = []
        for category in root_categories:
            children = categories.filter(parent=category)
            hierarchy.append({
                'category': category,
                'children': children,
                'task_count': category.task_count
            })
        
        context['category_hierarchy'] = hierarchy
        return context


class CategoryCreateView(LoginRequiredMixin, TaskManagerContextMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'tasks/category/category_form.html'
    success_url = reverse_lazy('tasks:category_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Category '{form.instance.name}' created successfully!")
        return super().form_valid(form)


class CategoryUpdateView(LoginRequiredMixin, TaskManagerContextMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'tasks/category/category_form.html'
    success_url = reverse_lazy('tasks:category_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Category '{form.instance.name}' updated successfully!")
        return super().form_valid(form)


class CategoryDeleteView(LoginRequiredMixin, TaskManagerContextMixin, DeleteView):
    model = Category
    template_name = 'tasks/category/category_confirm_delete.html'
    success_url = reverse_lazy('tasks:category_list')
    
    
