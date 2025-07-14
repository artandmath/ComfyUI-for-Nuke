# ComfyUI Iterations Implementation - TODO List

## Phase 1: Core Infrastructure Setup (2-3 hours)

### 1.1 Add Global State Management
- [ ] **Task**: Add `iteration_mode` global variable to `src/run.py`
  - **Location**: After existing imports, near line 20
  - **Code**: `iteration_mode = False`
  - **Test**: Variable exists and can be imported

### 1.2 Modify Submit Function Signature
- [ ] **Task**: Update `submit()` function signature in `src/run.py`
  - **Location**: Line ~158 (current function definition)
  - **Change**: `def submit(run_node=None, animation=None, success_callback=None):`
  - **To**: `def submit(run_node=None, animation=None, iterations=None, success_callback=None):`
  - **Test**: Function accepts new parameter without breaking existing calls

### 1.3 Add Basic Iteration Parameter Handling
- [ ] **Task**: Add iteration parameter unpacking in submit function
  - **Location**: After animation parameter handling (~line 183)
  - **Code**: 
    ```python
    if iterations:
        current_iteration, total_iterations, iteration_callback, finished_callback, iteration_task = iterations
    ```
  - **Test**: Function handles iterations parameter without errors

## Phase 2: Message Suppression System (1-2 hours)

### 2.1 Suppress Messages in run.py
- [ ] **Task**: Modify error message in WebSocket on_message handler
  - **Location**: Line ~311 `nuke.executeInMainThread(nuke.message, args=(error))`
  - **Change**: Add condition `if not iteration_mode:`
  - **Test**: Messages suppressed when iteration_mode=True

- [ ] **Task**: Modify error message in WebSocket on_error handler  
  - **Location**: Line ~320 `nuke.executeInMainThread(nuke.message, args=('error: ' + str(error)))`
  - **Change**: Add condition `if not iteration_mode:`
  - **Test**: Messages suppressed when iteration_mode=True

- [ ] **Task**: Modify error message in main submit function
  - **Location**: Line ~370 `nuke.message(error)`
  - **Change**: Add condition `if not iteration_mode:`
  - **Test**: Messages suppressed when iteration_mode=True

### 2.2 Suppress Messages in connection.py
- [ ] **Task**: Import iteration_mode flag in connection.py
  - **Location**: Top of file after imports
  - **Code**: `from .run import iteration_mode`
  - **Test**: Import works without circular dependency issues

- [ ] **Task**: Modify GET() function error message
  - **Location**: Line ~23 `nuke.message('Error connecting to server...')`
  - **Change**: Add condition `if not iteration_mode:`
  - **Test**: Connection errors suppressed during iterations

- [ ] **Task**: Modify check_connection() function error message  
  - **Location**: Line ~31 `nuke.message('Error connecting to server...')`
  - **Change**: Add condition `if not iteration_mode:`
  - **Test**: Connection check errors suppressed during iterations

- [ ] **Task**: Modify POST() function error message
  - **Location**: Line ~58 `nuke.message(traceback.format_exc())`
  - **Change**: Add condition `if not iteration_mode:`
  - **Test**: POST errors suppressed during iterations

## Phase 3: Iteration Logic Implementation (2-3 hours)

### 3.1 Add Iteration Handling in progress_finished()
- [ ] **Task**: Locate progress_finished function in submit()
  - **Location**: Line ~332 (nested function definition)
  - **Action**: Add iteration logic before existing animation logic

- [ ] **Task**: Add iteration completion logic
  - **Location**: Start of progress_finished() function
  - **Code**:
    ```python
    if iterations:
        current_iteration, total_iterations, iteration_callback, finished_callback, iteration_task = iterations
        
        # Backup current result
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
    ```
  - **Test**: Single iteration progresses to next iteration correctly

### 3.2 Add Iteration Progress Tracking  
- [ ] **Task**: Add progress updates in WebSocket handlers
  - **Location**: In on_message handler for 'progress' type (~line 274)
  - **Code**: Update iteration progress task if iterations active
  - **Test**: Progress dialog shows correct iteration progress

## Phase 4: Entry Point Function (1-2 hours)

### 4.1 Create iteration_submit() Function
- [ ] **Task**: Add iteration_submit function to run.py
  - **Location**: After submit() function definition
  - **Code**:
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
            nuke.message(f'Completed {iteration_count} iterations successfully!')
        
        global iteration_mode
        iteration_mode = True
        
        submit(run_node, iterations=(1, iteration_count, iteration_callback, finished_callback, iteration_task))
    ```
  - **Test**: Function exists and can be called

### 4.2 Usage Pattern (Updated)
- [ ] **Task**: Update integration code in WAN gizmo
  - **Location**: In WAN gizmo button code
  - **Code**: 
    ```python
    nuke.thisNode().parent().knob('update_frames').execute()

    if nuke.thisNode().parent().knob('enable_iterations').value():
        iteration_count = int(nuke.thisNode().parent().knob('iteration_count').value())
        comfyui.run.iteration_submit(iteration_count)  # Pass iteration count as parameter
    elif nuke.thisNode().knob('force_animation').value():
        comfyui.run.animation_submit()
    else:
        comfyui.run.submit()
    ```
  - **Test**: Integration works with parameterized function call

## Phase 5: Testing & Validation (3-4 hours)

### 5.1 Unit Testing
- [ ] **Task**: Test single iteration mode
  - **Test**: `iteration_submit(1)` behaves like normal submit()
  - **Expected**: Same behavior as regular submit

- [ ] **Task**: Test multiple iterations mode  
  - **Test**: `iteration_submit(3)` with iteration_count=3
  - **Expected**: 3 sequential ComfyUI runs with backups

- [ ] **Task**: Test message suppression
  - **Test**: Trigger error during iteration mode
  - **Expected**: No nuke.message dialogs appear

### 5.2 Integration Testing  
- [ ] **Task**: Test cancellation during iterations
  - **Test**: Cancel progress dialog during multi-iteration run
  - **Expected**: Clean cancellation, iteration_mode reset to False

- [ ] **Task**: Test backup creation
  - **Test**: Run multiple iterations and verify backup nodes created
  - **Expected**: Backup read nodes created after each iteration

- [ ] **Task**: Test error recovery
  - **Test**: Simulate ComfyUI error during iteration 2 of 5
  - **Expected**: Proper cleanup, iteration_mode reset, user informed

### 5.3 Backward Compatibility Testing
- [ ] **Task**: Test existing animation_submit() function
  - **Test**: Ensure animation workflow still works
  - **Expected**: No regression in animation functionality

- [ ] **Task**: Test existing submit() function
  - **Test**: Ensure regular submit workflow still works  
  - **Expected**: No regression in normal submit functionality

## Phase 6: Documentation & Cleanup (1 hour)

### 6.1 Code Documentation
- [ ] **Task**: Add docstrings to iteration_submit() function
- [ ] **Task**: Add inline comments explaining iteration logic
- [ ] **Task**: Update any relevant README or documentation

### 6.2 Final Cleanup
- [ ] **Task**: Remove any debug print statements
- [ ] **Task**: Ensure consistent code style (PEP8)
- [ ] **Task**: Verify all imports are correct

## Critical Success Criteria

### Must Have
- [ ] Single iterations work identically to original submit()
- [ ] Multiple iterations execute sequentially 
- [ ] Backup system creates nodes between iterations
- [ ] Error messages are suppressed during iterations
- [ ] User can cancel iteration runs cleanly
- [ ] No regression in existing animation/submit functionality

### Nice to Have  
- [ ] Progress tracking shows current iteration clearly
- [ ] Final completion message shows total iterations completed
- [ ] Error logging still works (just UI messages suppressed)

## Estimated Timeline
- **Phase 1**: 2-3 hours
- **Phase 2**: 1-2 hours  
- **Phase 3**: 2-3 hours
- **Phase 4**: 1-2 hours
- **Phase 5**: 3-4 hours
- **Phase 6**: 1 hour

**Total**: 10-15 hours

## Next Steps
1. Start with Phase 1 - Core Infrastructure Setup
2. Test each phase thoroughly before moving to next
3. Keep existing functionality working at each step
4. Document any issues or deviations from plan 