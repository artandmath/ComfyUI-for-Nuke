# ComfyUI Server Cluster Implementation Plan

## Overview
This plan outlines the implementation of a ComfyUI server cluster system that allows Nuke to distribute workloads across multiple ComfyUI servers, with intelligent load balancing and queue management.

## Current System Analysis

### Current Architecture
- Single server configuration via environment variables
- Direct connection to one ComfyUI instance
- No load balancing or failover capabilities
- Uses WebSocket connections for real-time communication
- HTTP GET/POST for API calls

### Key Components
- `env.py`: Environment configuration
- `src/connection.py`: HTTP/WebSocket communication
- `src/run.py`: Main execution logic
- `src/common.py`: Shared utilities

## Implementation Options

### Option 1: Environment Variable Array (Recommended)
Store server configurations as JSON arrays in environment variables:

```bash
# Single environment variable containing all server configs
NUKE_COMFYUI_SERVERS='[
  {
    "name": "server1",
    "ip": "192.168.1.187",
    "port": 8188,
    "dir_local": "U:/",
    "dir_remote": "/home/kmmuser/ComfyUI/",
    "priority": 1,
    "enabled": true
  },
  {
    "name": "server2", 
    "ip": "192.168.1.188",
    "port": 8188,
    "dir_local": "U:/",
    "dir_remote": "/home/kmmuser/ComfyUI/",
    "priority": 2,
    "enabled": true
  }
]'
```

**Pros:**
- Single environment variable to manage
- Flexible configuration
- Easy to add/remove servers
- Can include metadata (priority, enabled status)

**Cons:**
- JSON parsing required
- Slightly more complex than numbered variables

### Option 2: Numbered Environment Variables
```bash
NUKE_COMFYUI_IP_1=192.168.1.187
NUKE_COMFYUI_PORT_1=8188
NUKE_COMFYUI_DIR_LOCAL_1=U:/
NUKE_COMFYUI_DIR_REMOTE_1=/home/kmmuser/ComfyUI/

NUKE_COMFYUI_IP_2=192.168.1.188
NUKE_COMFYUI_PORT_2=8188
NUKE_COMFYUI_DIR_LOCAL_2=U:/
NUKE_COMFYUI_DIR_REMOTE_2=/home/kmmuser/ComfyUI/
```

**Pros:**
- Simple to understand
- Backward compatible with existing system

**Cons:**
- Multiple environment variables to manage
- Limited metadata capabilities
- Harder to add/remove servers dynamically

## Server Status Detection

### Available ComfyUI API Endpoints
Based on ComfyUI's API, we can use these endpoints for status detection:

1. **Queue Status**: `GET /queue` - Returns current queue information
2. **History**: `GET /history` - Returns execution history
3. **System Stats**: `GET /system_stats` - Returns system information
4. **Object Info**: `GET /object_info` - Returns available nodes (already used)

### Server Status Implementation
```python
def get_server_status(server_config):
    """Get current status of a ComfyUI server"""
    try:
        # Check if server is responding
        queue_data = GET('/queue', server_config)
        if not queue_data:
            return {'status': 'offline', 'queue_length': 0, 'processing': False}
        
        # Parse queue information
        queue_length = len(queue_data.get('queue_running', []))
        processing = len(queue_data.get('queue_running', [])) > 0
        
        return {
            'status': 'online',
            'queue_length': queue_length,
            'processing': processing,
            'server_config': server_config
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e), 'server_config': server_config}
```

## Load Balancing Strategies

### Strategy 1: Round Robin (Simple)
- Cycle through available servers in order
- Good for equal-capacity servers

### Strategy 2: Least Loaded (Recommended)
- Query all servers for queue status
- Select server with shortest queue
- Best for varying server capacities

### Strategy 3: Priority Based
- Use server priority from configuration
- Fall back to least loaded if priority servers are busy
- Good for heterogeneous server setups

### Strategy 4: Fastest Completion
- Estimate completion time based on queue length and processing speed
- Select server that will complete first
- Most complex but potentially most efficient

## Implementation Plan

### Phase 1: Environment Configuration
1. **Update `env.py`**
   - Add server cluster configuration functions
   - Support both JSON array and numbered variable formats
   - Maintain backward compatibility

2. **Server Configuration Class**
   ```python
   class ComfyUIServer:
       def __init__(self, name, ip, port, dir_local, dir_remote, priority=1, enabled=True):
           self.name = name
           self.ip = ip
           self.port = port
           self.dir_local = dir_local
           self.dir_remote = dir_remote
           self.priority = priority
           self.enabled = enabled
           self.last_status_check = None
           self.status = 'unknown'
   ```

### Phase 2: Server Management
1. **Server Pool Class**
   ```python
   class ComfyUIServerPool:
       def __init__(self):
           self.servers = []
           self.current_server_index = 0
           self.load_configuration()
       
       def get_available_server(self, strategy='least_loaded'):
           # Implement load balancing strategies
           pass
       
       def update_server_status(self):
           # Update status of all servers
           pass
   ```

2. **Status Monitoring**
   - Periodic status checks
   - Connection health monitoring
   - Automatic failover

### Phase 3: Connection Layer Updates
1. **Update `src/connection.py`**
   - Add server-specific GET/POST methods
   - Implement connection pooling
   - Add retry logic for failed connections

2. **WebSocket Management**
   - Server-specific WebSocket connections
   - Connection failover during execution
   - Proper cleanup of connections

### Phase 4: Execution Layer Updates
1. **Update `src/run.py`**
   - Integrate server pool with submission logic
   - Handle server failover during execution
   - Update progress tracking for multi-server scenarios

2. **Error Handling**
   - Graceful degradation when servers fail
   - Retry logic with different servers
   - User notification of server issues

### Phase 5: User Interface
1. **Server Status Panel**
   - Real-time server status display
   - Queue length indicators
   - Manual server selection option

2. **Configuration Interface**
   - Easy server addition/removal
   - Priority adjustment
   - Enable/disable servers

## Technical Considerations

### Backward Compatibility
- Maintain existing single-server functionality
- Gradual migration path
- Environment variable fallbacks

### Performance Impact
- Status checking overhead (minimal with caching)
- Connection pooling benefits
- Reduced single-point-of-failure

### Error Handling
- Network timeouts
- Server unavailability
- Partial failures during execution

### Security
- Server authentication (if needed)
- Secure configuration storage
- Access control for different servers

## Implementation Timeline

### Week 1: Environment & Configuration
- Update `env.py` with cluster support
- Implement server configuration parsing
- Add backward compatibility layer

### Week 2: Server Management
- Implement `ComfyUIServer` and `ComfyUIServerPool` classes
- Add status checking functionality
- Implement basic load balancing

### Week 3: Connection Layer
- Update connection.py for multi-server support
- Implement connection pooling
- Add retry and failover logic

### Week 4: Execution Integration
- Integrate server pool with run.py
- Update submission logic
- Add error handling and recovery

### Week 5: Testing & Polish
- Comprehensive testing with multiple servers
- Performance optimization
- User interface improvements

## Recommended Approach

**Use Option 1 (JSON Array)** with **Strategy 2 (Least Loaded)** load balancing:

1. **Environment Configuration**: JSON array for flexibility
2. **Load Balancing**: Least loaded server selection
3. **Status Monitoring**: Periodic queue checks with caching
4. **Failover**: Automatic retry with different servers
5. **User Control**: Optional manual server selection

This approach provides the best balance of flexibility, performance, and user control while maintaining backward compatibility with existing single-server setups. 