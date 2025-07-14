# ComfyUI X Iterations Implementation Plan

## Analysis of Current Codebase

### Current Submit Function Architecture
The existing `submit()` function in `src/run.py` has these key characteristics:

1. **Global State Management**: Uses `nuke.comfyui_running` flag to prevent concurrent executions
2. **Threading Architecture**: Uses WebSocket connection with separate threads for progress tracking
3. **Error Handling**: Multiple `nuke.message()` calls that interrupt user workflow
4. **Progress Tracking**: Uses `nuke.ProgressTask` with cancellation support
5. **Sequential Pattern**: Already implemented in `animation_submit()` for frame-by-frame processing

### Current Sequential Processing Pattern (Animation Submit)
The `animation_submit()` function already demonstrates how to handle sequential operations:
- Recursive submission with state tracking
- Progress management across iterations  
- Callback-based completion handling
- Cancellation support

### Key Components for Iteration Feature
1. **Backup System**: `save_image_backup()` exists in `read_media.py`
2. **Error Suppression**: Need to bypass `nuke.message()` calls during iterations
3. **State Management**: Track iteration count and progress
4. **Threading**: Maintain current architecture while adding iteration logic

## Implementation Strategy

We will extend the existing `submit()` function to support an `iterations` parameter, similar to how the `animation` parameter works.

**Advantages:**
- Reuses existing threading and WebSocket architecture
- Maintains compatibility with current UI code
- Leverages proven sequential processing pattern from animations
- Minimal code duplication

**Implementation Details:**
```python
def submit(run_node=None, animation=None, iterations=None, success_callback=None):
    # iterations = [current_iteration, total_iterations, iteration_callback, finished_callback, progress_task]
```

## Detailed Implementation Plan

### 1. Function Signature Modification
```python
def submit(run_node=None, animation=None, iterations=None, success_callback=None, suppress_messages=False):
```

### 2. Error Message Suppression
Create a context manager or global flag to suppress `nuke.message()` calls during iterations:

```python
# Add global variable
iteration_mode = False

# Modify error handling sections to check this flag
if not iteration_mode:
    nuke.message(error)
```

**Locations to modify:**
- Line ~311: `nuke.executeInMainThread(nuke.message, args=(error))`
- Line ~320: `nuke.executeInMainThread(nuke.message, args=('error: ' + str(error)))`  
- Line ~370: `nuke.message(error)`
- Connection module error messages

### 3. Iteration Logic Implementation
Model after the animation processing pattern:

```python
if iterations:
    current_iteration, total_iterations, iteration_callback, finished_callback, iteration_task = iterations
    
    # Progress calculation
    progress = int(current_iteration * 100 / total_iterations)
    iteration_task[0].setProgress(progress)
    iteration_task[0].setMessage(f'Iteration: {current_iteration}/{total_iterations}')
```

### 4. Backup Integration
Add backup call in the success handling:

```python
def progress_finished(n):
    filename = get_filename(run_node)
    
    if iterations:
        current_iteration, total_iterations, iteration_callback, finished_callback, iteration_task = iterations
        
        # Backup current result
        from .read_media import save_image_backup
        save_image_backup()
        
        # Call iteration callback
        iteration_callback(current_iteration, filename)
        
        # Check for completion
        next_iteration = current_iteration + 1
        if next_iteration > total_iterations:
            finished_callback()
            return
            
        # Continue to next iteration
        submit(run_node, iterations=(next_iteration, total_iterations, iteration_callback, finished_callback, iteration_task), suppress_messages=True)
        return
```

### 5. New Entry Point Function
Create a new function that initiates the iteration process:

```python
def iteration_submit():
    """Entry point for X iterations of ComfyUI runs"""
    run_node = nuke.thisNode()
    
    # Get iteration count from UI (could be a knob on the gizmo)
    iteration_count = run_node.parent().knob('iteration_count').value()
    
    if iteration_count <= 1:
        # Fall back to regular submit
        submit()
        return
    
    # Create progress task for iterations
    iteration_task = [nuke.ProgressTask(f'Running {iteration_count} ComfyUI iterations...')]
    iteration_results = []
    
    def iteration_callback(iteration_num, filename):
        iteration_results.append((iteration_num, filename))
        
    def finished_callback():
        del iteration_task[0]
        # Optional: Create read nodes for all iterations or just the last one
        nuke.message(f'Completed {iteration_count} iterations successfully!')
    
    # Start iteration process
    global iteration_mode
    iteration_mode = True
    
    submit(run_node, iterations=(1, iteration_count, iteration_callback, finished_callback, iteration_task), suppress_messages=True)
```

## Integration Points

### UI Integration
The function would be called from the WAN gizmo like this:
```python
nuke.thisNode().parent().knob('update_frames').execute()

# Check if iterations mode is enabled
if nuke.thisNode().parent().knob('enable_iterations').value():
    comfyui.run.iteration_submit()
elif nuke.thisNode().knob('force_animation').value():
    comfyui.run.animation_submit()
else:
    comfyui.run.submit()
```

### Required UI Elements
Add to the gizmo:
- `iteration_count` (integer knob): Number of iterations to run
- `enable_iterations` (boolean knob): Toggle iteration mode

## Risk Assessment

### Low Risk
- Function signature change is backward compatible (new parameters are optional)
- Message suppression uses existing patterns
- Leverages proven animation architecture

### Medium Risk  
- Global state management for message suppression
- Threading complexity with iteration callbacks
- Backup system interaction

### Mitigation Strategies
1. **Thorough Testing**: Test with various iteration counts and cancellation scenarios
2. **Fallback Behavior**: Ensure single iterations work identically to original submit
3. **Error Recovery**: Proper cleanup if iterations are cancelled mid-process
4. **Progress Tracking**: Clear feedback to user about current iteration status

## Implementation Timeline

1. **Phase 1**: Add iteration parameter and basic structure (2-3 hours)
2. **Phase 2**: Implement message suppression mechanism (1-2 hours) 
3. **Phase 3**: Add backup integration and iteration callbacks (2-3 hours)
4. **Phase 4**: Create entry point function and UI integration (1-2 hours)
5. **Phase 5**: Testing and refinement (3-4 hours)

**Total Estimated Time**: 9-14 hours

## Conclusion

This implementation leverages the existing animation processing pattern to create a robust iteration system. The key insight is that the codebase already has the infrastructure for sequential processing - we just need to adapt it for iterations instead of frames.

The approach minimizes code changes while maintaining compatibility and reusing proven patterns. The message suppression system ensures a smooth user experience during multi-iteration runs. 