
document.addEventListener('DOMContentLoaded', function() {
    let newItemIdCounter = 0;
    const deletedItemIds = new Set();
    const MAX_SUBTASK_LEVEL = 6;

    attachEventListeners(document);

    document.querySelectorAll('.completed-checkbox').forEach(checkbox => {
        const taskCard = checkbox.closest('.card');
        if (taskCard && checkbox.checked) {
            applyCompletionStyles(taskCard, true);
        }
    });

    document.querySelectorAll('.task-list, .subtask-list').forEach(initSortable);
    
    const taskManagerForm = document.getElementById('task-manager-form');
    taskManagerForm.addEventListener('submit', handleFormSubmit);
    
    updateRemainingHours();

    function initSortable(listEl) {
        new Sortable(listEl, {
            group: 'nested-tasks',
            animation: 150,
            handle: '.drag-handle',
            fallbackOnBody: true,
            swapThreshold: 0.65,
            onAdd: function (evt) {
                const item = evt.item;
                const newParentCard = item.closest('.card:not([data-item-id="' + item.dataset.itemId + '"])');
                const newParentId = newParentCard ? newParentCard.dataset.itemId : '';
                item.dataset.parentItemId = newParentId;
            }
        });
    }

    function collectTaskData(container) {
    const items = [];
    container.querySelectorAll(':scope > .card').forEach((card, index) => {
        // The level check is now implicitly handled by where we start the call.
        // But keeping it adds robustness in case the root card is ever passed in.
        const level = parseInt(card.dataset.level, 10);
        if (level > 0) {
            const itemId = card.dataset.itemId;
            // This is the critical line that needs the correct context
            const parentItemId = card.dataset.parentItemId || null; 

            const name = card.querySelector(`input[id^="name_"]`).value;
            const description = card.querySelector(`textarea[id^="description_"]`).value;
            const dueDate = card.querySelector(`input[id^="due_date_"]`).value;
            const isCompleted = card.querySelector(`input[id^="is_completed_"]`).checked;
            const plannedHours = card.querySelector(`input[id^="planned_hours_"]`).value;
            const isMinimized = card.querySelector('.task-options').classList.contains('task-options-minimized');
            
            let subtasks = [];
            const subtaskListContainer = card.querySelector('.subtask-list');
            if (subtaskListContainer) {
                // The recursive call remains the same
                subtasks = collectTaskData(subtaskListContainer);
            }

            const itemObject = {
                item_id: itemId,
                parent_item_id: parentItemId,
                name: name,
                description: description,
                due_date: dueDate || null,
                is_completed: isCompleted,
                is_minimized: isMinimized,
                planned_hours: plannedHours || null,
                display_order: index,
                subtasks: subtasks
            };
            items.push(itemObject);
        }
    });
    // The function now only has one return path.
    return items;
    }

    async function handleFormSubmit(event) {
        event.preventDefault(); // Always prevent the default submission first

        let isDataValid = true;
        // Find all date inputs in the form to validate them
        document.querySelectorAll('.card[data-level]:not([data-level="0"]) input[type="date"]').forEach(dateInput => {
            const subtaskCard = dateInput.closest('.card');
            const parentCard = subtaskCard.closest('.subtask-list')?.closest('.card');
            const parentDueDateInput = parentCard?.querySelector('input[type="date"]');

            // Check for the invalid condition: parent has a due date AND the subtask's due date is later.
            if (parentDueDateInput && parentDueDateInput.value && dateInput.value) {
                if (dateInput.value > parentDueDateInput.value) {
                    const taskName = subtaskCard.querySelector('input[id^="name_"]').value || "Untitled Task";
                    showAlert(`Validation Error: Task "${taskName}" cannot be due after its parent.`);
                    isDataValid = false; // Mark data as invalid
                }
            }
        });

        // If the validation loop found any errors, STOP the submission.
        if (!isDataValid) {
            return;
        }

        // --- save logic  ---
        const projectId = document.getElementById('project_id').value;

        // This is the actual starting point for the tasks we want to save.
        const startContainer = document.querySelector('.card[data-level="0"] .subtask-list');

        // Only collect data if the container exists.
        const tasksData = startContainer ? collectTaskData(startContainer) : [];
   
        const payload = {
            project_id: projectId,
            tasks: tasksData,
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
            const deleteBtn = event.target.closest('.delete-task-btn');
            const toggleBtn = event.target.closest('.toggle-subtasks-btn');
            if (addBtn) handleAddSubtask(addBtn);
            if (addBtn) updateProjectRemainingTime();
            if (deleteBtn) handleDeleteTask(deleteBtn);
            if (deleteBtn) updateProjectRemainingTime();
            if (toggleBtn) handleMinimizeToggle(toggleBtn);
            
        });

        container.addEventListener('change', function(event) {
            const checkbox = event.target.closest('.completed-checkbox');
            if (checkbox) handleCompletionChange(checkbox);

            // Correctly target the due date input
            if (event.target.matches('input[type="date"]')) {
                validateDueDate(event.target);
            }
        });

        container.addEventListener('input', function(event) {
            if (event.target.matches('input[id^="planned_hours_"]')) {
                updateRemainingHours();
            }
        });

        container.addEventListener('input', function(event) {
            if (event.target.matches('input[id^="planned_hours_"]')) {
                const parentCard = event.target.closest('.subtask-list')?.closest('.card');
                updateParentHours(parentCard); // Trigger the new summation logic
                updateRemainingHours();      // Update the project-wide total
            }   
        });
    }

    function handleAddSubtask(button) {
    // 1. Get the parent ID directly from the button's data attribute. This is foolproof.
    const parentId = button.dataset.parentId;
    if (!parentId) {
        console.error("Button is missing a data-parent-id attribute:", button);
        return;
    }

    // 2. Find the parent card using the foolproof ID.
    // Note the use of quotes around the ID in the selector for compatibility with IDs like 'new-1'.
    const parentCard = document.querySelector(`.card[data-item-id="${parentId}"]`);
    if (!parentCard) {
        console.error("Could not find parent card with ID:", parentId);
        return;
    }

    // 3. The rest of the logic remains the same, but is now guaranteed to work.
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
        const newSubtaskListDiv = document.createElement('div');
        newSubtaskListDiv.className = 'subtask-list';
        parentCard.querySelector('.card-body').appendChild(newSubtaskListDiv);
        subtaskList = newSubtaskListDiv;
        initSortable(subtaskList);
    }

    subtaskList.insertAdjacentHTML('beforeend', newSubtaskHtml);

    updateParentHours(parentCard);
    updateRemainingHours();

    if (subtaskList.classList.contains('subtask-list-collapsed')) {
        const toggleBtn = parentCard.querySelector('.toggle-subtasks-btn');
        if (toggleBtn) handleMinimizeToggle(toggleBtn);
    }
}

    function handleDeleteTask(button) {
        const cardToDelete = button.closest('.card');
        if (cardToDelete) {
            const parentCard = cardToDelete.closest('.subtask-list')?.closest('.card');
            const itemId = cardToDelete.dataset.itemId;
            if (!itemId.startsWith('new-')) {
                deletedItemIds.add(itemId);
            }
            
            cardToDelete.remove(); // Remove the element from the DOM

            if (parentCard) {
                updateParentHours(parentCard); // Recalculate hours for the parent
            }
            updateRemainingHours(); // Update the project-wide total
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
    
    /**
     * This functioncascades minimization to all descendant subtasks.
     */
    function handleMinimizeToggle(button) {
        const taskCard = button.closest('.card');
        const taskOptions = taskCard.querySelector(':scope > .card-body > .task-options');
        const collapseIcon = button.querySelector('.collapse-icon');

        // Toggle the main task's options visibility
        taskOptions.classList.toggle('task-options-minimized');
        const isMinimized = taskOptions.classList.contains('task-options-minimized');

        // Update the icon for the main task
        collapseIcon.innerHTML = isMinimized ? '&#9650;' : '&#9660;';

        // When the parent is minimized, cascade the minimization to all descendants.
        if (isMinimized) {
            // This selector finds ALL nested .card elements, ensuring the effect cascades.
            const allDescendantSubtasks = taskCard.querySelectorAll('.subtask-list .card');

            allDescendantSubtasks.forEach(subtaskCard => {
                const subtaskOptions = subtaskCard.querySelector(':scope > .card-body > .task-options');
                const subtaskCollapseIcon = subtaskCard.querySelector('.toggle-subtasks-btn .collapse-icon');

                if (subtaskOptions) {
                    subtaskOptions.classList.add('task-options-minimized');
                }
                if (subtaskCollapseIcon) {
                    subtaskCollapseIcon.innerHTML = '&#9650;';
                }
            });
        }
    }

    function generateTaskHtml(itemId, parentItemId, level) {
        const htmlId = itemId.replace(/[.-]/g, '_');
        
        // Added data-parent-id to the button, using the ID of the task it belongs to.
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

    function updateRemainingHours() {
        const displayElement = document.getElementById('remaining-hours-display');
        if (!displayElement) return;
        let totalHours = 0;
        let completedHours = 0;
        const hourInputs = document.querySelectorAll('.card[data-level]:not([data-level="0"]) input[id^="planned_hours_"]');
        hourInputs.forEach(input => {
            const value = parseFloat(input.value);
            if (!isNaN(value)) {
                totalHours += value;
                const taskCard = input.closest('.card');
                if (taskCard && taskCard.classList.contains('completed-task')) {
                    completedHours += value;
                }
            }
        });
        const remainingHours = totalHours - completedHours;
        displayElement.textContent = `${remainingHours.toFixed(1)}hrs`;
        if (remainingHours <= 0 && totalHours > 0) {
            displayElement.classList.remove('text-warning');
            displayElement.classList.add('text-success');
        } else {
            displayElement.classList.remove('text-success');
            displayElement.classList.add('text-warning');
        }
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
        if (isCompleted) {
            taskCard.classList.add('completed-task');
        } else {
            taskCard.classList.remove('completed-task');
        }
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

    function propagateUncompletionUpwards(currentTaskCard) {
        let parentCard = currentTaskCard.closest('.subtask-list')?.closest('.card');
        if (parentCard) {
            const parentCheckbox = parentCard.querySelector('.completed-checkbox');
            if (parentCheckbox && parentCheckbox.checked) {
                parentCheckbox.checked = false;
                applyCompletionStyles(parentCard, false);
                propagateUncompletionUpwards(parentCard);
            }
        }
    }

    /**
     * Checks a subtask's due date is not earlier than its parent's.
     * @param {HTMLInputElement} dateInput The date input element that was changed.
     */
    function validateDueDate(dateInput) {
        const subtaskCard = dateInput.closest('.card');
        if (!subtaskCard) return;

        // Find the parent card by navigating up the DOM tree
        const parentCard = subtaskCard.closest('.subtask-list')?.closest('.card');
        if (!parentCard) {
            // This subtask has no parent in the current structure, so no validation needed
            return;
        }

        // Find the parent's due date input
        const parentDueDateInput = parentCard.querySelector('input[type="date"]');
        if (!parentDueDateInput || !parentDueDateInput.value) {
            // Parent has no due date set, so we can't validate against it
            return;
        }
        
        const parentDueDateStr = parentDueDateInput.value;
        const subtaskDueDateStr = dateInput.value;

        // Only compare if the subtask has a date
        if (subtaskDueDateStr && subtaskDueDateStr > parentDueDateStr) {
            showAlert("A subtask's due date cannot be later than its parent's due date.");
            dateInput.value = ''; // Reset the invalid date
        }
    }


    /**
     * Calculates the sum of all direct subtasks' hours and updates the parent task.
     * This function is designed to be called recursively to cascade up the hierarchy.
     * @param {HTMLElement} parentCard The parent card element whose hours need updating.
     */
    function updateParentHours(parentCard) {
        if (!parentCard) return;

        const parentHourInput = parentCard.querySelector('input[id^="planned_hours_"]');
        if (!parentHourInput) return;

        let totalSubtaskHours = 0;
        const subtaskList = parentCard.querySelector(':scope > .card-body > .subtask-list');

        if (subtaskList && subtaskList.hasChildNodes()) {
            const directSubtasks = subtaskList.querySelectorAll(':scope > .card');
            directSubtasks.forEach(subtask => {
                const subtaskHourInput = subtask.querySelector('input[id^="planned_hours_"]');
                if (subtaskHourInput) {
                    totalSubtaskHours += parseFloat(subtaskHourInput.value) || 0;
                }
            });

            // Parent's hours are the sum of its children's hours
            parentHourInput.value = totalSubtaskHours.toFixed(1);
            parentHourInput.readOnly = true; // Ensure it's read-only
        } else {
            // If there are no subtasks, the field should be editable
            parentHourInput.readOnly = false;
        }

        // --- Cascade Upwards ---
        // Find the grandparent and trigger its update
        const grandParentCard = parentCard.closest('.subtask-list')?.closest('.card');
        if (grandParentCard) {
            updateParentHours(grandParentCard);
        }
    }
});


/**
 * Calculates and updates the total planned hours for the Level 0 project task.
 * This function should be called after all subtask hours have been updated.
 */
function updateProjectRemainingTime() {
    let totalProjectHours = 0;
    // Select all direct children of the main task-list container that are cards
    // These should be your Level 0 tasks (though in your template, there's only one project card at level 0).
    // Or, more accurately, sum all Level 1 tasks directly.
    const level1Tasks = document.querySelectorAll('.task-list > .card[data-level="0"] > .card-body > .subtask-list > .card[data-level="1"]');

    level1Tasks.forEach(taskCard => {
        const plannedHoursInput = taskCard.querySelector('input[id^="planned_hours_"]');
        if (plannedHoursInput) {
            totalProjectHours += parseFloat(plannedHoursInput.value) || 0;
        }
    });

    const remainingHoursDisplay = document.getElementById('remaining-hours-display');
    if (remainingHoursDisplay) {
        // You might need to subtract 'completed' hours here if you track them separately
        // For now, it's just the sum of all planned hours.
        remainingHoursDisplay.textContent = `${totalProjectHours.toFixed(1)} hrs`;
    }
}

// Ensure this is called after your updateParentHours has finished its cascade
document.addEventListener('DOMContentLoaded', () => {
    // Existing logic to trigger updateParentHours on load (important for initial sums)
    updateProjectRemainingTime()
    const allCardsElements = document.querySelectorAll('.card[data-item-id]');
    const sortedCardsByLevel = Array.from(allCardsElements).sort((a, b) => {
        const levelA = parseInt(a.dataset.level, 10);
        const levelB = parseInt(b.dataset.level, 10);
        return levelB - levelA; // Deepest level first
    });

    const updatedParents = new Set(); 

    sortedCardsByLevel.forEach(card => {
        const parentCard = card.closest('.subtask-list')?.closest('.card');
        if (parentCard && !updatedParents.has(parentCard)) {
            updateParentHours(parentCard);
            updatedParents.add(parentCard);
        } else if (parseInt(card.dataset.level, 10) === 0 && !updatedParents.has(card)) {
            // Ensure the level 0 card also gets its 'subtask sum' (even if it's not displayed there)
            // if it has subtasks, this will make its input readonly.
            // updateParentHours(card); // You might not need to call this directly on level 0 if you are handling total project sum separately
            // Instead, just ensure the level 1 cards are correctly summed up to their level 0 parent.
        }
    });

    // NOW, after all individual task/subtask sums have potentially propagated upwards,
    // calculate the total remaining time for the project.
    updateProjectRemainingTime();

    // Add event listeners for input changes
    document.querySelectorAll('input[id^="planned_hours_"]').forEach(input => {
        input.addEventListener('input', (event) => {
            const changedInput = event.target;
            const parentCard = changedInput.closest('.card');
            
            if (parentCard && !changedInput.readOnly) { // Only process if the field is editable (i.e., it's a leaf task)
                const grandParentCard = parentCard.closest('.subtask-list')?.closest('.card');
                if (grandParentCard) {
                    updateParentHours(grandParentCard); // Cascade sum upwards
                }
                // After any individual task's hours change, update the project total.
                updateProjectRemainingTime();
            }
        });
    });
});