import time
import json
import uuid
import logging
import traceback
from django.conf import settings
from django.http import JsonResponse, HttpResponseServerError
from django.template.loader import render_to_string
from django.utils.deprecation import MiddlewareMixin

# Configure loggers
request_logger = logging.getLogger('tasks.request')
security_logger = logging.getLogger('security')
performance_logger = logging.getLogger('performance')
audit_logger = logging.getLogger('audit')
error_logger = logging.getLogger('error')


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all requests and responses.
    
    Logs request details including:
    - Request method
    - Request path
    - Request headers (excluding sensitive data)
    - Request body (for non-binary content)
    - User ID (if authenticated)
    - IP address
    """
    
    def __init__(self, get_response=None):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Generate a unique request ID
        request.id = str(uuid.uuid4())
        request.start_time = time.time()
        
        # Get user info if user is authenticated
        # Check if user attribute exists (added by AuthenticationMiddleware)
        if hasattr(request, 'user'):
            user_info = {
                'authenticated': request.user.is_authenticated,
                'id': request.user.id if request.user.is_authenticated else None,
                'username': request.user.username if request.user.is_authenticated else None,
            }
        else:
            # User middleware hasn't run yet
            user_info = {
                'authenticated': False,
                'id': None,
                'username': None,
            }
        
        # Get client IP
        client_ip = self._get_client_ip(request)
        
        # Log request details
        log_data = {
            'request_id': request.id,
            'method': request.method,
            'path': request.path,
            'query_params': dict(request.GET),
            'client_ip': client_ip,
            'user': user_info
        }
        
        # Only log request body for non-GET requests that are not file uploads
        if request.method not in ('GET', 'HEAD') and not request.content_type.startswith('multipart/form-data'):
            try:
                # Try to parse request body as JSON
                if request.body:
                    log_data['body'] = json.loads(request.body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # If not JSON, log raw body size
                log_data['body_size'] = len(request.body)
        
        # Log request headers (excluding sensitive ones)
        headers = {}
        for key, value in request.META.items():
            if key.startswith('HTTP_'):
                header_name = key[5:].lower().replace('_', '-')
                # Skip sensitive headers
                if not header_name in ('authorization', 'cookie', 'proxy-authorization'):
                    headers[header_name] = value
        
        log_data['headers'] = headers
        
        # Log the request
        request_logger.info(f"Request {request.id}: {request.method} {request.path}", extra={'data': log_data})
        
        # If this is a security-sensitive endpoint, log to security logger
        sensitive_paths = ['/admin/', '/login/', '/register/', '/password/', '/api/token/']
        if any(path in request.path for path in sensitive_paths):
            security_logger.info(f"Security-sensitive request {request.id}: {request.method} {request.path}",
                               extra={'data': log_data})
        
        return None

    def process_response(self, request, response):
        # Calculate request processing time
        if hasattr(request, 'start_time'):
            processing_time = time.time() - request.start_time
            
            # Log performance metrics
            performance_logger.info(
                f"Request {getattr(request, 'id', 'unknown')} completed in {processing_time:.4f}s",
                extra={
                    'request_id': getattr(request, 'id', 'unknown'),
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                    'processing_time': processing_time,
                }
            )
            
            # Add custom header with processing time
            response['X-Processing-Time'] = str(processing_time)
        
        # Log response summary
        log_data = {
            'request_id': getattr(request, 'id', 'unknown'),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
        }
        
        # Log error responses with more detail
        if response.status_code >= 400:
            log_level = logging.WARNING if response.status_code < 500 else logging.ERROR
            request_logger.log(log_level, f"Error response {log_data['status_code']} for request {log_data['request_id']}",
                             extra={'data': log_data})
        else:
            request_logger.info(f"Response {log_data['status_code']} for request {log_data['request_id']}",
                              extra={'data': log_data})
            
        return response
    
    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Get first IP in case of proxy chain
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class ExceptionLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to handle and log uncaught exceptions.
    
    - Logs detailed exception information
    - Returns appropriate error responses based on request type (HTML or API)
    - Notifies admins of critical errors
    """
    
    def process_exception(self, request, exception):
        # Get exception details
        error_id = str(uuid.uuid4())
        error_message = str(exception)
        error_class = exception.__class__.__name__
        error_traceback = traceback.format_exc()
        
        # Prepare error log data
        log_data = {
            'error_id': error_id,
            'error_class': error_class,
            'error_message': error_message,
            'request_id': getattr(request, 'id', 'unknown'),
            'method': request.method,
            'path': request.path,
            'user_id': request.user.id if hasattr(request, 'user') and request.user.is_authenticated else None,
            'traceback': error_traceback,
        }
        
        error_logger.error(
            f"Uncaught exception ({error_class}): {error_message}",
            extra={'data': log_data},
            exc_info=True
        )
        
        # Return appropriate response based on request type
        if request.headers.get('Accept', '').lower() == 'application/json' or \
           request.headers.get('Content-Type', '').lower() == 'application/json':
            # API request - return JSON error response
            return JsonResponse({
                'error': True,
                'error_id': error_id,
                'message': 'An unexpected error occurred. Our team has been notified.',
                'status_code': 500
            }, status=500)
        else:
            # HTML request - render error page
            if settings.DEBUG:
                # In debug mode, let Django's default error handler display the error
                return None
            else:
                # In production, show a generic error page
                context = {
                    'error_id': error_id,
                    'request_path': request.path,
                }
                html = render_to_string('tasks/error/500.html', context)
                return HttpResponseServerError(html)


class AuditLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log security and audit events.
    
    - Logs user authentication events
    - Logs sensitive data access
    - Logs modification actions (POST, PUT, DELETE)
    """
    
    SENSITIVE_PATHS = [
        '/admin/',
        '/login/',
        '/register/',
        '/profile/',
        '/settings/',
        '/password/',
    ]
    
    SENSITIVE_OPERATIONS = [
        '/task/create',
        '/task/delete',
        '/task/status',
        '/project/create',
        '/project/update',
        '/project/delete',
        '/user/',
    ]
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Skip static and media files
        if request.path.startswith(('/static/', '/media/')):
            return None
            
        # Determine if this is a sensitive path or operation
        is_sensitive_path = any(path in request.path for path in self.SENSITIVE_PATHS)
        is_sensitive_operation = any(op in request.path for op in self.SENSITIVE_OPERATIONS)
        is_data_modification = request.method in ('POST', 'PUT', 'DELETE', 'PATCH')
        
        # Log authentication events
        if '/login/' in request.path and request.method == 'POST':
            username = request.POST.get('username', 'unknown')
            audit_logger.info(f"Login attempt for user '{username}'", extra={
                'event_type': 'auth_attempt',
                'username': username,
                'client_ip': self._get_client_ip(request),
                'request_id': getattr(request, 'id', 'unknown'),
            })
            
        # Log sensitive data access
        elif is_sensitive_path and request.user.is_authenticated:
            audit_logger.info(f"Sensitive data access: {request.path}", extra={
                'event_type': 'sensitive_access',
                'user_id': request.user.id,
                'username': request.user.username,
                'path': request.path,
                'method': request.method,
                'client_ip': self._get_client_ip(request),
                'request_id': getattr(request, 'id', 'unknown'),
            })
            
        # Log data modification operations
        elif (is_sensitive_operation or is_data_modification) and request.user.is_authenticated:
            audit_logger.info(f"Data modification: {request.method} {request.path}", extra={
                'event_type': 'data_modification',
                'user_id': request.user.id,
                'username': request.user.username,
                'path': request.path,
                'method': request.method,
                'client_ip': self._get_client_ip(request),
                'request_id': getattr(request, 'id', 'unknown'),
            })
            
        return None
    
    def _get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip


class PerformanceMonitoringMiddleware(MiddlewareMixin):
    """
    Middleware to monitor performance of requests.
    
    - Tracks request processing time
    - Logs slow requests
    - Adds performance metrics headers to responses
    """
    
    # Define slow request threshold (in seconds)
    SLOW_REQUEST_THRESHOLD = getattr(settings, 'SLOW_REQUEST_THRESHOLD', 1.0)
    
    def process_request(self, request):
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            # Calculate processing time
            processing_time = time.time() - request.start_time
            
            # Add processing time header
            response['X-Processing-Time'] = f"{processing_time:.4f}s"
            
            # Log slow requests
            if processing_time > self.SLOW_REQUEST_THRESHOLD:
                performance_logger.warning(
                    f"Slow request detected: {request.method} {request.path} took {processing_time:.4f}s",
                    extra={
                        'request_id': getattr(request, 'id', 'unknown'),
                        'method': request.method,
                        'path': request.path,
                        'processing_time': processing_time,
                        'threshold': self.SLOW_REQUEST_THRESHOLD,
                    }
                )
                
            # Add detailed performance breakdown if available
            if hasattr(request, 'performance_stats'):
                for key, value in request.performance_stats.items():
                    response[f'X-Performance-{key.replace("_", "-")}'] = f"{value:.4f}s"
                    
        return response

