/**
 * Task Manager - Task-specific JavaScript functionality
 * Handles task status updates, comments, attachments, and form enhancements
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all task-related functionality
    initTaskStatusUpdates();
    initCommentSystem();
    initAttachmentSystem();
    initTaskFormEnhancements();
});

/**
 * Task Status Updates
 * Handles updating task status via AJAX and updating UI elements
 */
function initTaskStatusUpdates() {
    // Get all status update elements
    const statusSelects = document.querySelectorAll('.task-status-select');
    const statusButtons = document.querySelectorAll('.task-status-btn');
    
    // Handle status select changes
    statusSelects.forEach(select => {
        select.addEventListener('change', function() {
            const taskId = this.getAttribute('data-task-id');
            const newStatus = this.value;
            
            updateTaskStatus(taskId, newStatus, this);
        });
    });
    
    // Handle status button clicks
    statusButtons.forEach(button => {
        button.addEventListener('click', function() {
            const taskId = this.getAttribute('data-task-id');
            const newStatus = this.getAttribute('data-status');
            
            // Don't do anything if the button is disabled
            if (this.hasAttribute('disabled')) {
                return;
            }
            
            updateTaskStatus(taskId, newStatus, this);
        });
    });
    
    // Function to update task status via AJAX
    function updateTaskStatus(taskId, newStatus, element) {
        // Create a loading state
        const originalText = element.tagName === 'BUTTON' ? element.innerHTML : '';
        const originalValue = element.tagName === 'SELECT' ? element.value : '';
        
        if (element.tagName === 'BUTTON') {
            element.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Updating...';
            element.disabled = true;
        } else if (element.tagName === 'SELECT') {
            element.disabled = true;
        }
        
        // Prepare data for the request
        const data = JSON.stringify({
            status: newStatus
        });
        
        // Send AJAX request
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
                throw new Error(`Server responded with ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                // Update UI elements
                updateTaskStatusUI(taskId, newStatus, data.status_display);
                
                // Show success notification
                showNotification(data.message || 'Task status updated successfully', 'success');
            } else {
                // Show error message
                showNotification(data.message || 'Error updating task status', 'error');
                
                // Revert back to original value
                if (element.tagName === 'SELECT') {
                    element.value = originalValue;
                }
            }
        })
        .catch(error => {
            console.error('Error updating task status:', error);
            showNotification('An error occurred while updating the task status', 'error');
            
            // Revert back to original value
            if (element.tagName === 'SELECT') {
                element.value = originalValue;
            }
        })
        .finally(() => {
            // Restore element state
            if (element.tagName === 'BUTTON') {
                element.innerHTML = originalText;
                element.disabled = false;
            } else if (element.tagName === 'SELECT') {
                element.disabled = false;
            }
        });
    }
    
    // Function to update task status UI elements
    function updateTaskStatusUI(taskId, newStatus, statusDisplay) {
        // Update task card if on the list page
        const taskCard = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (taskCard) {
            // Remove all status classes
            taskCard.classList.remove('status-todo', 'status-in-progress', 'status-review', 'status-completed', 'status-archived');
            
            // Add new status class
            taskCard.classList.add(`status-${newStatus}`);
            
            // Update status badge
            const statusBadge = taskCard.querySelector('.status-badge');
            if (statusBadge) {
                statusBadge.textContent = statusDisplay;
                statusBadge.className = `status-badge status-${newStatus}`;
            }
        }
        
        // Update status tag if on the detail page
        const statusTag = document.querySelector('.task-status-tag');
        if (statusTag) {
            statusTag.className = `task-status-tag status-${newStatus}`;
            const statusText = statusTag.querySelector('span');
            if (statusText) {
                statusText.textContent = statusDisplay;
            }
        }
        
        // Update progress bar if on the detail page
        updateProgressBar(newStatus);
        
        // Update all status selects to reflect the new status
        document.querySelectorAll('.task-status-select').forEach(select => {
            select.value = newStatus;
        });
        
        // Disable "Mark Complete" buttons if the task is now completed
        if (newStatus === 'completed') {
            document.querySelectorAll('.task-status-btn[data-status="completed"]').forEach(btn => {
                btn.disabled = true;
            });
        } else {
            document.querySelectorAll('.task-status-btn[data-status="completed"]').forEach(btn => {
                btn.disabled = false;
            });
        }
    }
    
    // Function to update progress bar based on status
    function updateProgressBar(status) {
        const progressBar = document.querySelector('.progress-fill');
        const progressPercentage = document.querySelector('.progress-percentage');
        
        if (!progressBar || !progressPercentage) {
            return;
        }
        
        // Define percentages for each status
        const percentages = {
            'todo': 0,
            'in_progress': 50,
            'review': 80,
            'completed': 100,
            'archived': 100
        };
        
        const percentage = percentages[status] || 0;
        
        // Animate the progress bar
        progressBar.style.width = `${percentage}%`;
        progressPercentage.textContent = `${percentage}%`;
        
        // Add classes for visual feedback
        if (percentage === 100) {
            progressBar.classList.add('completed');
        } else {
            progressBar.classList.remove('completed');
        }
    }
}

/**
 * Comment System
 * Handles submitting comments via AJAX and updating the UI
 */
function initCommentSystem() {
    const commentForm = document.querySelector('.comment-form');
    
    if (!commentForm) {
        return;
    }
    
    // Handle comment form submission
    commentForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Validate form
        const commentText = this.querySelector('textarea').value.trim();
        if (!commentText) {
            showNotification('Please enter a comment before submitting', 'warning');
            return;
        }
        
        // Get task ID from form action URL
        const taskId = this.action.split('/').slice(-2)[0];
        
        // Disable submit button and show loading
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        submitBtn.disabled = true;
        
        // Prepare form data
        const formData = new FormData(this);
        
        // Send AJAX request
        fetch(this.action, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            },
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'success') {
                // Add the new comment to the UI
                addCommentToUI(data);
                
                // Clear the form
                this.reset();
                
                // Show success message
                showNotification(data.message || 'Comment added successfully', 'success');
            } else {
                showNotification(data.message || 'Error adding comment', 'error');
            }
        })
        .catch(error => {
            console.error('Error submitting comment:', error);
            showNotification('An error occurred while submitting your comment', 'error');
        })
        .finally(() => {
            // Restore submit button
            submitBtn.innerHTML = originalBtnText;
            submitBtn.disabled = false;
        });
    });
    
    // Function to add a new comment to the UI
    function addCommentToUI(data) {
        const commentsList = document.querySelector('.comments-list');
        const emptyState = commentsList.querySelector('.comments-empty');
        
        // Remove empty state if present
        if (emptyState) {
            emptyState.remove();
        }
        
        // Create new comment element
        const newComment = document.createElement('div');
        newComment.className = 'comment-item new-comment';
        
        // Set comment HTML
        newComment.innerHTML = `
            <div class="comment-header">
                <div class="comment-user">
                    <div class="avatar-initials avatar-sm">${data.user.charAt(0).toUpperCase()}</div>
                    <span class="comment-username">${data.user}</span>
                </div>
                <div class="comment-date">
                    ${data.created_at}
                </div>
            </div>
            <div class="comment-content">
                ${data.text.replace(/\n/g, '<br>')}
            </div>
        `;
        
        // Add to the comments list
        commentsList.insertBefore(newComment, commentsList.firstChild);
        
        // Highlight the new comment briefly
        setTimeout(() => {
            newComment.classList.add('highlight');
            
            setTimeout(() => {
                newComment.classList.remove('highlight', 'new-comment');
            }, 1500);
        }, 100);
        
        // Update comment count
        const commentCount = document.querySelector('.card-title:contains("Comments")');
        if (commentCount) {
            const count = commentsList.querySelectorAll('.comment-item').length;
            commentCount.innerHTML = `<i class="fas fa-comments"></i> Comments (${count})`;
        }
    }
}

/**
 * Attachment System
 * Handles file uploads with progress indication and validation
 */
function initAttachmentSystem() {
    const attachmentForm = document.querySelector('.attachment-form');
    
    if (!attachmentForm) {
        return;
    }
    
    const fileInput = attachmentForm.querySelector('input[type="file"]');
    const nameInput = attachmentForm.querySelector('input[name="name"]');
    
    // Automatically set the name field when a file is selected
    if (fileInput && nameInput) {
        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                // Set the name field to the file name (without extension)
                const fileName = this.files[0].name.split('.').slice(0, -1).join('.');
                nameInput.value = fileName;
                
                // Validate file size
                if (this.files[0].size > 10 * 1024 * 1024) { // 10MB limit
                    showNotification('File size exceeds 10MB limit', 'error');
                    this.value = '';
                    nameInput.value = '';
                }
                
                // Validate file type
                const validTypes = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf', 
                                   'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
                                   'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                   'text/plain', 'application/zip'];
                                   
                if (!validTypes.includes(this.files[0].type)) {
                    showNotification('Invalid file type. Please upload a valid document or image.', 'error');
                    this.value = '';
                    nameInput.value = '';
                }
            }
        });
    }
    
    // Handle form submission
    attachmentForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Validate form
        if (!fileInput.files || !fileInput.files[0]) {
            showNotification('Please select a file to upload', 'warning');
            return;
        }
        
        if (!nameInput.value.trim()) {
            showNotification('Please provide a name for the attachment', 'warning');
            return;
        }
        
        // Show upload progress
        const submitBtn = this.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
        submitBtn.disabled = true;
        
        // Create progress bar
        const progressContainer = document.createElement('div');
        progressContainer.className = 'upload-progress';
        progressContainer.innerHTML = `
            <div class="progress-bar-container">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
                <div class="progress-percentage">0%</div>
            </div>
        `;
        
        this.appendChild(progressContainer);
        
        // Create FormData and add file
        const formData = new FormData(this);
        
        // Create XMLHttpRequest for progress tracking
        const xhr = new XMLHttpRequest();
        
        // Track upload progress
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentage = Math.round((e.loaded / e.total) * 100);
                progressContainer.querySelector('.progress-fill').style.width = `${percentage}%`;
                progressContainer.querySelector('.progress-percentage').textContent = `${percentage}%`;
            }
        });
        
        // Handle completion
        xhr.addEventListener('load', function() {
            if (xhr.status >= 200 && xhr.status < 300) {
                // Success
                try {
                    const response = JSON.parse(xhr.responseText);
                    showNotification(response.message || 'File uploaded successfully', 'success');
                    
                    // Reset form and refresh attachments list
                    attachmentForm.reset();
                    
                    // Check if we need to reload the page or update UI directly
                    if (response.reload) {
                        window.location.reload();
                    } else if (response.attachment) {
                        // Add new attachment to UI
                        addAttachmentToUI(response.attachment);
                    }
                } catch (e) {
                    console.error('Error parsing response:', e);
                    showNotification('File uploaded but there was an error updating the UI', 'warning');
                    
                    // Reload the page as a fallback
                    setTimeout(() => window.location.reload(), 1500);
                }
            } else {
                // Server error
                showNotification('Error uploading file. Please try again.', 'error');
                console.error('Server error:', xhr.status, xhr.statusText);
            }
        });
        
        // Handle errors
        xhr.addEventListener('error', function() {
            showNotification('Network error occurred while uploading the file', 'error');
        });
        
        xhr.addEventListener('abort', function() {
            showNotification('File upload was aborted', 'warning');
        });
        
        // Complete handler (runs regardless of success/failure)
        xhr.addEventListener('loadend', function() {
            // Remove progress bar
            progressContainer.remove();
            
            // Restore button
            submitBtn.innerHTML = originalBtnText;
            submitBtn.disabled = false;
        });
        
        // Open and send request
        xhr.open('POST', attachmentForm.action, true);
        xhr.send(formData);
    });
    
    // Function to add a new attachment to the UI
    function addAttachmentToUI(attachment) {
        const attachmentsList = document.querySelector('.attachments-list');
        const emptyState = attachmentsList.querySelector('.attachments-empty');
        const attachmentGrid = attachmentsList.querySelector('.attachment-grid');
        
        // Remove empty state if present
        if (emptyState) {
            emptyState.remove();
        }
        
        // Create attachment grid if not present
        let grid = attachmentGrid;
        if (!grid) {
            grid = document.createElement('div');
            grid.className = 'attachment-grid';
            attachmentsList.appendChild(grid);
        }
        
        // Create new attachment element
        const newAttachment = document.createElement('div');
        newAttachment.className = 'attachment-item new-attachment';
        
        // Generate icon based on file extension
        const fileExtension = attachment.url.split('.').pop().toLowerCase();
        let iconClass = 'fas fa-file';
        
        // Set icon based on file type
        if (['jpg', 'jpeg', 'png', 'gif'].includes(fileExtension)) {
            iconClass = 'fas fa-file-image';
        } else if (['pdf'].includes(fileExtension)) {
            iconClass = 'fas fa-file-pdf';
        } else if (['doc', 'docx'].includes(fileExtension)) {
            iconClass = 'fas fa-file-word';
        } else if (['xls', 'xlsx'].includes(fileExtension)) {
            iconClass = 'fas fa-file-excel';
        } else if (['zip', 'rar'].includes(fileExtension)) {
            iconClass = 'fas fa-file-archive';
        } else if (['txt', 'md'].includes(fileExtension)) {
            iconClass = 'fas fa-file-alt';
        }
        
        // Set attachment HTML
        newAttachment.innerHTML = `
            <div class="attachment-icon">
                <i class="${iconClass}"></i>
            </div>
            <div class="attachment-details">
                <div class="attachment-name">
                    <a href="${attachment.url}" target="_blank">${attachment.name}</a>
                </div>
                <div class="attachment-meta">
                    <span class="attachment-uploader">${attachment.uploaded_by}</span>
                    <span class="attachment-date">${attachment.uploaded_at}</span>
                    <span class="attachment-size">${attachment.size}</span>
                </div>
            </div>
            <div class="attachment-actions">
                <a href="${attachment.url}" class="btn btn-sm btn-outline" download>
                    <i class="fas fa-download"></i>
                </a>
                <a href="${attachment.delete_url}" class="btn btn-sm btn-danger" onclick="return confirm('Are you sure you want to delete this attachment?')">
                    <i class="fas fa-trash"></i>
                </a>
            </div>
        `;
        
        // Add to the attachments grid
        grid.appendChild(newAttachment);
        
        // Highlight the new attachment briefly
        setTimeout(() => {
            newAttachment.classList.add('highlight');
            
            setTimeout(() => {
                newAttachment.classList.remove('highlight', 'new-attachment');
            }, 1500);
        }, 100);
        
        // Update attachment count
        const attachmentCount = document.querySelector('.card-title:contains("Attachments")');
        if (attachmentCount) {
            const count = grid.querySelectorAll('.attachment-item').length;
            attachmentCount.innerHTML = `<i class="fas fa-paperclip"></i> Attachments (${count})`;
        }
    }
}

/**
 * Task Form Enhancements
 * Handles form validation, rich text editing, and date pickers
 */
function initTaskFormEnhancements() {
    const taskForm = document.querySelector('.task-form');
    
    if (!taskForm) {
        return;
    }
    
    // Initialize deadline datetime picker if available
    const deadlineInput = taskForm.querySelector('input[name="deadline"]');
    if (deadlineInput) {
        // Modern browsers support datetime-local input
        // This is a simple enhancement to ensure the field is properly formatted
        deadlineInput.addEventListener('blur', function() {
            if (this.value && !this.value.includes('T')) {
                // If a date was entered without time, append default time (12:00)
                this.value = this.value + 'T12:00';
            }
        });
    }
    
    // Add simple character counter for description field
    const descriptionField = taskForm.querySelector('textarea[name="description"]');
    if (descriptionField) {
        // Create counter element
        const counter = document.createElement('div');
        counter.className = 'character-counter';
        counter.innerHTML = `<span class="current">0</span> characters`;
        
        // Insert after description field
        descriptionField.parentNode.insertBefore(counter, descriptionField.nextSibling);
        
        // Update counter on input
        descriptionField.addEventListener('input', function() {
            const length = this.value.length;
            counter.querySelector('.current').textContent = length;
            
            // Add classes for visual feedback
            if (length > 1000) {
                counter.classList.add('warning');
            } else {
                counter.classList.remove('warning');
            }
        });
        
        // Trigger initial update
        descriptionField.dispatchEvent(new Event('input'));
    }
    
    // Add validation before form submission
    taskForm.addEventListener('submit', function(e) {
        let isValid = true;
        
        // Required fields validation
        taskForm.querySelectorAll('input[required], select[required], textarea[required]').forEach(field => {
            if (!field.value.trim()) {
                isValid = false;
                field.classList.add('is-invalid');
                
                // Add feedback message if not present
                let feedback = field.parentNode.querySelector('.invalid-feedback');
                if (!feedback) {
                    feedback = document.createElement('div');
                    feedback.className = 'invalid-feedback';
                    field.parentNode.appendChild(feedback);
                }
                feedback.textContent = 'This field is required';
            } else {
                field.classList.remove('is-invalid');
                field.classList.add('is-valid');
            }
        });
        
        if (!isValid) {
            e.preventDefault();
            showNotification('Please fill in all required fields', 'warning');
            
            // Scroll to first invalid field
            const firstInvalid = taskForm.querySelector('.is-invalid');
            if (firstInvalid) {
                firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                firstInvalid.focus();
            }
        }
    });
}

// Utility function to get CSRF token from cookies
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value || '';
}
