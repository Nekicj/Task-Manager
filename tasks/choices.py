

class TaskStatus:
    TODO = 'todo'
    IN_PROGRESS = 'in_progress'
    REVIEW = 'review'
    COMPLETED = 'completed'
    ARCHIVED = 'archived'
    
    CHOICES = [
        (TODO, 'To Do'),
        (IN_PROGRESS, 'In Progress'),
        (REVIEW, 'Review'),
        (COMPLETED, 'Completed'),
        (ARCHIVED, 'Archived'),
    ]


class TaskPriority:
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    URGENT = 'urgent'
    
    CHOICES = [
        (LOW, 'Low'),
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
        (URGENT, 'Urgent'),
    ]

