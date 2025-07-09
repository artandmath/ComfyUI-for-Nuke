# -----------------------------------------------------------
# AUTHOR --------> Francisco Contreras
# OFFICE --------> Senior VFX Compositor, Software Developer
# WEBSITE -------> https://vinavfx.com
# -----------------------------------------------------------
import textwrap
import os
import shutil
import sys
import nuke  # type: ignore
import uuid
import traceback
from time import sleep
import websocket
import json
import threading
import copy

from ..nuke_util.nuke_util import set_tile_color
from ..env import NUKE_COMFYUI_IP, NUKE_COMFYUI_PORT
from .common import get_comfyui_dir_remote, get_comfyui_dir_local, replace_local_paths_with_remote, replace_remote_paths_with_local, update_images_and_mask_inputs
from .connection import POST, interrupt, check_connection
from .nodes import extract_data, get_connected_comfyui_nodes
from .read_media import create_read, update_filename_prefix, exr_filepath_fixed, get_filename

client_id = str(uuid.uuid4())[:32].replace('-', '')
states = {}
iteration_mode = False


def multi_node_submit(nodes=None, iterations=None):
    """Run multiple ComfyUI gizmos sequentially, accessing Run nodes inside groups"""
    if nodes is None:
        nodes = nuke.selectedNodes()
    
    # Find ComfyUI gizmos or direct Run nodes
    comfyui_gizmos = []
    for node in nodes:
        if node.Class() == 'Group':
            with node:
                run_node = nuke.toNode('Run')
                if run_node and run_node.knob('comfyui_submit'):
                    # Get iteration count from the gizmo if not specified
                    gizmo_iterations = iterations
                    if gizmo_iterations is None:
                        iteration_knob = node.knob('iteration_count')
                        if iteration_knob:
                            gizmo_iterations = int(iteration_knob.value())
                            if gizmo_iterations < 1:
                                gizmo_iterations = 1
                        else:
                            gizmo_iterations = 1
                    
                    comfyui_gizmos.append((node, run_node, gizmo_iterations))
    
    if not comfyui_gizmos:
        nuke.message('No ComfyUI gizmos or Run nodes selected!')
        return
    
    total_nodes = len(comfyui_gizmos)
    multi_task = [nuke.ProgressTask('Running {} gizmos...'.format(total_nodes))]
    completed_nodes = [0]
    
    def run_next_gizmo(gizmo_index=0):
        if gizmo_index >= len(comfyui_gizmos):
            # All gizmos completed
            del multi_task[0]
            nuke.message('Completed running {} ComfyUI gizmos!'.format(total_nodes))
            return
            
        if multi_task[0].isCancelled():
            del multi_task[0]
            return
            
        gizmo_node, run_node, gizmo_iterations = comfyui_gizmos[gizmo_index]
        progress = int((gizmo_index * 100) / total_nodes)
        multi_task[0].setProgress(progress)
        multi_task[0].setMessage('Running gizmo {}/{}: {} ({} iterations)'.format(
            gizmo_index + 1, total_nodes, gizmo_node.name(), gizmo_iterations))
        
        def success_callback(read_node):
            completed_nodes[0] += 1
            # Continue to next gizmo
            run_next_gizmo(gizmo_index + 1)
        
        # Execute the gizmo's update_frames if it exists
        update_frames_knob = gizmo_node.knob('update_frames')
        if update_frames_knob:
            update_frames_knob.execute()
        
        # Check if force_animation is enabled
        force_animation = False
        force_animation_knob = run_node.knob('force_animation')
        if force_animation_knob:
            force_animation = force_animation_knob.value()
        
        # Run the gizmo with appropriate method
        if force_animation:
            # Use animation submit if force_animation is enabled
            submit_with_context(gizmo_node, run_node, animation_mode=True, success_callback=success_callback)
        else:
            # Use iteration submit with the gizmo's iteration count
            submit_with_context(gizmo_node, run_node, iterations=gizmo_iterations, success_callback=success_callback)
    
    # Start with the first gizmo
    run_next_gizmo(0)


def submit_with_context(gizmo_node, run_node, iterations=1, animation_mode=False, success_callback=None):
    """Submit a run with proper context switching for gizmos"""
    # Switch to the gizmo's context if it's a group
    if gizmo_node.Class() == 'Group' and gizmo_node != run_node:
        with gizmo_node:
            if animation_mode:
                # Call animation_submit in the gizmo context
                nuke.executeInMainThread(animation_submit_in_context, args=(run_node, success_callback))
            elif iterations > 1:
                iteration_submit_for_node(run_node, iterations, success_callback)
            else:
                submit(run_node=run_node, success_callback=success_callback)
    else:
        # Direct run node
        if animation_mode:
            nuke.executeInMainThread(animation_submit_in_context, args=(run_node, success_callback))
        elif iterations > 1:
            iteration_submit_for_node(run_node, iterations, success_callback)
        else:
            submit(run_node=run_node, success_callback=success_callback)


def animation_submit_in_context(run_node, success_callback=None):
    """Call animation_submit with proper context"""
    # Temporarily set nuke.thisNode to return the run_node
    original_thisNode = nuke.thisNode
    nuke.thisNode = lambda: run_node
    
    try:
        animation_submit()
        if success_callback:
            success_callback(None)
    finally:
        # Restore original thisNode function
        nuke.thisNode = original_thisNode


def iteration_submit_for_node(run_node, iteration_count, completion_callback=None):
    """Run iterations for a specific node (modified version of iteration_submit)"""
    if iteration_count <= 1:
        submit(run_node=run_node, success_callback=completion_callback)
        return
    
    iteration_task = [nuke.ProgressTask('Iterations: {}'.format(iteration_count))]
    iteration_results = []
    
    def iteration_callback(iteration_num, filename):
        iteration_results.append((iteration_num, filename))
        
    def finished_callback():
        global iteration_mode
        iteration_mode = False
        del iteration_task[0]
        if completion_callback:
            completion_callback(None)  # Call the completion callback when all iterations are done
    
    global iteration_mode
    iteration_mode = True
    
    submit(run_node, iterations=(1, iteration_count, iteration_callback, finished_callback, iteration_task))


def error_node_style(node_name, enable, message=''):
    node = nuke.toNode(node_name)
    if not node:
        return

    if enable:
        set_tile_color(node, [0, 1, 1])
        message = ' '.join(message.split()[:30])
        formatted_message = '\n'.join(textwrap.wrap(message, width=30))
        node.knob('label').setValue('ERROR:\n' + formatted_message)
    else:
        node['tile_color'].setValue(0)
        node.knob('label').setValue('')


def remove_all_error_style(root_node):
    for n, _ in get_connected_comfyui_nodes(root_node):
        label_knob = n.knob('label')
        if 'ERROR' in label_knob.value():
            error_node_style(n.fullName(), False)


def update_node(node_name, data, run_node):
    # Convert remote paths to local paths for local processing
    local_data = replace_remote_paths_with_local(data)

    if 'ShowText' in node_name:
        show_text_uptate(node_name, local_data, run_node)

    elif 'PreviewImage' in node_name:
        preview_image_update(node_name, local_data)


def show_text_uptate(node_name, data, run_node):
    output = data.get('output', {})
    texts = output.get('text', [])
    text = texts[0] if texts else ''

    run_node.parent().begin()
    show_text_node = nuke.toNode(node_name)

    if not show_text_node:
        return

    if not text:
        return

    text = text.replace('\n', '')
    text = text.encode('utf-8') if sys.version_info[0] < 3 else text
    formatted_text = '\n'.join(textwrap.wrap(text, width=50))

    text_knob = show_text_node.knob('text')
    if text_knob:
        text_knob.setValue(text)

    output_text_node = nuke.toNode(node_name + 'Output')
    if not output_text_node:
        return

    label = '( [value {}.name] )\n{}\n\n'.format(node_name, formatted_text)
    output_text_node.knob('label').setValue(label)
    xpos = show_text_node.xpos() - output_text_node.screenWidth() - 50
    ypos = show_text_node.ypos() - (output_text_node.screenHeight() / 2) + \
        (show_text_node.screenHeight() / 2)
    output_text_node.knob('label')
    output_text_node.setXYpos(xpos, ypos)


def preview_image_update(node_name, data):
    output = data.get('output', {})
    images = output.get('images', [])

    if not images:
        return

    filename = images[0].get('filename')
    if not filename:
        return

    preview_node = nuke.toNode(node_name)
    if not preview_node:
        return

    preview_node.begin()

    filename = '{}/temp/{}'.format(get_comfyui_dir_local(), filename)
    read = nuke.toNode('read')

    if not read:
        read = nuke.createNode('Read', inpanel=False)
        read.setName('read')

    read.knob('file').setValue(filename)
    nuke.toNode('Output1').setInput(0, read)

    preview_node.knob('postage_stamp').setValue(True)
    preview_node.end()


def animation_submit():
    run_node = nuke.thisNode()

    p = nuke.Panel('ComfyUI Submit')
    p.addSingleLineInput(
        'Frames', '{}-{}'.format(nuke.root().firstFrame(), nuke.root().lastFrame()))
    p.addButton('Cancel')
    p.addButton('Send')

    if not p.show():
        return

    try:
        first_frame, last_frame = map(int, p.value('Frames').split('-'))
    except:
        nuke.message('Incompatible field of "Frames"')
        return

    animation_task = [nuke.ProgressTask('Sending Frames...')]
    sequence = []

    def each_frame(frame, filename):
        progress = int((frame - first_frame) * 100 / (last_frame - first_frame))
        animation_task[0].setProgress(progress)
        animation_task[0].setMessage('Frame: ' + str(frame))
        sequence.append((filename, frame))

    def finished_inference():
        del animation_task[0]

        first_filename = sequence[0][0]
        basename = first_filename.split('_')[0]
        sequence_output = os.path.dirname(first_filename)
        ext = first_filename.split('.')[-1]

        for filename, frame in sequence:
            frame_str = '0000{}'.format(frame)[-4:]
            shutil.move(filename, '{}_{}.{}'.format(basename, frame_str, ext))

        filename = nuke.getFileNameList(sequence_output)[0]
        create_read(run_node, os.path.join(sequence_output, filename))

    submit(animation=[first_frame, last_frame, each_frame, finished_inference, animation_task])


def submit(run_node=None, animation=None, iterations=None, success_callback=None):
    if not check_connection():
        return

    update_images_and_mask_inputs()

    if nuke.comfyui_running:
        if not iteration_mode:
            nuke.message('Inference in execution !')
        return

    nuke.comfyui_running = True

    comfyui_dir = get_comfyui_dir_remote()
    if not comfyui_dir:
        nuke.comfyui_running = False
        return

    frame = animation[0] if animation else -1

    # Handle iterations parameter
    if iterations:
        current_iteration, total_iterations, iteration_callback, finished_callback, iteration_task = iterations
        # Update progress right at the start of this iteration
        iteration_task[0].setMessage('Iteration: {}/{}'.format(current_iteration, total_iterations))

    run_node = run_node if run_node else nuke.thisNode()
    exr_filepath_fixed(run_node)

    data, input_node_changed = extract_data(frame, run_node)

    if not data:
        nuke.comfyui_running = False
        return

    global states
    if data == states.get(run_node.fullName(), {}) and not input_node_changed and not animation:
        nuke.comfyui_running = False
        read = create_read(run_node, get_filename(run_node))

        if success_callback:
            success_callback(read)
        return

    update_filename_prefix(run_node)
    data, _ = extract_data(frame, run_node)

    state_data = copy.deepcopy(data)
    run_node.knob('comfyui_submit').setEnabled(False)

    # Convert local paths to remote paths for sending to ComfyUI
    remote_data = replace_local_paths_with_remote(data)

    body = {
        'client_id': client_id,
        'prompt': remote_data,
        'extra_data': {}
    }

    url = "ws://{}:{}/ws?clientId={}".format(NUKE_COMFYUI_IP, NUKE_COMFYUI_PORT, client_id)
    task = [nuke.ProgressTask('ComfyUI Connection...')]

    execution_error = [False]

    def on_message(_, message):
        # Check if message is binary data. This e.g. happens when a live preview is send from ComfyUI.
        try:
            message = json.loads(message)
        except:
            # TODO: maybe show the preview image in Nuke?
            return

        data = message.get('data', None)
        type_data = message.get('type', None)

        if not data:
            return

        elif type_data == 'executed':
            node = data.get('node')
            nuke.executeInMainThread(
                update_node, args=(node, data, run_node))

        elif type_data == 'progress':
            progress = int(data['value'] * 100 / data['max'])
            if task:
                task[0].setProgress(progress)

        elif type_data == 'executing':
            node = data.get('node')

            if task:
                if node:
                    task[0].setMessage('Inference: ' + node)
                else:
                    del task[0]

        elif type_data == 'execution_error':
            execution_message = data.get('exception_message')
            error = 'Error: {}\n\n'.format(data.get('node_type'))
            error += execution_message + '\n\n'

            for tb in data.get('traceback'):
                error += tb + '\n'

            execution_error[0] = True

            if task:
                del task[0]

            nuke.executeInMainThread(
                error_node_style, args=(data.get('node_id'), True, execution_message))
            if not iteration_mode:
                nuke.executeInMainThread(nuke.message, args=(error))

    def on_error(ws, error):
        ws.close()
        if task:
            del task[0]

        if 'connected' in str(error):
            return

        execution_error[0] = True
        if not iteration_mode:
            nuke.executeInMainThread(nuke.message, args=('error: ' + str(error)))

    def progress_task_loop():
        cancelled = False
        while task:
            if task[0].isCancelled():
                cancelled = True
                break

            if animation:
                if animation[4][0].isCancelled():
                    cancelled = True
                    break

            sleep(.1)

        interrupt()

        if task:
            del task[0]

        ws.close()

        if cancelled:
            run_node.knob('comfyui_submit').setEnabled(True)
            nuke.comfyui_running = False
            return

        nuke.executeInMainThread(progress_finished, args=(run_node))
        run_node.knob('comfyui_submit').setEnabled(True)
        nuke.comfyui_running = False

    def progress_finished(n):
        filename = get_filename(run_node)

        if iterations:
            current_iteration, total_iterations, iteration_callback, finished_callback, iteration_task = iterations
            
            # Run normal completion steps for this iteration
            try:
                if filename:  # Only create read node if we have a valid filename
                    read = create_read(n, filename)
                else:
                    read = None

                if success_callback:
                    success_callback(read)

                if not execution_error[0]:
                    remove_all_error_style(run_node)
                    states[run_node.fullName()] = state_data

            except Exception as e:
                pass  # Don't fail if normal completion fails
            
            # Then create a backup of this iteration's result
            if read and filename:  # Only create backup if read node was created successfully
                try:
                    # Simple backup creation without complex context switching
                    read_parent = read.parent()
                    if read_parent:
                        read_parent.begin()
                        
                        # Create backup name
                        import os
                        from ..nuke_util.media_util import get_name_no_padding
                        basename = get_name_no_padding(filename).replace(' ', '_')
                        rand = str(current_iteration).zfill(4)  # Use iteration number as identifier
                        gizmo_name = read.name().replace('Read', '')  # Get gizmo name from read node
                        backup_name = '{}Backup_{}'.format(gizmo_name, rand)
                        
                        # Create backup read node if it doesn't exist
                        if not nuke.toNode(backup_name):
                            backup_read = nuke.createNode('Read', inpanel=False)
                            backup_read.setName(backup_name)
                            backup_read.knob('file').setValue(read.knob('file').value())
                            backup_read.knob('first').setValue(read.knob('first').value())
                            backup_read.knob('last').setValue(read.knob('last').value())
                            
                            # Set colorspace
                            from .read_media import set_correct_colorspace
                            set_correct_colorspace(backup_read)
                            
                            # Position backup node
                            xpos = read.xpos() + (current_iteration * 100)
                            backup_read.setXYpos(xpos, read.ypos())
                            
                        read_parent.end()
                        
                except Exception as e:
                    pass  # Don't fail if backup fails during iterations
                
            iteration_callback(current_iteration, filename)
            
            next_iteration = current_iteration + 1
            if next_iteration > total_iterations:
                finished_callback()
                return
                
            # Continue to next iteration
            submit(run_node, iterations=(next_iteration, total_iterations, iteration_callback, finished_callback, iteration_task))
            return

        if animation:
            frame, last_frame, each, end, animation_task = animation
            if animation_task[0].isCancelled():
                return

            each(frame, get_filename(run_node))

            next_frame = frame + 1
            if next_frame > last_frame:
                end()
                return

            run_node.begin()
            submit(animation=(next_frame, last_frame, each, end, animation_task))

            return

        try:
            read = create_read(n, filename)

            if success_callback:
                success_callback(read)

            if not execution_error[0]:
                remove_all_error_style(run_node)
                states[run_node.fullName()] = state_data

        except:
            nuke.executeInMainThread(
                nuke.message, args=(traceback.format_exc()))

    ws = websocket.WebSocketApp(url, on_message=on_message, on_error=on_error)

    threading.Thread(target=ws.run_forever).start()
    threading.Thread(target=progress_task_loop).start()

    error = POST('prompt', body)

    if error:
        execution_error[0] = True
        if task:
            del task[0]
        nuke.comfyui_running = False
        if not iteration_mode:
            nuke.message(error)
        run_node.knob('comfyui_submit').setEnabled(True)


def iteration_submit(iteration_count):
    """Entry point for X iterations of ComfyUI runs"""
    run_node = nuke.thisNode()
    
    if iteration_count <= 1:
        submit()
        return
    
    iteration_task = [nuke.ProgressTask('Iterations: {}'.format(iteration_count))]
    iteration_results = []
    
    def iteration_callback(iteration_num, filename):
        iteration_results.append((iteration_num, filename))
        
    def finished_callback():
        global iteration_mode
        iteration_mode = False
        del iteration_task[0]
    
    global iteration_mode
    iteration_mode = True
    
    submit(run_node, iterations=(1, iteration_count, iteration_callback, finished_callback, iteration_task))
