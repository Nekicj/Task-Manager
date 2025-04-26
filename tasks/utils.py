import os
import mimetypes
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from functools import wraps
from django.http import HttpResponseForbidden

# File validation constants
MAX_FILE_SIZE_MB = 10  # Maximum file size in MB
ALLOWED_FILE_TYPES = {
    'image/jpeg': ['.jpg', '.jpeg'],
    'image/png': ['.png'],
    'image/gif': ['.gif'],
    'application/pdf': ['.pdf'],
    'application/msword': ['.doc'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'application/vnd.ms-excel': ['.xls'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'text/plain': ['.txt'],
    'application/zip': ['.zip'],
}

def validate_file_type(file):
    """
    Validate file type using mimetypes module and file extension.
    
    Returns tuple of (is_valid, error_message)
    """
    try:
        # Initialize mimetypes if not already done
        if not mimetypes.inited:
            mimetypes.init()
            
        # Get file extension and guess MIME type
        file_ext = os.path.splitext(file.name)[1].lower()
        guessed_mime_type = mimetypes.guess_type(file.name)[0]
        
        # If we couldn't guess the MIME type from extension, reject it
        if guessed_mime_type is None:
            return False, _("Unrecognized file type. Allowed types: {0}").format(
                ", ".join([ext for exts in ALLOWED_FILE_TYPES.values() for ext in exts])
            )
            
        # Check if the guessed MIME type is in our allowed types
        if guessed_mime_type not in ALLOWED_FILE_TYPES:
            return False, _("File type not allowed. Allowed types: {0}").format(
                ", ".join([ext for exts in ALLOWED_FILE_TYPES.values() for ext in exts])
            )
        
        # Check if the file extension matches the allowed extensions for this MIME type
        if file_ext not in ALLOWED_FILE_TYPES[guessed_mime_type]:
            return False, _("File extension does not match its content type.")
        
        return True, None
        
    except Exception as e:
        return False, _("Error validating file: {0}").format(str(e))

def validate_file_size(file):
    """
    Validate that the file size is under the maximum allowed size.
    
    Returns tuple of (is_valid, error_message)
    """
    # Convert MB to bytes
    max_size_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    
    if file.size > max_size_bytes:
        return False, _("File too large. Maximum size is {0} MB.").format(MAX_FILE_SIZE_MB)
    
    return True, None

def validate_file(file):
    """
    Comprehensive file validation.
    
    Raises ValidationError if the file is invalid.
    """
    # Check file size
    is_valid_size, size_error = validate_file_size(file)
    if not is_valid_size:
        raise ValidationError(size_error)
    
    # Check file type
    is_valid_type, type_error = validate_file_type(file)
    if not is_valid_type:
        raise ValidationError(type_error)

def custom_ratelimit(key_func, rate, method=None, block=True):
    """
    Custom rate limiting decorator that provides more detailed error responses.
    
    Args:
        key_func: Function that generates the cache key (e.g., 'ip', 'user')
        rate: Rate limit string (e.g., '5/m', '100/d')
        method: HTTP methods to apply rate limiting to (e.g., ['GET', 'POST'])
        block: Whether to block the request when rate limit is exceeded
    """
    from ratelimit.decorators import ratelimit
    from ratelimit.exceptions import Ratelimited
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            try:
                # Apply Django's ratelimit decorator
                ratelimited_func = ratelimit(key=key_func, rate=rate, method=method, block=block)(view_func)
                return ratelimited_func(*args, **kwargs)
            except Ratelimited:
                return HttpResponseForbidden(
                    _("Too many requests. Please try again later.")
                )
        return wrapped_view
    return decorator

# Permission check helper function
def check_task_permission(user, task):
    """Check if a user has permission to view/edit a task."""
    return (
        task.project.owner == user or
        task.created_by == user or
        (task.assigned_to and task.assigned_to == user) or
        task.project.members.filter(id=user.id).exists()
    )

# Cache utilities
from django.core.cache import cache
from django.conf import settings
from functools import wraps

def cached_property(timeout=None):
    """
    Decorator for caching expensive model property methods.
    Caches the result with a key based on the model's ID and method name.
    
    Example:
        @cached_property(timeout=300)
        def expensive_calculation(self):
            # complex calculation
            return result
    """
    def decorator(func):
        @property
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Use class name, method name and ID to create a unique cache key
            cache_key = f"{self.__class__.__name__}:{self.id}:{func.__name__}"
            result = cache.get(cache_key)
            
            if result is None:
                result = func(self, *args, **kwargs)
                # Use the default TTL if timeout is None
                cache_ttl = timeout if timeout is not None else getattr(settings, 'CACHE_TTL', 60 * 15)
                cache.set(cache_key, result, cache_ttl)
                
            return result
        return wrapper
    return decorator

def cached_view_data(timeout=None):
    """
    Decorator for caching expensive view methods.
    Caches based on user ID and optional additional keys.
    
    Example:
        @cached_view_data(timeout=300)
        def get_expensive_data(self, user_id, *extra_key_parts):
            # complex data processing
            return data
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Generate a cache key including all args for uniqueness
            parts = [func.__name__]
            
            # If we have a request with a user, use that as part of the key
            if hasattr(self, 'request') and hasattr(self.request, 'user') and self.request.user.is_authenticated:
                parts.append(f"user:{self.request.user.id}")
                
            # Add any other args as part of the key
            for arg in args:
                parts.append(str(arg))
                
            # Include relevant kwargs in the cache key
            for key, value in kwargs.items():
                if key != 'self' and not key.startswith('_'):
                    parts.append(f"{key}:{value}")
            
            cache_key = ":".join(parts)
            result = cache.get(cache_key)
            
            if result is None:
                result = func(self, *args, **kwargs)
                # Use the default TTL if timeout is None
                cache_ttl = timeout if timeout is not None else getattr(settings, 'CACHE_TTL', 60 * 15)
                cache.set(cache_key, result, cache_ttl)
                
            return result
        return wrapper
    return decorator

def invalidate_model_cache(instance):
    """
    Invalidate all cached properties for a model instance.
    Call this in model save() and delete() methods.
    """
    # Create a pattern that matches all cached properties for this instance
    pattern = f"{instance.__class__.__name__}:{instance.id}:*"
    
    # Get all keys matching the pattern and delete them
    if hasattr(cache, 'delete_pattern'):
        # For backends that support pattern deletion (like redis)
        cache.delete_pattern(pattern)
    else:
        # Fallback for backends that don't support pattern deletion
        # For proper implementation, you'd need to track the keys elsewhere
        pass
