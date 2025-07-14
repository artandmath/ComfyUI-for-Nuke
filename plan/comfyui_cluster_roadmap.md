# ComfyUI Server Cluster - Implementation Roadmap

## Phase 1: Foundation & Environment Configuration (Week 1)

### Step 1.1: Update Environment Configuration
**File**: `env.py`

```python
import os
import json
from .nuke_util.nuke_util import get_nuke_path

# Default values (backward compatibility)
_dir_local  = 'U:/'
_dir_remote = '/home/kmmuser/ComfyUI/'
_ip         = '192.168.1.187'
_port       = 8188
_nuke_user  = get_nuke_path()

def NUKE_COMFYUI_SERVERS():
    """Get ComfyUI server cluster configuration"""
    servers_json = os.environ.get('NUKE_COMFYUI_SERVERS', None)
    
    # Fallback to current env.py implementation if NUKE_COMFYUI_SERVERS doesn't exist or is empty
    if not servers_json or servers_json.strip() == '':
        return [{
            'name': 'default',
            'ip': NUKE_COMFYUI_IP(),
            'port': NUKE_COMFYUI_PORT(),
            'dir_local': NUKE_COMFYUI_DIR_LOCAL(),
            'dir_remote': NUKE_COMFYUI_DIR_REMOTE(),
            'priority': 1,
            'enabled': True
        }]
    
    try:
        return json.loads(servers_json)
    except json.JSONDecodeError:
        print("Warning: Invalid NUKE_COMFYUI_SERVERS JSON format, falling back to single server configuration")
        # Fallback to current env.py implementation on JSON parse error
        return [{
            'name': 'default',
            'ip': NUKE_COMFYUI_IP(),
            'port': NUKE_COMFYUI_PORT(),
            'dir_local': NUKE_COMFYUI_DIR_LOCAL(),
            'dir_remote': NUKE_COMFYUI_DIR_REMOTE(),
            'priority': 1,
            'enabled': True
        }]

# Maintain backward compatibility
def NUKE_COMFYUI_DIR_LOCAL():
    servers = NUKE_COMFYUI_SERVERS()
    return servers[0]['dir_local'] if servers else _dir_local

def NUKE_COMFYUI_DIR_REMOTE():
    servers = NUKE_COMFYUI_SERVERS()
    return servers[0]['dir_remote'] if servers else _dir_remote

def NUKE_COMFYUI_IP():
    servers = NUKE_COMFYUI_SERVERS()
    return servers[0]['ip'] if servers else _ip

def NUKE_COMFYUI_PORT():
    servers = NUKE_COMFYUI_SERVERS()
    return int(servers[0]['port']) if servers else _port

def NUKE_COMFYUI_NUKE_USER():
    return os.environ.get('NUKE_COMFYUI_NUKE_USER', _nuke_user)
```

### Step 1.2: Create Server Management Classes
**File**: `src/server_pool.py` (new file)

```python
import time
import threading
from typing import List, Dict, Optional
from ..env import NUKE_COMFYUI_SERVERS

class ComfyUIServer:
    def __init__(self, config: Dict):
        self.name = config.get('name', 'unknown')
        self.ip = config.get('ip', 'localhost')
        self.port = config.get('port', 8188)
        self.dir_local = config.get('dir_local', '')
        self.dir_remote = config.get('dir_remote', '')
        self.priority = config.get('priority', 1)
        self.enabled = config.get('enabled', True)
        
        # Status tracking
        self.last_status_check = None
        self.status = 'unknown'
        self.queue_length = 0
        self.processing = False
        self.response_time = None
        
    def __str__(self):
        return f"ComfyUIServer({self.name}:{self.ip}:{self.port})"

class ComfyUIServerPool:
    def __init__(self):
        self.servers: List[ComfyUIServer] = []
        self.current_server_index = 0
        self.status_cache_ttl = 10  # seconds
        self.load_configuration()
        
    def load_configuration(self):
        """Load server configuration from environment"""
        configs = NUKE_COMFYUI_SERVERS()
        self.servers = [ComfyUIServer(config) for config in configs if config.get('enabled', True)]
        
    def get_server_status(self, server: ComfyUIServer) -> Dict:
        """Get current status of a server"""
        current_time = time.time()
        
        # Check cache first
        if (server.last_status_check and 
            current_time - server.last_status_check < self.status_cache_ttl):
            return {
                'status': server.status,
                'queue_length': server.queue_length,
                'processing': server.processing,
                'response_time': server.response_time
            }
        
        # Query server status
        start_time = time.time()
        try:
            from .connection import GET
            queue_data = GET('/queue', {'ip': server.ip, 'port': server.port})
            
            if queue_data:
                queue_running = len(queue_data.get('queue_running', []))
                queue_pending = len(queue_data.get('queue_pending', []))
                
                server.status = 'online'
                server.queue_length = queue_running + queue_pending
                server.processing = queue_running > 0
                server.response_time = time.time() - start_time
            else:
                server.status = 'offline'
                server.queue_length = 0
                server.processing = False
                server.response_time = None
                
        except Exception as e:
            server.status = 'error'
            server.queue_length = 0
            server.processing = False
            server.response_time = None
            
        server.last_status_check = current_time
        
        return {
            'status': server.status,
            'queue_length': server.queue_length,
            'processing': server.processing,
            'response_time': server.response_time
        }
    
    def get_available_server(self, strategy: str = 'least_loaded') -> Optional[ComfyUIServer]:
        """Get the best available server based on strategy"""
        if not self.servers:
            return None
            
        # Update status of all servers
        for server in self.servers:
            self.get_server_status(server)
        
        # Filter online servers
        online_servers = [s for s in self.servers if s.status == 'online']
        
        if not online_servers:
            return None
            
        if strategy == 'round_robin':
            return self._round_robin_select(online_servers)
        elif strategy == 'least_loaded':
            return self._least_loaded_select(online_servers)
        elif strategy == 'priority':
            return self._priority_select(online_servers)
        else:
            return online_servers[0]  # Default to first available
    
    def _round_robin_select(self, servers: List[ComfyUIServer]) -> ComfyUIServer:
        """Round robin selection"""
        server = servers[self.current_server_index % len(servers)]
        self.current_server_index += 1
        return server
    
    def _least_loaded_select(self, servers: List[ComfyUIServer]) -> ComfyUIServer:
        """Select server with shortest queue"""
        return min(servers, key=lambda s: s.queue_length)
    
    def _priority_select(self, servers: List[ComfyUIServer]) -> ComfyUIServer:
        """Select by priority, fallback to least loaded"""
        # Sort by priority first, then by queue length
        return min(servers, key=lambda s: (s.priority, s.queue_length))
    
    def get_all_status(self) -> List[Dict]:
        """Get status of all servers"""
        return [self.get_server_status(server) for server in self.servers]

# Global server pool instance
_server_pool = None

def get_server_pool() -> ComfyUIServerPool:
    """Get global server pool instance"""
    global _server_pool
    if _server_pool is None:
        _server_pool = ComfyUIServerPool()
    return _server_pool
```

## Phase 2: Connection Layer Updates (Week 2)

### Step 2.1: Update Connection Module
**File**: `src/connection.py`

```python
# Add to existing connection.py
import time
from typing import Dict, Optional
from .server_pool import get_server_pool

def GET(relative_url, server_config=None):
    """Enhanced GET with server-specific configuration"""
    if server_config:
        ip = server_config.get('ip')
        port = server_config.get('port')
    else:
        # Use default server (backward compatibility)
        from ..env import NUKE_COMFYUI_IP, NUKE_COMFYUI_PORT
        ip = NUKE_COMFYUI_IP()
        port = NUKE_COMFYUI_PORT()
    
    url = 'http://{}:{}/{}'.format(ip, port, relative_url)
    
    try:
        response = urllib2.urlopen(url, timeout=10)  # Add timeout
        data = response.read().decode()
        return json.loads(data, object_pairs_hook=OrderedDict)
    except Exception as e:
        if not _should_suppress_messages():
            nuke.message('Error connecting to server {}:{} - {}'.format(ip, port, str(e)))
        return None

def POST(relative_url, data={}, server_config=None):
    """Enhanced POST with server-specific configuration"""
    if server_config:
        ip = server_config.get('ip')
        port = server_config.get('port')
    else:
        # Use default server (backward compatibility)
        from ..env import NUKE_COMFYUI_IP, NUKE_COMFYUI_PORT
        ip = NUKE_COMFYUI_IP()
        port = NUKE_COMFYUI_PORT()
    
    url = 'http://{}:{}/{}'.format(ip, port, relative_url)
    headers = {'Content-Type': 'application/json'}
    bytes_data = json.dumps(data).encode('utf-8')
    request = urllib2.Request(url, bytes_data, headers)
    
    try:
        urllib2.urlopen(request, timeout=30)  # Add timeout
        return ''
    except urllib2.HTTPError as e:
        # ... existing error handling ...
        pass
    except Exception as e:
        return 'Error: {}'.format(e)

def check_connection(server_config=None):
    """Enhanced connection check with server-specific configuration"""
    try:
        if server_config:
            ip = server_config.get('ip')
            port = server_config.get('port')
        else:
            from ..env import NUKE_COMFYUI_IP, NUKE_COMFYUI_PORT
            ip = NUKE_COMFYUI_IP()
            port = NUKE_COMFYUI_PORT()
            
        response = urllib2.urlopen('http://{}:{}'.format(ip, port), timeout=5)
        return response.getcode() == 200
    except:
        return False

def get_optimal_server(strategy='least_loaded'):
    """Get optimal server for job submission"""
    server_pool = get_server_pool()
    server = server_pool.get_available_server(strategy)
    
    if server:
        return {
            'ip': server.ip,
            'port': server.port,
            'dir_local': server.dir_local,
            'dir_remote': server.dir_remote,
            'name': server.name
        }
    return None
```

### Step 2.2: WebSocket Connection Management
**File**: `src/websocket_manager.py` (new file)

```python
import websocket
import json
import threading
import time
from typing import Dict, Callable, Optional

class ComfyUIWebSocketManager:
    def __init__(self):
        self.connections: Dict[str, websocket.WebSocketApp] = {}
        self.callbacks: Dict[str, Dict] = {}
        self.client_id = None
        
    def create_connection(self, server_config: Dict, callbacks: Dict) -> str:
        """Create WebSocket connection to specific server"""
        ip = server_config['ip']
        port = server_config['port']
        client_id = self._generate_client_id()
        
        url = "ws://{}:{}/ws?clientId={}".format(ip, port, client_id)
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if 'on_message' in callbacks:
                    callbacks['on_message'](data)
            except:
                pass  # Handle binary data or invalid JSON
                
        def on_error(ws, error):
            if 'on_error' in callbacks:
                callbacks['on_error'](error)
                
        def on_close(ws, close_status_code, close_msg):
            if 'on_close' in callbacks:
                callbacks['on_close']()
                
        ws = websocket.WebSocketApp(
            url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        connection_id = f"{ip}:{port}:{client_id}"
        self.connections[connection_id] = ws
        self.callbacks[connection_id] = callbacks
        
        # Start connection in background thread
        thread = threading.Thread(target=ws.run_forever)
        thread.daemon = True
        thread.start()
        
        return connection_id
        
    def close_connection(self, connection_id: str):
        """Close specific WebSocket connection"""
        if connection_id in self.connections:
            self.connections[connection_id].close()
            del self.connections[connection_id]
            del self.callbacks[connection_id]
            
    def close_all(self):
        """Close all WebSocket connections"""
        for connection_id in list(self.connections.keys()):
            self.close_connection(connection_id)
            
    def _generate_client_id(self) -> str:
        """Generate unique client ID"""
        import uuid
        return str(uuid.uuid4())[:32].replace('-', '')

# Global WebSocket manager
_websocket_manager = None

def get_websocket_manager() -> ComfyUIWebSocketManager:
    """Get global WebSocket manager instance"""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = ComfyUIWebSocketManager()
    return _websocket_manager
```

## Phase 3: Execution Integration (Week 3)

### Step 3.1: Update Run Module
**File**: `src/run.py`

```python
# Add to existing run.py imports
from .server_pool import get_server_pool
from .websocket_manager import get_websocket_manager
from .connection import get_optimal_server

def submit(run_node=None, animation=None, iterations=None, success_callback=None, strategy='least_loaded'):
    """Enhanced submit with server selection"""
    if not check_connection():
        return

    update_images_and_mask_inputs()

    if nuke.comfyui_running:
        if not iteration_mode:
            nuke.message('Inference in execution !')
        return

    nuke.comfyui_running = True

    # Get optimal server
    server_config = get_optimal_server(strategy)
    if not server_config:
        nuke.comfyui_running = False
        nuke.message('No available ComfyUI servers!')
        return

    # Update environment for this submission
    original_env = {
        'ip': NUKE_COMFYUI_IP(),
        'port': NUKE_COMFYUI_PORT(),
        'dir_local': get_comfyui_dir_local(),
        'dir_remote': get_comfyui_dir_remote()
    }
    
    # Temporarily set environment for this server
    def set_server_env():
        import os
        os.environ['NUKE_COMFYUI_IP'] = server_config['ip']
        os.environ['NUKE_COMFYUI_PORT'] = str(server_config['port'])
        os.environ['NUKE_COMFYUI_DIR_LOCAL'] = server_config['dir_local']
        os.environ['NUKE_COMFYUI_DIR_REMOTE'] = server_config['dir_remote']
    
    def restore_env():
        import os
        os.environ['NUKE_COMFYUI_IP'] = original_env['ip']
        os.environ['NUKE_COMFYUI_PORT'] = str(original_env['port'])
        os.environ['NUKE_COMFYUI_DIR_LOCAL'] = original_env['dir_local']
        os.environ['NUKE_COMFYUI_DIR_REMOTE'] = original_env['dir_remote']
    
    set_server_env()
    
    try:
        # Continue with existing submission logic
        comfyui_dir = get_comfyui_dir_remote()
        if not comfyui_dir:
            nuke.comfyui_running = False
            return

        frame = animation[0] if animation else -1

        # Handle iterations parameter
        if iterations:
            current_iteration, total_iterations, iteration_callback, finished_callback, iteration_task = iterations
            iteration_task[0].setMessage('Iteration: {}/{} (Server: {})'.format(
                current_iteration, total_iterations, server_config['name']))

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

        # Use server-specific WebSocket connection
        websocket_manager = get_websocket_manager()
        
        def on_message(data):
            # Handle WebSocket messages (existing logic)
            pass
            
        def on_error(error):
            # Handle WebSocket errors
            pass
            
        def on_close():
            # Handle WebSocket close
            pass
        
        connection_id = websocket_manager.create_connection(
            server_config, 
            {'on_message': on_message, 'on_error': on_error, 'on_close': on_close}
        )

        # Submit to specific server
        error = POST('prompt', body, server_config)

        if error:
            nuke.comfyui_running = False
            if not iteration_mode:
                nuke.message(error)
            run_node.knob('comfyui_submit').setEnabled(True)
            websocket_manager.close_connection(connection_id)
            
    finally:
        restore_env()
```

## Phase 4: User Interface (Week 4)

### Step 4.1: Server Status Panel
**File**: `src/server_panel.py` (new file)

```python
import nuke
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem
from PySide2.QtCore import QTimer
from .server_pool import get_server_pool

class ServerStatusPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.server_pool = get_server_pool()
        self.setup_ui()
        self.setup_timer()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("ComfyUI Server Status")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Server table
        self.server_table = QTableWidget()
        self.server_table.setColumnCount(5)
        self.server_table.setHorizontalHeaderLabels([
            "Server", "Status", "Queue", "Processing", "Response Time"
        ])
        layout.addWidget(self.server_table)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_status)
        button_layout.addWidget(refresh_btn)
        
        auto_refresh_btn = QPushButton("Auto Refresh")
        auto_refresh_btn.setCheckable(True)
        auto_refresh_btn.toggled.connect(self.toggle_auto_refresh)
        button_layout.addWidget(auto_refresh_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def setup_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_status)
        self.auto_refresh_enabled = False
        
    def refresh_status(self):
        """Update server status display"""
        servers = self.server_pool.servers
        self.server_table.setRowCount(len(servers))
        
        for i, server in enumerate(servers):
            status = self.server_pool.get_server_status(server)
            
            # Server name
            name_item = QTableWidgetItem(server.name)
            self.server_table.setItem(i, 0, name_item)
            
            # Status
            status_item = QTableWidgetItem(status['status'])
            if status['status'] == 'online':
                status_item.setBackground(QColor(200, 255, 200))  # Green
            elif status['status'] == 'offline':
                status_item.setBackground(QColor(255, 200, 200))  # Red
            else:
                status_item.setBackground(QColor(255, 255, 200))  # Yellow
            self.server_table.setItem(i, 1, status_item)
            
            # Queue length
            queue_item = QTableWidgetItem(str(status['queue_length']))
            self.server_table.setItem(i, 2, queue_item)
            
            # Processing
            processing_item = QTableWidgetItem("Yes" if status['processing'] else "No")
            self.server_table.setItem(i, 3, processing_item)
            
            # Response time
            response_time = status.get('response_time')
            if response_time:
                response_item = QTableWidgetItem(f"{response_time:.3f}s")
            else:
                response_item = QTableWidgetItem("N/A")
            self.server_table.setItem(i, 4, response_item)
            
    def toggle_auto_refresh(self, enabled):
        """Toggle automatic status refresh"""
        self.auto_refresh_enabled = enabled
        if enabled:
            self.timer.start(5000)  # Refresh every 5 seconds
        else:
            self.timer.stop()

def show_server_panel():
    """Show server status panel"""
    panel = ServerStatusPanel()
    panel.show()
    return panel
```

## Phase 5: Testing & Deployment (Week 5)

### Step 5.1: Configuration Examples
**Environment Variables Setup**:

```bash
# Option 1: JSON Array (Recommended)
export NUKE_COMFYUI_SERVERS='[
  {
    "name": "primary",
    "ip": "192.168.1.187",
    "port": 8188,
    "dir_local": "U:/",
    "dir_remote": "/home/kmmuser/ComfyUI/",
    "priority": 1,
    "enabled": true
  },
  {
    "name": "secondary",
    "ip": "192.168.1.188", 
    "port": 8188,
    "dir_local": "U:/",
    "dir_remote": "/home/kmmuser/ComfyUI/",
    "priority": 2,
    "enabled": true
  }
]'

# Option 2: Backward Compatible (Single Server)
export NUKE_COMFYUI_IP=192.168.1.187
export NUKE_COMFYUI_PORT=8188
export NUKE_COMFYUI_DIR_LOCAL=U:/
export NUKE_COMFYUI_DIR_REMOTE=/home/kmmuser/ComfyUI/
```

### Step 5.2: Testing Checklist
- [ ] Single server functionality (backward compatibility)
- [ ] Multi-server configuration loading
- [ ] Server status detection
- [ ] Load balancing strategies
- [ ] WebSocket connection management
- [ ] Job submission to different servers
- [ ] Error handling and failover
- [ ] Performance under load
- [ ] User interface functionality

### Step 5.3: Deployment Steps
1. **Backup existing configuration**
2. **Deploy new code**
3. **Test with single server first**
4. **Add additional servers gradually**
5. **Monitor performance and errors**
6. **Update user documentation**

## Success Metrics

### Performance Improvements
- **Reduced wait times**: 50-80% reduction in queue wait times
- **Higher throughput**: 2-3x increase in concurrent processing
- **Better reliability**: 99%+ uptime with automatic failover

### User Experience
- **Seamless operation**: No user intervention required
- **Transparent failover**: Automatic server switching
- **Status visibility**: Real-time server status monitoring

### Technical Quality
- **Backward compatibility**: Existing setups continue to work
- **Error handling**: Graceful degradation on server failures
- **Performance**: Minimal overhead (<100ms additional latency) 