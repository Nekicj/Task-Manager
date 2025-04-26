from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.utils import timezone
from django.db import models
from .models import Task, Project, Category, CustomUser, TaskComment, TaskAttachment
from .choices import TaskStatus, TaskPriority


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        label=_("Email"),
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter your email'})
    )
    
    bio = forms.CharField(
        label=_("Bio"),
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tell us about yourself'})
    )
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'bio', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choose a username'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Confirm password'})


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )


class CategoryForm(forms.ModelForm):
    
    class Meta:
        model = Category
        fields = ['name', 'description', 'color', 'parent']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'color': forms.TextInput(attrs={'class': 'form-control color-picker', 'type': 'color'}),
            'parent': forms.Select(attrs={'class': 'form-control'})
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = Category.objects.all()
        self.fields['parent'].empty_label = "No parent category"
        self.fields['parent'].required = False


class ProjectForm(forms.ModelForm):
    
    class Meta:
        model = Project
        fields = ['title', 'description', 'members', 'start_date', 'end_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Project title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'members': forms.SelectMultiple(attrs={'class': 'form-control select2'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['members'].queryset = CustomUser.objects.all()
        
        if not self.instance.pk and not self.initial.get('start_date'):
            self.initial['start_date'] = timezone.now().date()
    
    def save(self, commit=True):
        """Override save to automatically set the owner to the current user."""
        instance = super().save(commit=False)
        if self.user and not instance.pk:
            instance.owner = self.user
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance


class TaskForm(forms.ModelForm):
    
    class Meta:
        model = Task
        fields = [
            'title', 'description', 'status', 'priority', 
            'project', 'category', 'assigned_to', 
            'deadline', 'estimated_hours'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'status': forms.Select(attrs={'class': 'form-control status-select'}),
            'priority': forms.Select(attrs={'class': 'form-control priority-select'}),
            'project': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'deadline': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'estimated_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25'})
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['assigned_to'].queryset = CustomUser.objects.all()
        self.fields['assigned_to'].empty_label = "Not assigned"
        self.fields['assigned_to'].required = False
        
        self.fields['category'].queryset = Category.objects.all()
        self.fields['category'].empty_label = "No category"
        self.fields['category'].required = False
        
        if self.user:
            user_projects = Project.objects.filter(
                models.Q(owner=self.user) | models.Q(members=self.user)
            ).distinct()
            self.fields['project'].queryset = user_projects
        
        if self.instance.deadline:
            self.initial['deadline'] = self.instance.deadline.strftime('%Y-%m-%dT%H:%M')
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.user and not instance.pk: 
            instance.created_by = self.user
        
        if commit:
            instance.save()
        
        return instance


class TaskCommentForm(forms.ModelForm):
    
    class Meta:
        model = TaskComment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Add a comment...'
            })
        }


class TaskAttachmentForm(forms.ModelForm):
    
    class Meta:
        model = TaskAttachment
        fields = ['file', 'name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Attachment name'}),
            'file': forms.FileInput(attrs={'class': 'form-control-file'})
        }
    
    def clean_file(self):
        """
        Validate the uploaded file using utils.validate_file function.
        """
        file = self.cleaned_data.get('file')
        if file:
            try:
                # Apply comprehensive file validation from utils
                from .utils import validate_file
                validate_file(file)
            except ValidationError as e:
                # Raise validation error to display in the form
                raise forms.ValidationError(str(e))
        return file


class TaskFilterForm(forms.Form):
    status = forms.MultipleChoiceField(
        choices=TaskStatus.CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'filter-checkbox'})
    )
    
    priority = forms.MultipleChoiceField(
        choices=TaskPriority.CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'filter-checkbox'})
    )
    
    category = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'filter-checkbox'})
    )
    
    assigned_to = forms.ModelChoiceField(
        queryset=CustomUser.objects.all(),
        required=False,
        empty_label="Anyone",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    deadline_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    deadline_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search tasks...',
            'data-debounce': 'true'
        })
    )

