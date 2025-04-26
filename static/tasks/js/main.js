/**
 * Task Manager - Main JavaScript
 * Handles global functionality like themes, dropdowns, and UI interactions
 */

// Execute when DOM content is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    initThemeToggle();
    initSidebar();
    initDropdowns();
    initNotifications();
    initFormValidation();
    initCollapsibleSections();
});

/**
 * Theme Switching Functionality
 * Handles toggling between light and dark themes
 */
function initThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeLabel = document.getElementById('theme-label');
    const body = document.body;
    const prefersDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    // Check if user has a saved preference, otherwise use system preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        body.classList.remove('light-theme', 'dark-theme');
        body.classList.add(savedTheme);
        updateThemeLabel(savedTheme === 'dark-theme');
    } else {
        // Use system preference as default
        body.classList.add(prefersDarkMode ? 'dark-theme' : 'light-theme');
        updateThemeLabel(prefersDarkMode);
    }
    
    // Handle theme toggle click
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const isDarkTheme = body.classList.contains('dark-theme');
            
            // Toggle theme
            body.classList.remove('light-theme', 'dark-theme');
            body.classList.add(isDarkTheme ? 'light-theme' : 'dark-theme');
            
            // Save preference to localStorage
            localStorage.setItem('theme', isDarkTheme ? 'light-theme' : 'dark-theme');
            
            // Update label
            updateThemeLabel(!isDarkTheme);
        });
    }
    
    function updateThemeLabel(isDark) {
        if (themeLabel) {
            themeLabel.textContent = isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode';
        }
    }
}

/**
 * Sidebar Functionality
 * Handles sidebar toggling and responsive behavior
 */
function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const sidebarClose = document.getElementById('sidebar-close');
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const appContainer = document.querySelector('.app-container');
    
    // Mobile menu toggle
    if (mobileMenuToggle && sidebar) {
        mobileMenuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });
    }
    
    // Close sidebar on mobile
    if (sidebarClose && sidebar) {
        sidebarClose.addEventListener('click', function() {
            sidebar.classList.remove('show');
        });
    }
    
    // Toggle sidebar collapse state (on desktop)
    const sidebarToggle = document.getElementById('sidebar-toggle');
    if (sidebarToggle && appContainer) {
        sidebarToggle.addEventListener('click', function() {
            appContainer.classList.toggle('sidebar-collapsed');
            
            // Save preference to localStorage
            if (appContainer.classList.contains('sidebar-collapsed')) {
                localStorage.setItem('sidebar-collapsed', 'true');
            } else {
                localStorage.setItem('sidebar-collapsed', 'false');
            }
        });
    }
    
    // Restore sidebar state from localStorage
    if (appContainer && localStorage.getItem('sidebar-collapsed') === 'true') {
        appContainer.classList.add('sidebar-collapsed');
    }
    
    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function(e) {
        if (window.innerWidth < 992 && 
            sidebar && 
            sidebar.classList.contains('show') && 
            !e.target.closest('#sidebar') && 
            !e.target.closest('#mobile-menu-toggle')) {
            sidebar.classList.remove('show');
        }
    });
    
    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 992 && sidebar) {
            sidebar.classList.remove('show');
        }
    });
}

/**
 * Dropdown Menu Functionality
 * Handles dropdown toggling and clickaway
 */
function initDropdowns() {
    const dropdownToggles = document.querySelectorAll('.dropdown-toggle');
    
    dropdownToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const dropdown = this.closest('.dropdown');
            const menu = dropdown.querySelector('.dropdown-menu');
            
            // Close all other dropdowns first
            document.querySelectorAll('.dropdown-menu').forEach(otherMenu => {
                if (otherMenu !== menu && otherMenu.classList.contains('show')) {
                    otherMenu.classList.remove('show');
                }
            });
            
            // Toggle current dropdown
            menu.classList.toggle('show');
        });
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown')) {
            document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
                menu.classList.remove('show');
            });
        }
    });
}

/**
 * Notification System
 * Shows and automatically dismisses notification messages
 */
function initNotifications() {
    // Set up existing notifications
    const existingMessages = document.querySelectorAll('.message');
    existingMessages.forEach(message => {
        setTimeout(() => {
            fadeOutAndRemove(message);
        }, 5000);
        
        const closeButton = message.querySelector('.message-close');
        if (closeButton) {
            closeButton.addEventListener('click', function() {
                fadeOutAndRemove(message);
            });
        }
    });
}

/**
 * Show a notification message
 * @param {string} message - The message to display
 * @param {string} type - The type of notification (success, error, info, warning)
 * @param {number} duration - How long to show the notification in ms (default: 5000ms)
 */
function showNotification(message, type = 'info', duration = 5000) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `message message-${type}`;
    
    // Set content
    notification.innerHTML = `
        <div class="message-content">${message}</div>
        <button class="message-close">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Get or create messages container
    let messagesContainer = document.querySelector('.messages');
    if (!messagesContainer) {
        messagesContainer = document.createElement('div');
        messagesContainer.className = 'messages';
        document.querySelector('.content').prepend(messagesContainer);
    }
    
    // Add to DOM
    messagesContainer.appendChild(notification);
    
    // Add animation
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // Set up auto dismiss
    setTimeout(() => {
        fadeOutAndRemove(notification);
    }, duration);
    
    // Set up close button
    const closeButton = notification.querySelector('.message-close');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            fadeOutAndRemove(notification);
        });
    }
}

/**
 * Fade out and remove an element
 * @param {HTMLElement} element - The element to fade out and remove
 */
function fadeOutAndRemove(element) {
    element.classList.add('fade-out');
    
    element.addEventListener('transitionend', function() {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });
}

/**
 * Form Validation
 * Validates forms on submission
 */
function initFormValidation() {
    const forms = document.querySelectorAll('form:not(.no-validation)');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Skip if this is an AJAX form or has a special handler
            if (form.classList.contains('ajax-form') || form.getAttribute('data-handler')) {
                return;
            }
            
            if (!validateForm(form)) {
                e.preventDefault();
                showNotification('Please correct the errors in the form.', 'error');
            }
        });
        
        // Real-time validation on input fields
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                validateInput(input);
            });
        });
    });
    
    function validateForm(form) {
        let isValid = true;
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            // Skip fields with no validation
            if (input.classList.contains('no-validation')) {
                return;
            }
            
            if (!validateInput(input)) {
                isValid = false;
            }
        });
        
        return isValid;
    }
    
    function validateInput(input) {
        // Skip fields with no validation
        if (input.classList.contains('no-validation')) {
            return true;
        }
        
        const value = input.value.trim();
        let isValid = true;
        let errorMessage = '';
        
        // Check required fields
        if (input.hasAttribute('required') && value === '') {
            isValid = false;
            errorMessage = 'This field is required';
        }
        
        // Email validation
        if (input.type === 'email' && value !== '' && !isValidEmail(value)) {
            isValid = false;
            errorMessage = 'Please enter a valid email address';
        }
        
        // Min length validation
        if (input.hasAttribute('minlength') && value.length < parseInt(input.getAttribute('minlength'))) {
            isValid = false;
            errorMessage = `Must be at least ${input.getAttribute('minlength')} characters`;
        }
        
        // Update UI based on validation
        const formGroup = input.closest('.form-group');
        if (formGroup) {
            const feedbackElement = formGroup.querySelector('.invalid-feedback') || 
                                   createFeedbackElement(formGroup);
            
            if (isValid) {
                input.classList.remove('is-invalid');
                input.classList.add('is-valid');
                feedbackElement.style.display = 'none';
            } else {
                input.classList.remove('is-valid');
                input.classList.add('is-invalid');
                feedbackElement.textContent = errorMessage;
                feedbackElement.style.display = 'block';
            }
        }
        
        return isValid;
    }
    
    function createFeedbackElement(formGroup) {
        const feedbackElement = document.createElement('div');
        feedbackElement.className = 'invalid-feedback';
        formGroup.appendChild(feedbackElement);
        return feedbackElement;
    }
    
    function isValidEmail(email) {
        const re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        return re.test(String(email).toLowerCase());
    }
}

/**
 * Collapsible Sections
 * Handles expanding/collapsing of sections
 */
function initCollapsibleSections() {
    const collapsibleHeaders = document.querySelectorAll('[data-toggle="collapse"]');
    
    collapsibleHeaders.forEach(header => {
        const targetId = header.getAttribute('data-target');
        const targetElement = document.querySelector(targetId);
        
        if (targetElement) {
            // Set initial state
            if (localStorage.getItem(targetId) === 'collapsed') {
                targetElement.style.display = 'none';
                header.classList.add('collapsed');
            }
            
            header.addEventListener('click', function() {
                // Toggle visibility
                if (targetElement.style.display === 'none') {
                    targetElement.style.display = 'block';
                    header.classList.remove('collapsed');
                    localStorage.setItem(targetId, 'expanded');
                } else {
                    targetElement.style.display = 'none';
                    header.classList.add('collapsed');
                    localStorage.setItem(targetId, 'collapsed');
                }
            });
        }
    });
}

// Utility function to get CSRF token from cookies
function getCsrfToken() {
    const tokenElement = document.querySelector('[name=csrfmiddlewaretoken]');
    if (tokenElement) {
        return tokenElement.value;
    }
    
    // Fallback to cookie
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 'csrftoken='.length) === 'csrftoken=') {
                cookieValue = decodeURIComponent(cookie.substring('csrftoken='.length));
                break;
            }
        }
    }
    return cookieValue;
}

// Debounce function for limiting how often a function is called
function debounce(func, wait = 300) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

/**
 * Task Manager - Main JavaScript File
 * Handles all interactive functionality for the task management system
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initializeSidebar();
    initializeThemeToggle();
    initializeDropdowns();
    initializeCollapsibleSections();
    initializeTaskStatusUpdates();
    initializeFormValidation();
    initializeNotifications();
    initializeMobileMenu();
});

/**
 * Sidebar functionality
 * Handles sidebar toggling and responsive behavior
 */
function initializeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const sidebarClose = document.getElementById('sidebar-close');
    const appContainer = document.querySelector('.app-container');
    
    // Close sidebar on mobile
    if (sidebarClose) {
        sidebarClose.addEventListener('click', function() {
            sidebar.classList.remove('show');
        });
    }
    
    // Toggle sidebar collapse state (on desktop)
    const sidebarToggle = document.getElementById('sidebar-toggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            appContainer.classList.toggle('sidebar-collapsed');
            
            // Save preference to localStorage
            if (appContainer.classList.contains('sidebar-collapsed')) {
                localStorage.setItem('sidebar-collapsed', 'true');
            } else {
                localStorage.setItem('sidebar-collapsed', 'false');
            }
        });
    }
    
    // Restore sidebar state from localStorage
    if (localStorage.getItem('sidebar-collapsed') === 'true') {
        appContainer.classList.add('sidebar-collapsed');
    }
}

/**
 * Theme toggle functionality
 * Handles switching between light and dark themes
 */
function initializeThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeLabel = document.getElementById('theme-label');
    const body = document.body;
    
    // Check if user has a saved preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        body.classList.remove('light-theme', 'dark-theme');
        body.classList.add(savedTheme);
        updateThemeLabel(savedTheme === 'dark-theme');
    } else {
        // Default to light theme
        body.classList.add('light-theme');
        updateThemeLabel(false);
    }
    
    // Handle theme toggle click
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            const isDarkTheme = body.classList.contains('dark-theme');
            
            // Toggle theme
            body.classList.remove('light-theme', 'dark-theme');
            body.classList.add(isDarkTheme ? 'light-theme' : 'dark-theme');
            
            // Save preference to localStorage
            localStorage.setItem('theme', isDarkTheme ? 'light-theme' : 'dark-theme');
            
            // Update label
            updateThemeLabel(!isDarkTheme);
        });
    }
    
    function updateThemeLabel(isDark) {
        if (themeLabel) {
            themeLabel.textContent = isDark ? 'Light Mode' : 'Dark Mode';
        }
    }
}

/**
 * Dropdown menu functionality
 * Handles dropdown toggling and clickaway closing
 */
function initializeDropdowns() {
    const dropdownToggles = document.querySelectorAll('.dropdown-toggle');
    
    dropdownToggles.forEach(toggle => {
        toggle.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const dropdown = this.closest('.dropdown');
            const menu = dropdown.querySelector('.dropdown-menu');
            
            // Close all other dropdowns first
            document.querySelectorAll('.dropdown-menu').forEach(otherMenu => {
                if (otherMenu !== menu && otherMenu.classList.contains('show')) {
                    otherMenu.classList.remove('show');
                }
            });
            
            // Toggle current dropdown
            menu.classList.toggle('show');
        });
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.dropdown')) {
            document.querySelectorAll('.dropdown-menu.show').forEach(menu => {
                menu.classList.remove('show');
            });
        }
    });
}

/**
 * Collapsible sections
 * Handles expanding/collapsing of sections like in the sidebar
 */
function initializeCollapsibleSections() {
    const collapsibleHeaders = document.querySelectorAll('[data-toggle="collapse"]');
    
    collapsibleHeaders.forEach(header => {
        const targetId = header.getAttribute('data-target');
        const targetElement = document.querySelector(targetId);
        
        if (targetElement) {
            // Set initial state
            if (localStorage.getItem(targetId) === 'collapsed') {
                targetElement.style.display = 'none';
                header.classList.add('collapsed');
            }
            
            header.addEventListener('click', function() {
                // Toggle visibility
                if (targetElement.style.display === 'none') {
                    targetElement.style.display = 'block';
                    header.classList.remove('collapsed');
                    localStorage.setItem(targetId, 'expanded');
                } else {
                    targetElement.style.display = 'none';
                    header.classList.add('collapsed');
                    localStorage.setItem(targetId, 'collapsed');
                }
            });
        }
    });
}

/**
 * Task status updates
 * Handles AJAX requests to update task status
 */
function initializeTaskStatusUpdates() {
    // Find all task status selects/buttons
    const statusSelects = document.querySelectorAll('.task-status-select');
    
    statusSelects.forEach(select => {
        select.addEventListener('change', function() {
            const taskId = this.getAttribute('data-task-id');
            const newStatus = this.value;
            
            if (taskId && newStatus) {
                updateTaskStatus(taskId, newStatus, this);
            }
        });
    });
    
    // Status buttons (if present)
    const statusButtons = document.querySelectorAll('.task-status-btn');
    
    statusButtons.forEach(button => {
        button.addEventListener('click', function() {
            const taskId = this.getAttribute('data-task-id');
            const newStatus = this.getAttribute('data-status');
            
            if (taskId && newStatus) {
                updateTaskStatus(taskId, newStatus, this);
            }
        });
    });
    
    function updateTaskStatus(taskId, newStatus, element) {
        // Show loading indicator
        const originalText = element.innerText || '';
        if (element.tagName === 'BUTTON') {
            element.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
            element.disabled = true;
        }
        
        // Create request data
        const data = JSON.stringify({
            status: newStatus
        });
        
        // Make AJAX request
        fetch(`/tasks/${taskId}/update-status/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            },
            body: data
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Server responded with an error');
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                // Update UI
                const taskElement = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
                if (taskElement) {
                    // Remove old status classes
                    taskElement.classList.remove('status-todo', 'status-in-progress', 'status-review', 'status-completed', 'status-archived');
                    // Add new status class
                    taskElement.classList.add(`status-${newStatus}`);
                }
                
                // Show success notification
                showNotification(data.message, 'success');
            } else {
                showNotification(data.message || 'Error updating task status', 'error');
            }
        })
        .catch(error => {
            console.error('Error updating task status:', error);
            showNotification('Failed to update task status. Please try again.', 'error');
        })
        .finally(() => {
            // Restore button text
            if (element.tagName === 'BUTTON') {
                element.innerHTML = originalText;
                element.disabled = false;
            }
        });
    }
}

/**
 * Form validation and submission
 * Handles client-side validation and AJAX form submission
 */
function initializeFormValidation() {
    const forms = document.querySelectorAll('form:not(.no-validation)');
    
    forms.forEach(form => {
        // Client-side validation
        form.addEventListener('submit', function(e) {
            if (!form.classList.contains('ajax-form')) {
                // For non-AJAX forms, just validate
                if (!validateForm(form)) {
                    e.preventDefault();
                }
            } else {
                // For AJAX forms, prevent default and handle submission
                e.preventDefault();
                if (validateForm(form)) {
                    submitFormViaAjax(form);
                }
            }
        });
        
        // Real-time validation on input fields
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            input.addEventListener('blur', function() {
                validateInput(input);
            });
        });
    });
    
    function validateForm(form) {
        let isValid = true;
        const inputs = form.querySelectorAll('input, select, textarea');
        
        inputs.forEach(input => {
            if (!validateInput(input)) {
                isValid = false;
            }
        });
        
        return isValid;
    }
    
    function validateInput(input) {
        // Skip inputs with no validation
        if (input.classList.contains('no-validation')) {
            return true;
        }
        
        const value = input.value.trim();
        let isValid = true;
        let errorMessage = '';
        
        // Check required fields
        if (input.hasAttribute('required') && value === '') {
            isValid = false;
            errorMessage = 'This field is required';
        }
        
        // Email validation
        if (input.type === 'email' && value !== '' && !isValidEmail(value)) {
            isValid = false;
            errorMessage = 'Please enter a valid email address';
        }
        
        // Min length validation
        if (input.hasAttribute('minlength') && value.length < parseInt(input.getAttribute('minlength'))) {
            isValid = false;
            errorMessage = `Must be at least ${input.getAttribute('minlength')} characters`;
        }
        
        // Update UI based on validation
        const formGroup = input.closest('.form-group');
        if (formGroup) {
            const feedbackElement = formGroup.querySelector('.invalid-feedback') || createFeedbackElement(formGroup);
            
            if (isValid) {
                input.classList.remove('is-invalid');
                input.classList.add('is-valid');
                feedbackElement.style.display = 'none';
            } else {
                input.classList.remove('is-valid');
                input.classList.add('is-invalid');
                feedbackElement.textContent = errorMessage;
                feedbackElement.style.display = 'block';
            }
        }
        
        return isValid;
    }
    
    function createFeedbackElement(formGroup) {
        const feedbackElement = document.createElement('div');
        feedbackElement.className = 'invalid-feedback';
        formGroup.appendChild(feedbackElement);
        return feedbackElement;
    }
    
    function isValidEmail(email) {
        const re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        return re.test(String(email).toLowerCase());
    }
    
    function submitFormViaAjax(form) {
        const formData = new FormData(form);
        const submitButton = form.querySelector('[type="submit"]');
        const originalButtonText = submitButton ? submitButton.innerHTML : '';
        
        // Show loading state
        if (submitButton) {
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
            submitButton.disabled = true;
        }
        
        // Get form action and method
        const action = form.getAttribute('action') || window.location.href;
        const method = form.getAttribute('method') || 'POST';
        
        // Submit form via AJAX
        fetch(action, {
            method: method,
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Server responded with an error');
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                // Handle success
                showNotification(data.message || 'Operation completed successfully', 'success');
                
                // Clear form if needed
                if (form.classList.contains('clear-on-submit')) {
                    form.reset();
                }
                
                // Redirect if needed
                if (data.redirect) {
                    window.location.href = data.redirect;
                }
                
                // Reload if needed
                if (data.reload) {
                    window.location.reload();
                }
                
                // Execute custom success callback if defined
                if (window[form.getAttribute('data-success-callback')]) {
                    window[form.getAttribute('data-success-callback')](data);
                }
            } else {
                // Handle errors
                if (data.errors) {
                    // Display field-specific errors
                    for (const field in data.errors) {
                        const input = form.querySelector(`[name="${field}"]`);
                        if (input) {
                            const formGroup = input.closest('.form-group');
                            if (formGroup) {
                                const feedbackElement = formGroup.querySelector('.invalid-feedback') || createFeedbackElement(formGroup);
                                input.classList.add('is-invalid');
                                feedbackElement.textContent = data.errors[field][0];
                                feedbackElement.style.display = 'block';
                            }
                        }
                    }
                }
                
                showNotification(data.message || 'There was an error processing your request', 'error');
            }
        })
        .catch(error => {
            console.error('Error submitting form:', error);
            showNotification('An error occurred while submitting the form. Please try again.', 'error');
        })
        .finally(() => {
            // Restore button state
            if (submitButton) {
                submitButton.innerHTML = originalButtonText;
                submitButton.disabled = false;
            }
        });
    }
}

/**
 * Notification system
 * Shows and automatically dismisses notification messages
 */
function initializeNotifications() {
    // Set up existing notifications
    const existingMessages = document.querySelectorAll('.message');
    existingMessages.forEach(message => {
        setTimeout(() => {
            fadeOutAndRemove(message);
        }, 5000);
        
        const closeButton = message.querySelector('.message-close');
        if (closeButton) {
            closeButton.addEventListener('click', function() {
                fadeOutAndRemove(message);
            });
        }
    });
}

/**
 * Show a notification message
 * @param {string} message - The message to display
 * @param {string} type - The type of notification (success, error, info, warning)
 * @param {number} duration - How long to show the notification in ms (default: 5000)
 */
function showNotification(message, type = 'info', duration = 5000) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `message message-${type}`;
    
    // Set content
    notification.innerHTML = `
        <div class="message-content">${message}</div>
        <button class="message-close">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Get or create messages container
    let messagesContainer = document.querySelector('.messages');
    if (!messagesContainer) {
        messagesContainer = document.createElement('div');
        messagesContainer.className = 'messages';
        document.querySelector('.content').prepend(messagesContainer);
    }
    
    // Add to DOM
    messagesContainer.appendChild(notification);
    
    // Add animation
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // Set up auto dismiss
    setTimeout(() => {
        fadeOutAndRemove(notification);
    }, duration);
    
    // Set up close button
    const closeButton = notification.querySelector('.message-close');
    if (closeButton) {
        closeButton.addEventListener('click', function() {
            fadeOutAndRemove(notification);
        });
    }
}

/**
 * Fade out and remove an element
 * @param {HTMLElement} element - The element to fade out and remove
 */
function fadeOutAndRemove(element) {
    element.classList.add('fade-out');
    
    element.addEventListener('transitionend', function() {
        if (element.parentNode) {
            element.parentNode.removeChild(element);
        }
    });
}

/**
 * Mobile menu functionality
 * Handles toggling the mobile menu
 */
function initializeMobileMenu() {
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const sidebar = document.getElementById('sidebar');
    
    if (mobileMenuToggle && sidebar) {
        mobileMenuToggle.addEventListener('click', function() {
            sidebar.classList.toggle('show');
        });
    }
    
    // Close sidebar when clicking outside on mobile
    document.addEventListener('click', function(e) {
        if (window.innerWidth < 992 && 
            sidebar && 
            sidebar.classList.contains('show') && 
            !e.target.closest('#sidebar') && 
            !e.target.closest('#mobile-menu-toggle')) {
            sidebar.classList.remove('show');
        }
    });
    
    // Handle window resize
    window.addEventListener('resize', function() {
        if (window.innerWidth >= 992 && sidebar) {
            sidebar.classList.remove('show');
        }
    });
}

/**
 * Get CSRF token from cookies
 * @returns {string} The CSRF token
 */
function getCsrfToken() {
    let cookieValue = null;
    
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, 'csrftoken='.length) === 'csrftoken=') {
                cookieValue = decodeURIComponent(cookie.substring('csrftoken='.length));
                break;
            }
        }
    }
    
    return cookieValue;
}

/**
 * Debounce function for search inputs
 * @param {Function} func - Function to debounce
 * @param {number} wait - Time to wait in ms
 * @returns {Function} Debounced function
 */
function debounce(func, wait = 300) {
    let timeout;
    
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            func(...args);
        };
        
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Format date for display
 * @param {Date|string} date - Date object or date string
 * @param {string} format - Format to use (default: 'short')
 * @returns {string} Formatted date string
 */
function formatDate(date, format = 'short') {
    const dateObj = date instanceof Date ? date : new Date(date);
    
    if (isNaN(dateObj.getTime())) {
        return 'Invalid date';
    }
    
    const now = new Date();
    const isToday = dateObj.toDateString() === now.toDateString();
    const isYesterday = new Date(now - 86400000).toDateString() === dateObj.toDateString();
    const isTomorrow = new Date(now.getTime() + 86400000).toDateString() === dateObj.toDateString();
    
    if (format === 'relative') {
        if (isToday) return 'Today';
        if (isYesterday) return 'Yesterday';
        if (isTomorrow) return 'Tomorrow';
    }
    
    switch (format) {
        case 'time':
            return dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        case 'datetime':
            return `${dateObj.toLocaleDateString()} ${dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
        case 'full':
            return dateObj.toLocaleDateString([], { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
        case 'short':
        default:
            return dateObj.toLocaleDateString();
    }
}

/**
 * Initialize search inputs with debouncing
 */
document.addEventListener('DOMContentLoaded', function() {
    // Find all search inputs with debounce attribute
    const searchInputs = document.querySelectorAll('input[data-debounce="true"]');
    
    searchInputs.forEach(input => {
        const form = input.closest('form');
        
        if (form) {
            // Create debounced handler
            const debouncedSubmit = debounce(function() {
                form.submit();
            }, 500);
            
            // Add event listener
            input.addEventListener('input', debouncedSubmit);
        }
    });
});
