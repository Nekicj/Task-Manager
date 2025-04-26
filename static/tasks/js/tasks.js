/**
 * Task Manager - Task-specific JavaScript
 * Handles task operations, filtering, and kanban board functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    initTaskDragAndDrop();
    initTaskFiltering();
    initTaskSearch();
    initTaskComments();
    initTaskAttachments();
    initTaskProgress();
});

/**
 * Task Drag and Drop for Kanban Board
 * Enables dragging tasks between status columns
 */
function initTaskDragAndDrop() {
    // Check if we're on a page with a kanban board
    const kanbanBoard = document.getElementById('kanban-board');
    if (!kanbanBoard) return;
    
    // Get all draggable task cards
    const draggables = document.querySelectorAll('.draggable');
    const columns = document.querySelectorAll('.kanban-column');
    
    // Initialize draggable items
    draggables.forEach(draggable => {
        draggable.addEventListener('dragstart', () => {
            draggable.classList.add('dragging');
        });
        
        draggable.addEventListener('dragend', () => {
            draggable.classList.remove('dragging');
        });
        
        // Make the element draggable
        draggable.setAttribute('draggable', 'true');
    });
    
    // Initialize drop zones (columns)
    columns.forEach(column => {
        column.addEventListener('dragover', e => {
            e.preventDefault();
            const dragging = document.querySelector('.dragging');
            const columnBody = column.querySelector('.column-body');
            
            if (dragging && columnBody) {
                const afterElement = getDragAfterElement(columnBody, e.clientY);
                if (afterElement) {
                    columnBody.insertBefore(dragging, afterElement);
                } else {
                    columnBody.appendChild(dragging);
                }
                
                // Get the new status from the column
                const newStatus = column.getAttribute('data-status');
                const taskId = dragging.getAttribute('data-task-id');
                
                // Update task status via AJAX
                if (taskId && newStatus) {
                    updateTaskStatus(taskId, newStatus, dragging);
                }
            }
        });
    });
    
    // Helper function to determine where to insert the dragged element
    function getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll('.draggable:not(.dragging)')];
        
        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            
            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }
    
    /**
     * Update task status via AJAX
     * @param {string} taskId - The ID of the task
     * @param {string} newStatus - The new status to set
     * @param {HTMLElement} element - The task card element
     */
    function updateTaskStatus(taskId, newStatus, element) {
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
                if (element) {
                    // Remove old status classes
                    element.classList.remove('status-todo', 'status-in-progress', 'status-review', 'status-completed', 'status-archived');
                    // Add new status class
                    element.classList.add(`status-${newStatus}`);
                }
                
                // Update column counts
                updateColumnCounts();
                
                // Show success notification
                showNotification(data.message || 'Task status updated successfully', 'success');
            } else {
                showNotification(data.message || 'Error updating task status', 'error');
            }
        })
        .catch(error => {
            console.error('Error updating task status:', error);
            showNotification('Failed to update task status. Please try again.', 'error');
        });
    }
    
    /**
     * Update the task count in each column header
     */
    function updateColumnCounts() {
        columns.forEach(column => {
            const count = column.querySelectorAll('.draggable').length;
            const countElement = column.querySelector('.task-count');
            if (countElement) {
                countElement.textContent = count;
            }
            
            // Update empty state
            const columnBody = column.querySelector('.column-body');
            const emptyState = columnBody.querySelector('.empty-column');
            
            if (count === 0 && !emptyState) {
                // Add empty state
                const emptyDiv = document.createElement('div');
                emptyDiv.className = 'empty-column';
                emptyDiv.innerHTML = '<p>No tasks in this column</p>';
                columnBody.appendChild(emptyDiv);
            } else if (count > 0 && emptyState) {
                // Remove empty state
                emptyState.remove();
            }
        });
    }
}

/**
 * Task Filtering
 * Handles filtering tasks by various criteria
 */
function initTaskFiltering() {
    // Check if we're on a page with task filtering
    const filterForm = document.querySelector('.filter-form');
    if (!filterForm) return;
    
    // Get filter toggle button
    const filterToggle = document.querySelector('.filter-toggle');
    const filterBody = document.querySelector('.filter-body');
    
    // Initialize filter toggle
    if (filterToggle && filterBody) {
        // Check local storage for filter panel state
        const isFilterVisible = localStorage.getItem('filter-panel-visible') !== 'false';
        
        // Set initial state
        if (!isFilterVisible) {
            filterBody.style.display = 'none';
            filterToggle.classList.add('collapsed');
        }
        
        filterToggle.addEventListener('click', function() {
            if (filterBody.style.display === 'none') {
                filterBody.style.display = 'block';
                filterToggle.classList.remove('collapsed');
                localStorage.setItem('filter-panel-visible', 'true');
            } else {
                filterBody.style.display = 'none';
                filterToggle.classList.add('collapsed');
                localStorage.setItem('filter-panel-visible', 'false');
            }
        });
    }
    
    // Handle quick filters
    const quickFilters = document.querySelectorAll('.quick-filter');
    
    quickFilters.forEach(filter => {
        filter.addEventListener('click', function(e) {
            // If already active, remove the filter
            if (filter.classList.contains('active')) {
                e.preventDefault();
                window.location.href = filterForm.getAttribute('action');
            }
        });
    });
    
    // Check if search debounce is enabled
    const searchInput = filterForm.querySelector('input[data-debounce="true"]');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(function() {
            filterForm.submit();
        }, 500));
    }
    
    // Handle clear filter button
    const clearFilterBtn = filterForm.querySelector('.btn-outline');
    if (clearFilterBtn) {
        clearFilterBtn.addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = filterForm.getAttribute('action');
        });
    }
}

/**
 * Task Search
 * Handles real-time task searching
 */
function initTaskSearch() {
    // Check if we have a task search input
    const searchInput = document.getElementById('search');
    if (!searchInput) return;
    
    // Get task list
    const taskList = document.querySelector('.tasks-grid');
    if (!taskList) return;
    
    // Store original HTML for resetting
    const originalHTML = taskList.innerHTML;
    
    // Add event listener with debounce
    searchInput.addEventListener('input', debounce(function() {
        const searchTerm = searchInput.value.trim().toLowerCase();
        
        // If search term is empty, reset to original
        if (searchTerm === '') {
            taskList.innerHTML = originalHTML;
            return;
        }
        
        // Get all task cards
        const taskCards = taskList.querySelectorAll('.task-card');
        
        // Filter tasks based on search term
        taskCards.forEach(card => {
            const title = card.querySelector('.task-title').textContent.toLowerCase();
            const description = card.querySelector('.task-description')?.textContent.toLowerCase() || '';
            
            if (title.includes(searchTerm) || description.includes(searchTerm)) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
        
        // If no tasks match, show a message
        if ([...taskCards].every(card => card.style.display === 'none')) {
            const noResults = document.createElement('div');
            noResults.className = 'no-results';
            noResults.innerHTML = '<p>No tasks match your search query.</p>';
            taskList.appendChild(noResults);
        }
    }, 300));
}

/**
 * Task Comments
 * Handles adding and loading comments on task detail page
 */
function initTaskComments() {
    // Check if we're on a task detail page with comments
    const commentForm = document.querySelector('.comment-form');
    if (!commentForm) return;
    
    // Handle comment form submission
    commentForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const taskId = commentForm.getAttribute('action').split('/').slice(-2)[0];
        const commentText = commentForm.querySelector('textarea').value.trim();
        
        if (!commentText) {
            showNotification('Please enter a comment before submitting', 'warning');
            return;
        }
        
        // Submit comment via AJAX
        submitComment(taskId, commentText, commentForm);
    });
    
    /**
     * Submit a comment via AJAX
     * @param {string} taskId - The ID of the task
     * @param {string} text - The comment text
     * @param {HTMLFormElement} form - The comment form
     */
    function submitComment(taskId, text, form) {
        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalBtnText = submitBtn.innerHTML;
        
        // Show loading state
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
        submitBtn.disabled = true;
        
        // Make AJAX request
        fetch(form.action, {
            method: 'POST',
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
                // Add the new comment to the UI
                addCommentToUI(data);
                
                // Clear the form
                form.reset();
                
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
    }
    
    /**
     * Add a new comment to the UI
     * @param {Object} data - Comment data from the server
     */
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
 * Task Attachments
 * Handles uploading and managing attachments on task detail page
 */
function initTaskAttachments() {
    // Check if we're on a task detail page with attachments
    const attachmentForm = document.querySelector('.attachment-form');
    if (!attachmentForm) return;
    
    const fileInput = attachmentForm.querySelector('input[type="file"]');
    const nameInput = attachmentForm.querySelector('input[name="name"]');
    
    // Automatically set the name field when a file is selected
    if (fileInput && nameInput) {
        fileInput.addEventListener('change', function() {
            if (this.files && this.files[0]) {
                // Set the name field to the file name (without extension)
                const fileName = this.files[0].name.split('.').slice(0, -1).join('.');
                nameInput

