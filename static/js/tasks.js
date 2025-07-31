document.addEventListener('DOMContentLoaded', function() {

    // =========================================================================
    // STATE VARIABLES
    // =========================================================================
    let newItemIdCounter = 0;
    const deletedItemIds = new Set();
    const MAX_SUBTASK_LEVEL = 6;

    // =========================================================================
    // FUNCTION DEFINITIONS
    // =========================================================================

    // --- Core Event Handlers & Logic ---

    function handleAddSubtask(button) {
        const parentId = button.dataset.parentId;
        if (!parentId) {
            console.error("Button is missing a data-parent-id attribute:", button);
            return;
        }

        const parentCard = document.querySelector(`.card[data-item-id="${parentId}"]`);
        if (!parentCard) {
            console.error("Could not find parent card with ID:", parentId);
            return;
        }

        const parentLevel = parseInt(parentCard.dataset.level, 10);
        const newLevel = parentLevel + 1;
        if (newLevel > MAX_SUBTASK_LEVEL) {
            showAlert(`You can only create up to ${MAX_SUBTASK_LEVEL} levels of subtasks.`);
            return;
        }
        
        const newId = `new-${++newItemIdCounter}`;
        const newSubtaskHtml = generateTaskHtml(newId, parentId, newLevel);
        
        let subtaskList = parentCard.querySelector('.subtask-list');
        if (!subtaskList) {
            subtaskList = document.createElement('div');
            subtaskList.className = 'subtask-list';
            parentCard.querySelector('.card-body').appendChild(subtaskList);
            initSortable(subtaskList);
        }

        subtaskList.insertAdjacentHTML('beforeend', newSubtaskHtml);

        if (parentLevel > 0) {
            updateParentHours(parentCard);
        }
        updateRemainingHours();

        if (subtaskList.classList.contains('subtask-list-collapsed')) {
            const toggleBtn = parentCard.querySelector('.toggle-subtasks-btn');
            if (toggleBtn) handleMinimizeToggle(toggleBtn);
        }
    }

    function handleDeleteTask(button) {
        const cardToDelete = button.closest('.card');
        if (cardToDelete) {
            
            // --- CORRECTED LOGIC STARTS HERE ---
            const parentId = cardToDelete.dataset.parentItemId;
            let parentCard = null;
            if (parentId) {
                parentCard = document.querySelector(`.card[data-item-id="${parentId}"]`);
            }
            // --- CORRECTED LOGIC ENDS HERE ---

            const itemId = cardToDelete.dataset.itemId;
            if (!itemId.startsWith('new-')) {
                deletedItemIds.add(itemId);
            }
            
            cardToDelete.remove();

            if (parentCard) {
                updateParentHours(parentCard);
            }
            updateRemainingHours();
        }
    }

    function handleCompletionChange(checkbox) {
        const taskCard = checkbox.closest('.card');
        if (!taskCard) return;
        const isCompleted = checkbox.checked;
        applyCompletionStyles(taskCard, isCompleted);

        if (isCompleted) {
            propagateCompletionDownwards(taskCard.querySelector('.subtask-list'), true);
        } else {
            propagateUncompletionUpwards(taskCard);
        }
        updateRemainingHours();
    }

    function handleMinimizeToggle(button) {
        const taskCard = button.closest('.card');
        const taskOptions = taskCard.querySelector(':scope > .card-body > .task-options');
        const collapseIcon = button.querySelector('.collapse-icon');
        taskOptions.classList.toggle('task-options-minimized');
        const isMinimized = taskOptions.classList.contains('task-options-minimized');
        collapseIcon.innerHTML = isMinimized ? '&#9650;' : '&#9660;';

        if (isMinimized) {
            taskCard.querySelectorAll('.subtask-list .card').forEach(subtaskCard => {
                const subtaskOptions = subtaskCard.querySelector(':scope > .card-body > .task-options');
                if (subtaskOptions) subtaskOptions.classList.add('task-options-minimized');
                const subtaskCollapseIcon = subtaskCard.querySelector('.toggle-subtasks-btn .collapse-icon');
                if (subtaskCollapseIcon) subtaskCollapseIcon.innerHTML = '&#9650;';
            });
        }
    }
    
    // --- Calculation & Update Functions ---

    function updateParentHours(parentCard) {
        if (!parentCard) return;

        const parentHourInput = parentCard.querySelector(':scope > .card-body > .task-options input[id^="planned_hours_"]');
        if (!parentHourInput) return;

        let totalSubtaskHours = 0;
        const subtaskList = parentCard.querySelector(':scope > .card-body > .subtask-list');
        const hasSubtasks = subtaskList && subtaskList.querySelector(':scope > .card');

        if (hasSubtasks) {
            subtaskList.querySelectorAll(':scope > .card').forEach(subtask => {
                const subtaskHourInput = subtask.querySelector('input[id^="planned_hours_"]');
                if (subtaskHourInput) {
                    totalSubtaskHours += parseFloat(subtaskHourInput.value) || 0;
                }
            });
            parentHourInput.value = totalSubtaskHours.toFixed(1);
            parentHourInput.readOnly = true;
        } else {
            parentHourInput.readOnly = false;
        }

        // --- CORRECTED CASCADE LOGIC ---
        const grandParentId = parentCard.dataset.parentItemId;
        if (grandParentId) {
            const grandParentCard = document.querySelector(`.card[data-item-id="${grandParentId}"]`);
            // The level check is still a good safeguard here.
            if (grandParentCard && parseInt(grandParentCard.dataset.level, 10) > 0) {
                updateParentHours(grandParentCard);
            }
        }
    }

    function updateRemainingHours() {
        const displayElement = document.getElementById('remaining-hours-display');
        if (!displayElement) return;

        let totalHours = 0;
        let remainingHours = 0;
        
        // Get all task cards on the page (levels > 0)
        const allTaskCards = document.querySelectorAll('.card[data-level]:not([data-level="0"])');

        allTaskCards.forEach(card => {
            // A task's hours should only be counted if it's a "leaf" task (has no subtasks).
            // The hour value in a parent task is just a sum of its children, so we MUST ignore it
            // in this calculation to prevent double-counting.
            const hasSubtasks = card.querySelector('.subtask-list .card');

            if (!hasSubtasks) {
                const hourInput = card.querySelector('input[id^="planned_hours_"]');
                if (hourInput) {
                    const value = parseFloat(hourInput.value);
                    if (!isNaN(value)) {
                        // Add its hours to the project's true total
                        totalHours += value; 
                        
                        // If the task is NOT complete, add its hours to the remaining total
                        if (!card.classList.contains('completed-task')) {
                            remainingHours += value;
                        }
                    }
                }
            }
        });

        displayElement.textContent = `${remainingHours.toFixed(1)} hrs`;
        
        // The styling logic remains the same
        if (remainingHours <= 0 && totalHours > 0) {
            displayElement.classList.remove('text-warning');
            displayElement.classList.add('text-success');
        } else {
            displayElement.classList.remove('text-success');
            displayElement.classList.add('text-warning');
        }
    }

    // --- Data Collection & Submission ---

    function collectTaskData(container) {
        const items = [];
        container.querySelectorAll(':scope > .card').forEach((card, index) => {
            if (parseInt(card.dataset.level, 10) > 0) {
                const subtaskListContainer = card.querySelector('.subtask-list');
                items.push({
                    item_id: card.dataset.itemId,
                    parent_item_id: card.dataset.parentItemId || null,
                    name: card.querySelector(`input[id^="name_"]`).value,
                    description: card.querySelector(`textarea[id^="description_"]`).value,
                    due_date: card.querySelector(`input[id^="due_date_"]`).value || null,
                    is_completed: card.querySelector(`input[id^="is_completed_"]`).checked,
                    is_minimized: card.querySelector('.task-options').classList.contains('task-options-minimized'),
                    planned_hours: card.querySelector(`input[id^="planned_hours_"]`).value || null,
                    display_order: index,
                    subtasks: subtaskListContainer ? collectTaskData(subtaskListContainer) : []
                });
            }
        });
        return items;
    }

    // Made use of Gemini for this function, helped me debug an error where the parent task was misidentified.
    async function handleFormSubmit(event) {
        event.preventDefault();

        let isDataValid = true;
        document.querySelectorAll('.card[data-level]:not([data-level="0"]) input[type="date"]').forEach(dateInput => {
            const subtaskCard = dateInput.closest('.card');
            
            const parentId = subtaskCard.dataset.parentItemId;
            if (!parentId) return; 

            const parentCard = document.querySelector(`.card[data-item-id="${parentId}"]`);
            if (!parentCard) return;

            const parentDueDateInput = parentCard.querySelector(':scope > .card-body > .task-options input[type="date"]');

            if (parentDueDateInput && parentDueDateInput.value && dateInput.value && dateInput.value > parentDueDateInput.value) {
                const taskName = subtaskCard.querySelector('input[id^="name_"]').value || "Untitled Task";
                showAlert(`Validation Error: Task "${taskName}" cannot be due after its parent.`);
                isDataValid = false;
            }
        });

        if (!isDataValid) return;   

        const startContainer = document.querySelector('.card[data-level="0"] .subtask-list');
        const payload = {
            project_id: document.getElementById('project_id').value,
            tasks: startContainer ? collectTaskData(startContainer) : [],
            deleted_item_ids: Array.from(deletedItemIds)
        };

        console.log("SENDING PAYLOAD:", JSON.stringify(payload, null, 2));

        try {
            const response = await fetch('/save-tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (response.ok) {
                window.location.reload();
            } else {
                showAlert(`Failed to save tasks: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            showAlert('Error saving tasks. Please check your connection.');
        }
    }


    function attachEventListeners(container) {
        container.addEventListener('click', function(event) {
            const addBtn = event.target.closest('.add-subtask-btn');
            if (addBtn) handleAddSubtask(addBtn);

            const deleteBtn = event.target.closest('.delete-task-btn');
            if (deleteBtn) handleDeleteTask(deleteBtn);

            const toggleBtn = event.target.closest('.toggle-subtasks-btn');
            if (toggleBtn) handleMinimizeToggle(toggleBtn);
        });

        container.addEventListener('change', function(event) {
            if (event.target.matches('.completed-checkbox')) {
                handleCompletionChange(event.target);
            }
            if (event.target.matches('input[type="date"]')) {
                validateDueDate(event.target);
            }
        });

        container.addEventListener('input', function(event) {
            if (event.target.matches('input[id^="planned_hours_"]')) {
                const parentCard = event.target.closest('.subtask-list')?.closest('.card');
                if (parentCard && parseInt(parentCard.dataset.level, 10) > 0) {
                    updateParentHours(parentCard);
                }
                updateRemainingHours();
            }
        });
    }

    function generateTaskHtml(itemId, parentItemId, level) {
        const htmlId = itemId.replace(/[.-]/g, '_');
        const addBtn = level < MAX_SUBTASK_LEVEL ? `<button type="button" class="btn btn-sm btn-outline-primary add-subtask-btn" data-parent-id="${itemId}"><i class="fa-solid fa-plus"></i></button>` : '';
        return `
        <div class="card subtask-level-${level} mb-1" data-item-id="${itemId}" data-parent-item-id="${parentItemId}" data-level="${level}">
            <div class="card-body">
                <div class="task-header">
                    <span class="drag-handle"><i class="fa-solid fa-grip-vertical"></i></span>
                    <div class="form-floating flex-grow-1">
                        <input type="text" class="form-control" id="name_${htmlId}" name="name_${htmlId}" placeholder="Subtask Name">
                        <label for="name_${htmlId}">Subtask Name</label>
                    </div>
                    ${addBtn}
                    <button type="button" class="btn btn-sm btn-outline-secondary toggle-subtasks-btn"><span class="collapse-icon">&#9660;</span></button>
                    <button type="button" class="btn btn-sm btn-outline-danger delete-task-btn"><i class="fa-solid fa-trash"></i></button>
                </div>
                <div class="task-options">
                    <div class="d-flex flex-wrap align-items-center gap-2">
                        <div class="d-flex align-items-center gap-1" style="max-width: 200px;">
                            <label for="planned_hours_${htmlId}" class="form-label small mb-0 text-nowrap">Planned Hrs:</label>
                            <input type="number" min="0" step="0.1" class="form-control form-control-sm flex-grow-1" id="planned_hours_${htmlId}" name="planned_hours_${htmlId}" placeholder="0.0">
                        </div>
                        <div class="d-flex align-items-center gap-1" style="max-width: 200px;">
                            <label for="due_date_${htmlId}" class="form-label small mb-0 text-nowrap">Due Date:</label>
                            <input type="date" class="form-control form-control-sm flex-grow-1" id="due_date_${htmlId}" name="due_date_${htmlId}">
                        </div>
                        <div class="form-floating flex-grow-1 w-100">
                            <textarea class="form-control" placeholder="Description" id="description_${htmlId}" name="description_${htmlId}"></textarea>
                            <label for="description_${htmlId}">Description</label>
                        </div>
                        <div class="form-check mb-2">
                            <input type="checkbox" class="form-check-input completed-checkbox" id="is_completed_${htmlId}" name="is_completed_${htmlId}">
                            <label class="form-check-label" for="is_completed_${htmlId}">Completed</label>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
    }

    function initSortable(listEl) {
        new Sortable(listEl, {
            group: 'nested-tasks',
            animation: 150,
            handle: '.drag-handle',
            fallbackOnBody: true,
            swapThreshold: 0.65,
            onAdd: function (evt) {
                const item = evt.item; 

                const oldList = evt.from;
                const oldParentCard = oldList.closest('.card');

                const newList = evt.to;
                const newParentCard = newList.closest('.card');

                const newParentId = newParentCard ? newParentCard.dataset.itemId : '';
                item.dataset.parentItemId = newParentId;

                if (oldParentCard) {
                    updateParentHours(oldParentCard);
                }
                if (newParentCard && newParentCard !== oldParentCard) {
                    updateParentHours(newParentCard);
                }
            }
        });
    }

    function showAlert(message) {
        const alertBox = document.getElementById('alertMessage');
        alertBox.textContent = message;
        alertBox.style.display = 'block';
        alertBox.style.animation = 'none';
        void alertBox.offsetWidth;
        alertBox.style.animation = 'fadeOut 4s forwards';
    }

    function applyCompletionStyles(taskCard, isCompleted) {
        taskCard.classList.toggle('completed-task', isCompleted);
    }

    function propagateCompletionDownwards(subtaskListContainer, isCompleted) {
        if (!subtaskListContainer) return;
        subtaskListContainer.querySelectorAll(':scope > .card').forEach(subtaskCard => {
            const checkbox = subtaskCard.querySelector('.completed-checkbox');
            if (checkbox && checkbox.checked !== isCompleted) {
                checkbox.checked = isCompleted;
                applyCompletionStyles(subtaskCard, isCompleted);
            }
            const nestedSubtaskList = subtaskCard.querySelector('.subtask-list');
            if (nestedSubtaskList) {
                propagateCompletionDownwards(nestedSubtaskList, isCompleted);
            }
        });
    }

    // Gemini helped generate this feature.
    function propagateUncompletionUpwards(currentTaskCard) {
        const parentId = currentTaskCard.dataset.parentItemId;
        if (!parentId) return;

        const parentCard = document.querySelector(`.card[data-item-id="${parentId}"]`);
        if (!parentCard) return;

        const parentCheckbox = parentCard.querySelector('.completed-checkbox');
        if (parentCheckbox && parentCheckbox.checked) {
            parentCheckbox.checked = false;
            applyCompletionStyles(parentCard, false);
            propagateUncompletionUpwards(parentCard);
        }
    }
    
    function validateDueDate(dateInput) {
        const subtaskCard = dateInput.closest('.card');
        if (!subtaskCard) return;

        const parentId = subtaskCard.dataset.parentItemId;
        if (!parentId) {
            return;
        }

        const parentCard = document.querySelector(`.card[data-item-id="${parentId}"]`);
        if (!parentCard) return;
        const parentDueDateInput = parentCard.querySelector(':scope > .card-body > .task-options input[type="date"]');

        if (!parentDueDateInput || !parentDueDateInput.value) {
            return;
        }
        
        const parentDueDateStr = parentDueDateInput.value;
        const subtaskDueDateStr = dateInput.value;

        if (subtaskDueDateStr && subtaskDueDateStr > parentDueDateStr) {
            showAlert("A subtask's due date cannot be later than its parent's due date.");
            dateInput.value = ''; // Reset the invalid date
        }
    }


    // Used Gemini to restructure code into this section.
    // =========================================================================
    // INITIALIZATION
    // =========================================================================

    // Attach all delegated event listeners to the document.
    attachEventListeners(document);
    document.getElementById('task-manager-form').addEventListener('submit', handleFormSubmit);

    // Initialize UI components for existing tasks.
    document.querySelectorAll('.task-list, .subtask-list').forEach(initSortable);
    document.querySelectorAll('.completed-checkbox').forEach(checkbox => {
        if (checkbox.checked) {
            applyCompletionStyles(checkbox.closest('.card'), true);
        }
    });

    // Run initial calculations for readonly states and sums on page load.
    const allCards = Array.from(document.querySelectorAll('.card[data-item-id]'));
    allCards.sort((a, b) => parseInt(b.dataset.level) - parseInt(a.dataset.level));
    
    const updatedParents = new Set();
    allCards.forEach(card => {
        const parentId = card.dataset.parentItemId;
        if (parentId) {
            const parentCard = document.querySelector(`.card[data-item-id="${parentId}"]`);
            if (parentCard && !updatedParents.has(parentCard)) {
                updateParentHours(parentCard);
                updatedParents.add(parentCard);
            }
        }
    });

    // Set the initial project time display after all calculations are done.
    updateRemainingHours();

});