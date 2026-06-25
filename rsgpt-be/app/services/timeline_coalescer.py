"""Timeline coalescing functionality for converting streaming events into blocks."""

import time


class TimelineCoalescer:
    """Coalesces sequential events into blocks for efficient timeline storage"""

    def __init__(self):
        self.blocks = []
        self.current_block = None
        self.sequence_counter = 0
        self.pending_tools = {}  # tool_call_id -> block

    def process_event(self, event):
        """Process incoming event and coalesce if possible"""

        event_type = event.get('type', '')
        event_data = event.get('data', {})
        timestamp = event.get('timestamp', time.time() * 1000)

        # Thinking events → thinking_block
        if event_type in ['agent.thinking', 'agent.text_output']:
            # Preserve thinking content exactly as received from AI core
            thinking_text = event_data.get('text', event_data.get('content', event_data.get('thinking_text', event_data.get('thinking', ''))))
            is_complete = event_data.get('is_complete', False)

            if self.current_block and self.current_block['type'] == 'thinking_block':
                # If this is the completion event, replace content with full text (not delta)
                # Otherwise append the delta
                if is_complete:
                    # Completion event sends full text, replace instead of append
                    if thinking_text:
                        self.current_block['content'] = thinking_text
                    self.current_block['timestamp_end'] = timestamp
                    self.current_block['is_complete'] = True
                    self._finalize_current_block()
                else:
                    # Streaming delta, append to existing content
                    if thinking_text:
                        self.current_block['content'] += thinking_text
                    self.current_block['timestamp_end'] = timestamp
            else:
                # Start new thinking block
                self._finalize_current_block()
                self.current_block = {
                    'id': f"block_{self.sequence_counter:03d}",
                    'sequence': self.sequence_counter,
                    'type': 'thinking_block',
                    'timestamp_start': timestamp,
                    'timestamp_end': timestamp,
                    'content': thinking_text,
                    'agent_name': event_data.get('agent_name', 'RSInsight Agent'),
                    'is_complete': is_complete
                }

                # If it's already complete, finalize it immediately
                if is_complete:
                    self._finalize_current_block()

        # Message events → message_block
        elif event_type == 'agent.message.delta':
            if self.current_block and self.current_block['type'] == 'message_block':
                # Append to existing block
                self.current_block['content'] += event_data.get('delta', '')
                self.current_block['timestamp_end'] = timestamp
            else:
                # Start new message block
                self._finalize_current_block()
                self.current_block = {
                    'id': f"block_{self.sequence_counter:03d}",
                    'sequence': self.sequence_counter,
                    'type': 'message_block',
                    'timestamp_start': timestamp,
                    'timestamp_end': timestamp,
                    'content': event_data.get('delta', ''),
                    'agent_name': event_data.get('agent_name', 'RSInsight Agent')
                }

        # Tool call → create tool_execution_block (pending result)
        elif event_type in ['agent.tool_execution.started', 'tool.call']:
            # Finalize message blocks before starting tool execution (thinking blocks stay open)
            if self.current_block and self.current_block['type'] == 'message_block':
                self._finalize_current_block()

            tool_call_id = event_data.get('tool_call_id', event_data.get('call_id', 'unknown'))

            # Create tool block and store in pending_tools
            tool_block = {
                'id': f"block_{self.sequence_counter:03d}",
                'sequence': self.sequence_counter,
                'type': 'tool_execution_block',
                'timestamp_start': timestamp,
                'tool_call_id': tool_call_id,
                'tool_name': event_data.get('tool_name', event_data.get('name', 'unknown')),
                'tool_args': event_data.get('tool_args', event_data.get('args', {}))
            }
            self.pending_tools[tool_call_id] = tool_block
            self.blocks.append(tool_block)
            self.sequence_counter += 1

        # Tool result → finalize tool_execution_block
        elif event_type in ['agent.tool_execution.completed', 'agent.tool_execution.failed', 'tool.result', 'tool.error']:
            # Try to match by tool_call_id
            tool_call_id = event_data.get('tool_call_id', event_data.get('call_id'))
            if tool_call_id and tool_call_id in self.pending_tools:
                tool_block = self.pending_tools.pop(tool_call_id)
                tool_block['timestamp_end'] = timestamp
                tool_block['duration_ms'] = (
                    timestamp - tool_block['timestamp_start']
                )
                if event_type in ['agent.tool_execution.completed', 'tool.result']:
                    tool_block['status'] = 'completed'
                    tool_block['output'] = event_data.get('result', event_data.get('output', event_data.get('data')))
                else:
                    tool_block['status'] = 'failed'
                    tool_block['error'] = event_data.get('error', 'Unknown error')

        # Context summarization events → summarization_block
        elif event_type in ['context.summarizing']:
            self._finalize_current_block()
            summarization_block = {
                'id': f"block_{self.sequence_counter:03d}",
                'sequence': self.sequence_counter,
                'type': 'summarization_block',
                'timestamp_start': timestamp,
                'timestamp_end': timestamp,
                'agent_name': 'RSInsight Agent',
                'status': 'in_progress',
                'message_count': event_data.get('message_count')
            }
            self.pending_tools[f"summarization_{event_data.get('session_id', '')}"] = summarization_block
            self.blocks.append(summarization_block)
            self.sequence_counter += 1
        
        elif event_type in ['context.pruning_completed']:
            # Find and finalize the summarization block
            summarization_key = f"summarization_{event_data.get('session_id', '')}"
            if summarization_key in self.pending_tools:
                summarization_block = self.pending_tools.pop(summarization_key)
                summarization_block['timestamp_end'] = timestamp
                summarization_block['status'] = 'completed'
                summarization_block['items_after_pruning'] = event_data.get('items_after_pruning')
        
        # Context pruning error → mark summarization as failed
        elif event_type == 'context.pruning_error':
            summarization_key = f"summarization_{event_data.get('session_id', '')}"
            if summarization_key in self.pending_tools:
                summarization_block = self.pending_tools.pop(summarization_key)
                summarization_block['timestamp_end'] = timestamp
                summarization_block['status'] = 'failed'
                summarization_block['error'] = event_data.get('error', 'Unknown error')
        
        # Agent handoff → agent_transition_block
        elif event_type == 'agent.transition':
            self._finalize_current_block()
            self.blocks.append({
                'id': f"block_{self.sequence_counter:03d}",
                'sequence': self.sequence_counter,
                'type': 'agent_transition_block',
                'timestamp_start': timestamp,
                'timestamp_end': timestamp,
                'from_agent': event_data.get('from_agent', ''),
                'to_agent': event_data.get('to_agent', ''),
                'tool_name': event_data.get('tool_name'),
                'completed': event_data.get('completed', False),
            })
            self.sequence_counter += 1

        # Status events → status_block
        elif event_type == 'agent.workflow.status_changed':
            self._finalize_current_block()
            self.blocks.append({
                'id': f"block_{self.sequence_counter:03d}",
                'sequence': self.sequence_counter,
                'type': 'status_block',
                'timestamp_start': timestamp,
                'timestamp_end': timestamp,
                'status': event_data.get('status', 'unknown'),
                'agent_name': event_data.get('agent_name', 'RSInsight Agent'),
                'description': event_data.get('description')
            })
            self.sequence_counter += 1

        # Workflow start → workflow_start block
        elif event_type == 'agent.workflow.started':
            self._finalize_current_block()
            self.blocks.append({
                'id': f"block_{self.sequence_counter:03d}",
                'sequence': self.sequence_counter,
                'type': 'workflow_start',
                'timestamp_start': timestamp,
                'timestamp_end': timestamp,
                'trace_id': event_data.get('trace_id'),
                'agent_name': event_data.get('agent_name', 'RSInsight Agent')
            })
            self.sequence_counter += 1

        # Workflow end → workflow_end block
        elif event_type == 'agent.workflow.completed':
            self._finalize_current_block()
            self.blocks.append({
                'id': f"block_{self.sequence_counter:03d}",
                'sequence': self.sequence_counter,
                'type': 'workflow_end',
                'timestamp_start': timestamp,
                'timestamp_end': timestamp,
                'trace_id': event_data.get('trace_id'),
                'status': 'completed',
                'total_duration_ms': timestamp - (self.blocks[0]['timestamp_start'] if self.blocks else timestamp)
            })
            self.sequence_counter += 1

        elif event_type == 'agent.workflow.failed':
            self._finalize_current_block()
            self.blocks.append({
                'id': f"block_{self.sequence_counter:03d}",
                'sequence': self.sequence_counter,
                'type': 'workflow_end',
                'timestamp_start': timestamp,
                'timestamp_end': timestamp,
                'trace_id': event_data.get('trace_id'),
                'status': 'failed',
                'error': event_data.get('error'),
                'total_duration_ms': timestamp - (self.blocks[0]['timestamp_start'] if self.blocks else timestamp)
            })
            self.sequence_counter += 1

    def _finalize_current_block(self, is_cancelled=False):
        """Finalize and store the current block"""
        if self.current_block:
            # Ensure timestamp_end is set (for blocks that haven't been updated yet)
            if 'timestamp_end' not in self.current_block:
                self.current_block['timestamp_end'] = self.current_block['timestamp_start']

            # Calculate duration if not already set
            if 'duration_ms' not in self.current_block:
                self.current_block['duration_ms'] = (
                    self.current_block['timestamp_end'] -
                    self.current_block['timestamp_start']
                )

            # For thinking blocks, set completion status
            if self.current_block['type'] == 'thinking_block':
                # Only mark as cancelled if it was actually interrupted (not already complete)
                # If is_complete was already set to True by an event, preserve that
                if 'is_complete' in self.current_block and self.current_block['is_complete']:
                    # Already marked complete by an event, don't override
                    pass
                elif is_cancelled:
                    # Was interrupted by cancellation
                    self.current_block['is_complete'] = False
                    self.current_block['is_cancelled'] = True
                else:
                    # Normal finalization (e.g., when moving to next block type)
                    self.current_block['is_complete'] = True

            self.blocks.append(self.current_block)
            self.current_block = None
            self.sequence_counter += 1

    def get_timeline(self, is_cancelled=False):
        """Get final coalesced timeline"""
        self._finalize_current_block(is_cancelled)

        # Handle any remaining pending tool execution blocks and summarization blocks
        for tool_call_id, tool_block in self.pending_tools.items():
            # Handle summarization blocks
            if tool_block.get('type') == 'summarization_block':
                if tool_block.get('status') == 'in_progress':
                    # Summarization was interrupted
                    tool_block['status'] = 'cancelled'
                    if 'timestamp_end' not in tool_block:
                        tool_block['timestamp_end'] = tool_block['timestamp_start']
            # Handle tool execution blocks
            elif 'status' not in tool_block:
                # Mark incomplete tool executions as cancelled or failed based on response status
                if is_cancelled:
                    tool_block['status'] = 'cancelled'
                    tool_block['error'] = 'Tool execution was cancelled'
                else:
                    tool_block['status'] = 'failed'
                    tool_block['error'] = 'Tool execution was interrupted or timed out'
                # Ensure timestamps are set
                if 'timestamp_end' not in tool_block:
                    tool_block['timestamp_end'] = tool_block['timestamp_start']
                if 'duration_ms' not in tool_block:
                    tool_block['duration_ms'] = 0.0

        # Clear pending tools as we've processed them
        self.pending_tools.clear()

        # Sort blocks by timestamp_start to ensure chronological order
        sorted_blocks = sorted(self.blocks, key=lambda b: b['timestamp_start'])
        return {'blocks': sorted_blocks}

    @staticmethod
    def create_basic_timeline(message_text: str, agent_name: str = 'RSInsight Agent') -> dict:
        """Create a basic timeline with just a message block for regular AI responses"""
        import time
        timestamp = time.time() * 1000

        return {
            'blocks': [{
                'id': 'block_000',
                'sequence': 0,
                'type': 'message_block',
                'timestamp_start': timestamp,
                'timestamp_end': timestamp,
                'duration_ms': 0.0,
                'content': message_text,
                'agent_name': agent_name
            }]
        }
