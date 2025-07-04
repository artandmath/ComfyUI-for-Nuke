# -----------------------------------------------------------
# AUTHOR --------> Francisco Contreras
# OFFICE --------> Senior VFX Compositor, Software Developer
# WEBSITE -------> https://vinavfx.com
# -----------------------------------------------------------
import os
import nuke  # type: ignore
from ..env import NUKE_COMFYUI_DIR_REMOTE, NUKE_COMFYUI_DIR_LOCAL
from .connection import GET

if not getattr(nuke, 'comfyui_running', False):
    nuke.comfyui_running = False

image_inputs = ['image', 'frames', 'pixels', 'images', 'src_images']
mask_inputs = ['mask', 'attn_mask', 'mask_optional']
updated_inputs = False


def update_images_and_mask_inputs():
    global image_inputs, mask_inputs, updated_inputs

    if updated_inputs:
        return

    updated_inputs = True

    info = GET('object_info')
    if not info:
        return

    for _, data in info.items():
        input_data = data['input']
        required = input_data.get('required', {})
        optional = input_data.get('optional', {})

        for name, value in list(required.items()) + list(optional.items()):
            if value[0] == 'IMAGE':
                if not name in image_inputs:
                    image_inputs.append(name)

            elif value[0] == 'MASK':
                if not name in mask_inputs:
                    mask_inputs.append(name)


def get_available_name(prefix, directory):
    prefix += '_'
    taken_names = set(os.listdir(directory))

    for i in range(10000):
        potential_name = '{}{:04d}'.format(prefix, i)
        if potential_name not in taken_names:
            return potential_name

    return prefix


def get_comfyui_dir():
    # For backwards compatibility during transition
    return get_comfyui_dir_local()


def get_comfyui_dir_remote():
    return NUKE_COMFYUI_DIR_REMOTE

def get_comfyui_dir_local():
    if os.path.isdir(os.path.join(NUKE_COMFYUI_DIR_LOCAL, 'comfy')):
        return NUKE_COMFYUI_DIR_LOCAL

    nuke.message('Directory "{}" does not exist'.format(NUKE_COMFYUI_DIR_LOCAL))
    return ''


def replace_local_paths_with_remote(data):
    """Replace local ComfyUI directory paths with remote ones for sending to ComfyUI server"""
    import copy
    
    local_dir = get_comfyui_dir_local()
    remote_dir = get_comfyui_dir_remote()
    
    if not local_dir or not remote_dir:
        return data
    
    # Normalize directory paths for comparison
    local_dir_normalized = local_dir.replace('\\', '/')
    remote_dir_normalized = remote_dir.replace('\\', '/')
    
    # Make a deep copy to avoid modifying the original data
    remote_data = copy.deepcopy(data)
    
    # Recursively replace paths in the data structure
    def replace_paths_recursive(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    # Normalize the value path and check if it contains local directory
                    value_normalized = value.replace('\\', '/')
                    if local_dir_normalized in value_normalized:
                        # Replace with remote directory and ensure forward slashes for remote
                        new_value = value_normalized.replace(local_dir_normalized, remote_dir_normalized)
                        obj[key] = new_value
                    else:
                        replace_paths_recursive(value)
                else:
                    replace_paths_recursive(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str):
                    # Normalize the item path and check if it contains local directory
                    item_normalized = item.replace('\\', '/')
                    if local_dir_normalized in item_normalized:
                        # Replace with remote directory and ensure forward slashes for remote
                        new_item = item_normalized.replace(local_dir_normalized, remote_dir_normalized)
                        obj[i] = new_item
                    else:
                        replace_paths_recursive(item)
                else:
                    replace_paths_recursive(item)
    
    replace_paths_recursive(remote_data)
    return remote_data


def replace_remote_paths_with_local(data):
    """Replace remote ComfyUI directory paths with local ones for processing ComfyUI responses locally"""
    import copy
    import os
    
    local_dir = get_comfyui_dir_local()
    remote_dir = get_comfyui_dir_remote()
    
    if not local_dir or not remote_dir:
        return data
    
    # Normalize directory paths for comparison (remote should always use forward slashes)
    local_dir_normalized = local_dir.replace('\\', '/')
    remote_dir_normalized = remote_dir.replace('\\', '/')
    
    # Make a deep copy to avoid modifying the original data
    local_data = copy.deepcopy(data)
    
    # Recursively replace paths in the data structure
    def replace_paths_recursive(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    # Normalize the value path and check if it contains remote directory
                    value_normalized = value.replace('\\', '/')
                    if remote_dir_normalized in value_normalized:
                        # Replace with local directory and use OS-appropriate separators
                        new_value = value_normalized.replace(remote_dir_normalized, local_dir_normalized)
                        # Convert to OS-appropriate path separators for local use
                        obj[key] = os.path.normpath(new_value)
                    else:
                        replace_paths_recursive(value)
                else:
                    replace_paths_recursive(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str):
                    # Normalize the item path and check if it contains remote directory
                    item_normalized = item.replace('\\', '/')
                    if remote_dir_normalized in item_normalized:
                        # Replace with local directory and use OS-appropriate separators
                        new_item = item_normalized.replace(remote_dir_normalized, local_dir_normalized)
                        # Convert to OS-appropriate path separators for local use
                        obj[i] = os.path.normpath(new_item)
                    else:
                        replace_paths_recursive(item)
                else:
                    replace_paths_recursive(item)
    
    replace_paths_recursive(local_data)
    return local_data
  