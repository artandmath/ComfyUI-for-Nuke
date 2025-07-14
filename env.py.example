import os
from .nuke_util.nuke_util import get_nuke_path

# Default values
_dir_local  = '<path_TO_shared_ComfyUI>'  #eg '//10.10.10.10/shares/ComfyUI'
_dir_remote = '<path_ON_shared_ComfyUI>'  #eg '/home/user/ComfyUI/'
_ip         = '10.10.10.10'
_port       = 8188
_nuke_user  = get_nuke_path() #/home/<USER>/.nuke

def NUKE_COMFYUI_DIR_LOCAL():
    """Get local ComfyUI directory from environment or default"""
    return os.environ.get('NUKE_COMFYUI_DIR_LOCAL', _dir_local)

def NUKE_COMFYUI_DIR_REMOTE():
    """Get remote ComfyUI directory from environment or default"""
    return os.environ.get('NUKE_COMFYUI_DIR_REMOTE', _dir_remote)

def NUKE_COMFYUI_IP():
    """Get ComfyUI IP from environment or default"""
    return os.environ.get('NUKE_COMFYUI_IP', _ip)

def NUKE_COMFYUI_PORT():
    """Get ComfyUI port from environment or default"""
    return int(os.environ.get('NUKE_COMFYUI_PORT', _port))

def NUKE_COMFYUI_NUKE_USER():
    """Get Nuke user directory from environment or default"""
    return os.environ.get('NUKE_COMFYUI_NUKE_USER', _nuke_user)
