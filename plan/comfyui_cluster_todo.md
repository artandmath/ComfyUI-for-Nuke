# ComfyUI Server Cluster Implementation Todo List

## Overview
Implementation todo list for ComfyUI server cluster using Option 1 (JSON array configuration) with least loaded load balancing strategy.

## Environment Variable Format
```bash
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

## Phase 1: Environment Configuration & Core Classes

### 1.1 Update `env.py` with cluster support
- [ ] Add `NUKE_COMFYUI_SERVERS()` function to parse JSON array from environment
- [ ] **Add fallback to current env.py implementation if NUKE_COMFYUI_SERVERS doesn't exist or is empty**
- [ ] Add backward compatibility functions for single server config
- [ ] Add JSON validation and error handling
- [ ] Add default server configuration fallback
- [ ] Add server configuration validation (required fields, valid IP/port)
- [ ] Add fallback to existing single server config if cluster config not found
- [ ] **Handle empty/whitespace-only environment variable values**
- [ ] **Provide clear error messages when falling back to single server mode**

### 1.2 Create `ComfyUIServer` class
- [ ] Create `src/server.py` module
- [ ] Implement `ComfyUIServer` class with attributes:
  - name, ip, port, dir_local, dir_remote, priority, enabled
  - last_status_check, status, queue_length, processing
- [ ] Add `get_status()` method for queue status querying
- [ ] Add `test_connection()` method for health checks
- [ ] Add `update_status()` method for status updates
- [ ] Add `is_available()` method for availability checks

### 1.3 Create `ComfyUIServerPool` class
- [ ] Implement server pool management in `src/server.py`
- [ ] Add `load_configuration()` method from env
- [ ] Add `get_available_server(strategy='least_loaded')` method
- [ ] Add `update_all_server_status()` method
- [ ] Add `get_server_by_name(name)` method
- [ ] Add connection pooling and status caching
- [ ] Add server failover logic

## Phase 2: Connection Layer Updates

### 2.1 Update `src/connection.py`
- [ ] Add server-specific GET/POST methods
- [ ] Modify existing GET/POST to accept server config parameter
- [ ] Add connection retry logic with exponential backoff
- [ ] Add connection timeout handling
- [ ] Add server-specific error handling
- [ ] Maintain backward compatibility with single server calls
- [ ] Add connection health monitoring
- [ ] Update `check_connection()` to work with server pool

### 2.2 WebSocket Management
- [ ] Add server-specific WebSocket connection handling
- [ ] Implement WebSocket connection failover
- [ ] Add WebSocket connection pooling
- [ ] Handle WebSocket reconnection logic
- [ ] Add proper WebSocket cleanup
- [ ] Update WebSocket URL generation for multi-server

## Phase 3: Server Status & Monitoring

### 3.1 Server Status Detection
- [ ] Implement `/queue` endpoint querying for each server
- [ ] Parse queue information (running, pending, completed)
- [ ] Add server health checks using `/system_stats`
- [ ] Implement status caching (5-10 second TTL)
- [ ] Add status update threading for non-blocking operation
- [ ] Add status update error handling

### 3.2 Load Balancing Implementation
- [ ] Implement least loaded strategy in `ComfyUIServerPool`
- [ ] Add queue length comparison logic
- [ ] Add server priority fallback when queues are equal
- [ ] Add server availability filtering (enabled + online)
- [ ] Add load balancing metrics collection
- [ ] Add round-robin fallback if all servers have same load

## Phase 4: Execution Layer Integration

### 4.1 Update `src/run.py`
- [ ] Integrate server pool with submission logic
- [ ] Modify `submit()` function to use server pool
- [ ] Add server selection before submission
- [ ] Handle server failover during execution
- [ ] Update progress tracking for multi-server scenarios
- [ ] Add server-specific error handling in execution
- [ ] Maintain backward compatibility
- [ ] Update `animation_submit()` for multi-server
- [ ] Update `iteration_submit()` for multi-server

### 4.2 Error Handling & Recovery
- [ ] Implement graceful degradation when servers fail
- [ ] Add retry logic with different servers
- [ ] Add user notification of server issues
- [ ] Add execution recovery mechanisms
- [ ] Add detailed error logging
- [ ] Add server-specific error messages

## Phase 5: User Interface & Configuration

### 5.1 Server Status Panel
- [ ] Create server status display panel
- [ ] Show real-time server status (online/offline/error)
- [ ] Display queue length indicators
- [ ] Add server selection dropdown
- [ ] Show server priority and enabled status
- [ ] Add manual server selection option
- [ ] Add server status refresh button

### 5.2 Configuration Interface
- [ ] Create server configuration editor
- [ ] Add server addition/removal functionality
- [ ] Add priority adjustment controls
- [ ] Add enable/disable server toggles
- [ ] Add configuration validation
- [ ] Add configuration import/export
- [ ] Add configuration backup/restore

## Phase 6: Testing & Validation

### 6.1 Unit Testing
- [ ] Test server configuration parsing
- [ ] Test load balancing strategies
- [ ] Test server status detection
- [ ] Test connection failover
- [ ] Test backward compatibility
- [ ] Test JSON validation and error handling

### 6.2 Integration Testing
- [ ] Test with multiple ComfyUI servers
- [ ] Test server failover scenarios
- [ ] Test load balancing with varying loads
- [ ] Test WebSocket connection handling
- [ ] Test error recovery mechanisms
- [ ] Test with single server fallback

### 6.3 Performance Testing
- [ ] Measure status checking overhead
- [ ] Test connection pooling performance
- [ ] Validate load balancing efficiency
- [ ] Test memory usage with multiple servers
- [ ] Test response times with different server counts

## Phase 7: Documentation & Deployment

### 7.1 Documentation
- [ ] Update README with cluster configuration
- [ ] Add server configuration examples
- [ ] Document load balancing strategies
- [ ] Add troubleshooting guide
- [ ] Update installation instructions
- [ ] Add migration guide from single server

### 7.2 Deployment
- [ ] Create migration guide from single server
- [ ] Add configuration validation tools
- [ ] Create server health monitoring scripts
- [ ] Add deployment automation
- [ ] Add configuration backup scripts

## Implementation Priority Order

### High Priority (Core Functionality) - Week 1-2
1. Environment configuration (1.1)
2. Core server classes (1.2, 1.3)
3. Connection layer updates (2.1)
4. Basic load balancing (3.2)
5. Execution integration (4.1)

### Medium Priority (Enhanced Features) - Week 3-4
6. WebSocket management (2.2)
7. Advanced status monitoring (3.1)
8. Error handling (4.2)
9. Basic UI (5.1)

### Low Priority (Polish & Optimization) - Week 5
10. Configuration interface (5.2)
11. Comprehensive testing (6.x)
12. Documentation updates (7.x)

## Technical Requirements

### Dependencies
- JSON parsing (built-in)
- Threading for status updates
- WebSocket connections (existing)
- HTTP requests (existing)

### Backward Compatibility
- **Fallback to current env.py implementation if NUKE_COMFYUI_SERVERS doesn't exist or is empty**
- Single server configuration must continue to work
- Existing environment variables must be respected
- Gradual migration path from single to cluster
- **Automatic detection of missing or invalid cluster configuration**

### Performance Considerations
- Status checking should be non-blocking
- Connection pooling to reduce overhead
- Caching to minimize API calls
- Efficient load balancing algorithms

### Error Handling
- Network timeouts and connection failures
- Server unavailability
- Invalid configuration
- Partial failures during execution

## Success Criteria

- [ ] Multiple ComfyUI servers can be configured via JSON
- [ ] **Fallback to current env.py implementation works when NUKE_COMFYUI_SERVERS is missing or empty**
- [ ] Load balancing works correctly with least loaded strategy
- [ ] Server failover works automatically
- [ ] Backward compatibility is maintained
- [ ] Performance impact is minimal
- [ ] User interface shows server status clearly
- [ ] Error handling is robust and informative 