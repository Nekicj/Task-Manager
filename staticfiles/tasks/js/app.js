/**
 * Task Manager Application JavaScript
 */

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
    
    // Initialize popovers
    const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
    const popoverList = [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
    
    // Setup AJAX CSRF token
    setupAjaxCsrf();
    
    // Initialize task status updates
    initTaskStatusUpdates();
    
    // Initialize comment form AJAX submission
    initCommentForm();
    
    // Initialize drag and drop for kanban board
    initKanbanDragDrop();
    
    // Initialize form validation
    initFormValidation();
    
    // Initialize file upload previews
    initFileUploads();
});

/**
 * Setup CSRF token for AJAX requests
 */
function setupAjaxCsrf() {
    // Get CSRF token from cookie
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    const csrftoken = getCookie('csrftoken');
    
    // Add CSRF token to AJAX requests
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });
}

/**
 * Initialize task status updates via AJAX
 */
function initTaskStatusUpdates() {
    $('.task-status-select').on('change', function() {
        const taskId = $(this).data('task-id');
        const newStatus = $(this).val();
        const statusDisplay = $(this).find('option:selected').text();
        
        if (!taskId) {
            console.error('No task ID provided for status update');
            return;
        }
        
        // Show loading indicator
        $(this).addClass('disabled');
        const loadingSpinner = $('<span class="spinner-border spinner-border-sm ms-1" role="status" aria-hidden="true"></span>');
        $(this).parent().append(loadingSpinner);
        
        // Send AJAX request to update task status
        $.ajax({
            url: `/tasks/${taskId}/update-status/`,
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ status: newStatus }),
            success: function(response) {
                // Update UI to reflect new status
                const statusElement = $(`.task-status-badge[data-task-id="${taskId}"]`);
                
                // Remove old status classes
                statusElement.removeClass('task-status-todo task-status-in-progress task-status-review task-status-completed task-status-archived');
                
                // Add new status class
                statusElement.addClass(`task-status-${newStatus}`);
                statusElement.text(statusDisplay);
                
                // Show success toast
                showToast('Success', `Task status updated to ${statusDisplay}`, 'success');
                
                // Update progress bars or other UI elements
                updateTaskProgress(taskId, newStatus);
            },
            error: function(xhr) {
                console.error('Error updating task status:', xhr.responseText);
                showToast('Error', 'Failed to update task status', 'error');
                
                // Reset select to previous value
                $(this).val($(this).data('original-status'));
            },
            complete: function() {
                // Remove loading indicator
                $(this).removeClass('disabled');
                loadingSpinner.remove();
            }
        });
    });
}

/**
 * Initialize comment form AJAX submission
 */
function initCommentForm() {
    $('#comment-form').on('submit', function(e) {
        e.preventDefault();
        
        const form = $(this);
        const url = form.attr('action');
        const formData = new FormData(form[0]);
        
        // Disable form during submission
        form.addClass('form-loading');
        form.find('button[type="submit"]').prop('disabled', true);
        
        $.ajax({
            url: url,
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(response) {
                if (response.status === 'success') {
                    // Add the new comment to the comments list
                    const commentHtml = `
                        <div class="comment">
                            <div class="comment-header">
                                <span class="comment-user">${response.user}</span

