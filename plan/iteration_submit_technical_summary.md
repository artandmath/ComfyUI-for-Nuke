# ComfyUI Iterations - Technical Implementation Summary

## Core Concept
Extend the existing `submit()` function to support X iterations by modeling after the proven `animation_submit()` pattern.

## Key Code Changes Required

### 1. Add Global Flag for Message Suppression
```python
# At module level in run.py
iteration_mode = False
```

### 2. Modify Submit Function Signature
```python
def submit(run_node=None, animation=None, iterations=None, success_callback=None):
    # iterations = [current_iteration, total_iterations, iteration_callback, finished_callback, progress_task]
```

### 3. Add Message Suppression Logic
Replace `nuke.message()` calls with conditional checks:
```python
# Lines ~311, ~320, ~370 in run.py
if not iteration_mode:
    nuke.message(error_message)

# Also modify connection.py GET(), check_connection(), POST() functions
```

### 4. Add Iteration Logic in progress_finished()
```python
def progress_finished(n):
    filename = get_filename(run_node)
    
    if iterations:
        current_iteration, total_iterations, iteration_callback, finished_callback, iteration_task = iterations
        
        # Backup result
        try:
            from .read_media import save_image_backup
            save_image_backup()
        except:
            pass  # Don't fail if backup fails during iterations
            
        iteration_callback(current_iteration, filename)
        
        next_iteration = current_iteration + 1
        if next_iteration > total_iterations:
            finished_callback()
            return
            
        # Continue to next iteration
        submit(run_node, iterations=(next_iteration, total_iterations, iteration_callback, finished_callback, iteration_task))
        return
    
    # ... existing animation and normal code ...
```

### 5. Create Entry Point Function
```python
def iteration_submit(iteration_count):
    """Entry point for X iterations of ComfyUI runs"""
    run_node = nuke.thisNode()
    
    if iteration_count <= 1:
        submit()
        return
    
    iteration_task = [nuke.ProgressTask(f'ComfyUI Iterations: 0/{iteration_count}')]
    iteration_results = []
    
    def iteration_callback(iteration_num, filename):
        iteration_results.append((iteration_num, filename))
        iteration_task[0].setMessage(f'ComfyUI Iterations: {iteration_num}/{iteration_count}')
        
    def finished_callback():
        global iteration_mode
        iteration_mode = False
        del iteration_task[0]
        nuke.message(f'Completed {iteration_count} iterations!')
    
    global iteration_mode
    iteration_mode = True
    
    submit(run_node, iterations=(1, iteration_count, iteration_callback, finished_callback, iteration_task))
```

## Files to Modify

### src/run.py
- Add `iteration_mode` global variable
- Modify `submit()` function signature 
- Add iteration logic to `progress_finished()`
- Add `iteration_submit()` function
- Suppress messages when `iteration_mode = True`

### src/connection.py  
- Modify `GET()`, `check_connection()`, `POST()` to check iteration_mode
- Suppress error messages during iterations

## Usage Pattern
```python
# From WAN gizmo button
nuke.thisNode().parent().knob('update_frames').execute()

if nuke.thisNode().parent().knob('enable_iterations').value():
    iteration_count = int(nuke.thisNode().parent().knob('iteration_count').value())
    comfyui.run.iteration_submit(iteration_count)  # Pass iteration count as parameter
elif nuke.thisNode().knob('force_animation').value():
    comfyui.run.animation_submit()  
else:
    comfyui.run.submit()
```

## Critical Implementation Notes

1. **Backward Compatibility**: All new parameters are optional - existing code continues to work
2. **Error Handling**: Suppress UI dialogs during iterations but maintain error logging
3. **Cancellation**: User can cancel via progress dialog, same as animations
4. **Backup Integration**: Automatic backup after each iteration using existing `save_image_backup()`
5. **State Management**: Use global flag pattern already established in codebase
6. **Threading**: Reuse existing WebSocket threading architecture

## Testing Strategy
1. Test single iteration (should behave identically to normal submit)
2. Test multiple iterations with cancellation
3. Test error scenarios during iterations  
4. Verify backup creation between iterations
5. Test UI integration with different iteration counts 