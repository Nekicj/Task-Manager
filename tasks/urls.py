from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

from . import views

app_name = 'tasks'

auth_patterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    
    # Password reset
    path('password_reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='tasks/auth/password_reset_form.html',
             email_template_name='tasks/auth/password_reset_email.html',
             subject_template_name='tasks/auth/password_reset_subject.txt'
         ), 
         name='password_reset'),
    path('password_reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='tasks/auth/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('reset/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='tasks/auth/password_reset_confirm.html'
         ), 
         name='password_reset_confirm'),
    path('reset/done/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='tasks/auth/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
    
    # Password change
    path('password_change/', 
         auth_views.PasswordChangeView.as_view(
             template_name='tasks/auth/password_change_form.html'
         ), 
         name='password_change'),
    path('password_change/done/', 
         auth_views.PasswordChangeDoneView.as_view(
             template_name='tasks/auth/password_change_done.html'
         ), 
         name='password_change_done'),
]

# Project URLs
project_patterns = [
    path('', views.ProjectListView.as_view(), name='project_list'),
    path('new/', views.ProjectCreateView.as_view(), name='project_create'),
    path('<int:pk>/', views.ProjectDetailView.as_view(), name='project_detail'),
    path('<int:pk>/edit/', views.ProjectUpdateView.as_view(), name='project_update'),
    path('<int:pk>/delete/', views.ProjectDeleteView.as_view(), name='project_delete'),
]

# Task URLs
task_patterns = [
    path('', views.TaskListView.as_view(), name='task_list'),
    path('new/', views.TaskCreateView.as_view(), name='task_create'),
    path('<int:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    path('<int:pk>/edit/', views.TaskUpdateView.as_view(), name='task_update'),
    path('<int:pk>/delete/', views.TaskDeleteView.as_view(), name='task_delete'),
    
    path('<int:pk>/update-status/', views.TaskStatusUpdateView.as_view(), name='task_update_status'),
    path('<int:task_id>/comment/', views.TaskCommentCreateView.as_view(), name='task_add_comment'),
    path('<int:task_id>/attachment/', views.TaskAttachmentCreateView.as_view(), name='task_add_attachment'),
]

# Category URLs
category_patterns = [
    path('', views.CategoryListView.as_view(), name='category_list'),
    path('new/', views.CategoryCreateView.as_view(), name='category_create'),
    path('<int:pk>/edit/', views.CategoryUpdateView.as_view(), name='category_update'),
    path('<int:pk>/delete/', views.CategoryDeleteView.as_view(), name='category_delete'),
]

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    
    path('auth/', include(auth_patterns)),
    
    path('projects/', include(project_patterns)),
    
    path('tasks/', include(task_patterns)),
    
    path('categories/', include(category_patterns)),
]

