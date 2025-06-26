import os
from .nuke_util.nuke_util import get_nuke_path

dir_local  = '<path_TO_shared_ComfyUI>'  #eg '//10.10.10.10/shares/ComfyUI'
dir_remote = '<path_ON_shared_ComfyUI>'  #eg '/home/user/ComfyUI/'
ip         = '10.10.10.10'
port       = 8188
nuke_user  = get_nuke_path() #/home/<USER>/.nuke

NUKE_COMFYUI_DIR_LOCAL = os.environ.get('NUKE_COMFYUI_DIR_LOCAL', dir_local)
NUKE_COMFYUI_DIR_REMOTE = os.environ.get('NUKE_COMFYUI_DIR_REMOTE', dir_remote)
NUKE_COMFYUI_IP = os.environ.get('NUKE_COMFYUI_IP',ip)
NUKE_COMFYUI_PORT = int(os.environ.get('NUKE_COMFYUI_PORT', port))
NUKE_COMFYUI_NUKE_USER = os.environ.get('NUKE_COMFYUI_NUKE_USER', nuke_user)
