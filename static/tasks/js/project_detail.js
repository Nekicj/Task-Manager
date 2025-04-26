/**
 * Project Detail Page JavaScript
 * Handles Kanban board functionality, task status updates, and other project interactions
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize UI components
    initKanbanBoard();
    initViewToggle();
    initTaskActions();
    initProjectActions();
});

/**
 * Initialize the Kanban board functionality
 */
function initKanbanBoard() {
    const kanbanBoard = document.getElementById('kanban-board');
    
    if (!kanbanBoard) return;
    
    // Get all draggable task cards
    const draggables = document.querySelectorAll('.draggable');
    
    // Get all dropzones (column bodies)
    const dropzones = document.querySelectorAll('.column-body');
    
    // Setup drag and drop for each task card
    draggables.forEach(draggable => {
        setupDraggable(draggable);
    });
    
    // Setup dropzones
    dropzones.forEach(dropzone => {
        setupDropzone(dropzone);
    });
}

/**
 * Setup a draggable task card
 * @param {HTMLElement} draggable - The draggable element
 */
function setupDraggable(draggable) {
    draggable.setAttribute('draggable', true);
    
    // Add drag start event
    draggable.addEventListener('dragstart', function(e) {
        e.dataTransfer.setData('text/plain', draggable.dataset.taskId);
        draggable.classList.add('is-dragging');
        
        // Delay adding a ghost image for better UX
        setTimeout(() => {
            draggable.classList.add('drag-ghost');
        }, 0);
    });
    
    // Add drag end event
    draggable.addEventListener('dragend', function() {
        draggable.classList.remove('is-dragging', 'drag-ghost');
    });
}

/**
 * Setup a dropzone for task cards
 * @param {HTMLElement} dropzone - The dropzone element
 */
function setupDropzone(dropzone) {
    // Get the status of this column
    const columnStatus = dropzone.parentElement.dataset.status;
    
    // Prevent default to allow drop
    dropzone.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('drag-over');
    });
    
    // Handle drag enter
    dropzone.addEventListener('dragenter', function(e) {
        e.preventDefault();
        this.classList.add('drag-over');
    });
    
    // Handle drag leave
    dropzone.addEventListener('dragleave', function() {
        this.classList.remove('drag-over');
    });
    
    // Handle drop event
    dropzone.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('drag-over');
        
        // Get the task id from the data transfer
        const taskId = e.dataTransfer.getData('text/plain');
        
        // If dropping in same column, do nothing
        const taskCard = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
        if (!taskCard) return;
        
        const sourceColumn = taskCard.closest('.kanban-column');
        const targetColumn = this.closest('.kanban-column');
        
        if (sourceColumn === targetColumn) return;
        
        // Update task status via AJAX
        updateTaskStatus(taskId, columnStatus);
        
        // Move the card to this column
        this.appendChild(taskCard);
        
        // Update task counts
        updateTaskCounts();
    });
}

/**
 * Update task status via AJAX
 * @param {string} taskId - The task ID
 * @param {string} newStatus - The new status
 */
function updateTaskStatus(taskId, newStatus) {
    // Get the CSRF token from the page
    const csrfToken = getCsrfToken();
    
    // Send AJAX request to update task status
    fetch(`/tasks/${taskId}/update-status/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            status: newStatus
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            // Show success notification
            showNotification('Task status updated', 'success');
            
            // Update UI if needed
            if (newStatus === 'completed') {
                const taskCard = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
                if (taskCard) {
                    // Update card UI for completed tasks
                    taskCard.classList.add('completed');
                    
                    // Add completion timestamp
                    const now = new Date();
                    const formattedDate = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                    
                    const taskMeta = taskCard.querySelector('.task-meta');
                    if (taskMeta) {
                        const completedEl = document.createElement('div');
                        completedEl.className = 'task-completed';
                        completedEl.innerHTML = `
                            <i class="fas fa-check-circle"></i>
                            Completed: ${formattedDate}
                        `;
                        taskMeta.appendChild(completedEl);
                    }
                }
            }
        } else {
            // Show error notification
            showNotification(data.message || 'Failed to update task status', 'error');
            
            // Reload the page to reset the UI
            window.location.reload();
        }
    })
    .catch(error => {
        console.error('Error updating task status:', error);
        showNotification('Error updating task status', 'error');
        
        // Reload the page to reset the UI
        window.location.reload();
    });
}

/**
 * Update task counts in each column
 */
function updateTaskCounts() {
    const columns = document.querySelectorAll('.kanban-column');
    
    columns.forEach(column => {
        const taskCount = column.querySelectorAll('.task-card').length;
        const taskCountEl = column.querySelector('.task-count');
        
        if (taskCountEl) {
            taskCountEl.textContent = taskCount;
        }
    });
}

/**
 * Initialize view toggle between Kanban and List views
 */
function initViewToggle() {
    const kanbanViewBtn = document.getElementById('view-kanban');
    const listViewBtn = document.getElementById('view-list');
    const kanbanView = document.getElementById('kanban-view');
    const listView = document.getElementById('list-view');
    
    if (!kanbanViewBtn || !listViewBtn) return;
    
    // Toggle between views
    kanbanViewBtn.addEventListener('click', function() {
        kanbanViewBtn.classList.add('active');
        listViewBtn.classList.remove('active');
        
        if (kanbanView) kanbanView.style.display = 'grid';
        if (listView) listView.style.display = 'none';
    });
    
    listViewBtn.addEventListener('click', function() {
        listViewBtn.classList.add('active');
        kanbanViewBtn.classList.remove('active');
        
        if (kanbanView) kanbanView.style.display = 'none';
        if (listView) listView.style.display = 'block';
    });
}

/**
 * Initialize task action buttons
 */
function initTaskActions() {
    // Setup status update buttons
    const statusButtons = document.querySelectorAll('.task-status-btn');
    
    statusButtons.forEach(button => {
        button.addEventListener('click', function() {
            const taskId = this.dataset.taskId;
            const newStatus = this.dataset.status;
            
            // Update task status
            updateTaskStatus(taskId, newStatus);
            
            // Move the card to the appropriate column
            moveTaskCard(taskId, newStatus);
        });
    });
}

/**
 * Move a task card to a different column
 * @param {string} taskId - The task ID
 * @param {string} newStatus - The new status
 */
function moveTaskCard(taskId, newStatus) {
    const taskCard = document.querySelector(`.task-card[data-task-id="${taskId}"]`);
    if (!taskCard) return;
    
    const targetColumn = document.querySelector(`.kanban-column[data-status="${newStatus}"] .column-body`);
    if (!targetColumn) return;
    
    // Animate the card moving
    taskCard.classList.add('moving');
    
    // Add a small delay for the animation
    setTimeout(() => {
        targetColumn.appendChild(taskCard);
        taskCard.classList.remove('moving');
        
        // Update task counts
        updateTaskCounts();
    }, 300);
}

/**
 * Initialize project action buttons
 */
function initProjectActions() {
    // Archive/Unarchive project buttons
    const archiveButtons = document.querySelectorAll('.toggle-archive-btn');
    
    archiveButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const projectId = this.dataset.projectId;
            const action = this.dataset.action; // 'archive' or 'unarchive'
            
            toggleProjectArchived(projectId, action);
        });
    });
}

/**
 * Toggle project archived status
 * @param {string} projectId - The project ID
 * @param {string} action - Either 'archive' or 'unarchive'
 */
function toggleProjectArchived(projectId, action) {
    // Get the CSRF token
    const csrfToken = getCsrfToken();
    
    // Send AJAX request
    fetch(`/projects/${projectId}/toggle-archive/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({
            action: action
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            // Show success notification
            const message = action === 'archive' ? 'Project archived' : 'Project unarchived';
            showNotification(message, 'success');
            
            // Reload the page to update UI
            window.location.reload();
        } else {
            // Show error notification
            showNotification(data.message || 'Failed to update project', 'error');
        }
    })
    .catch(error => {
        console.error('Error updating project:', error);
        showNotification('Error updating project', 'error');
    });
}

/**
 * Get CSRF token from cookies
 * @returns {string} The CSRF token
 */
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

/**
 * Show a notification to the user
 * @param {string} message - The notification message
 * @param {string} type - The notification type (success, error, info)
 */
function showNotification(message, type = 'info') {
    // Check if we have a notifications container
    let container = document.getElementById('notifications-container');
    
    // If not, create one
    if (!container) {
        container = document.createElement('div');
        container.id = 'notifications-container';
        document.body.appendChild(container);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-icon">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
        </div>
        <div class="notification-content">
            <div class="notification-message">${message}</div>
        </div>
        <button class="notification-close">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    // Add to container
    container.appendChild(notification);
    
    // Add close button functionality
    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.addEventListener('click', function() {
        notification.classList.add('notification-hiding');
        setTimeout(() => {
            notification.remove();
        }, 300);
    });
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        notification.classList.add('notification-hiding');
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 5000);
    
    // Animate in
    setTimeout(() => {
        notification.classList.add('notification-visible');
    }, 10);
}

