"""Tests for TimelineCoalescer functionality."""

import time
import pytest
from app.services.timeline_coalescer import TimelineCoalescer


class TestTimelineCoalescer:
    """Test the TimelineCoalescer class."""

    def test_empty_coalescer(self):
        """Test that an empty coalescer returns empty timeline."""
        coalescer = TimelineCoalescer()
        timeline = coalescer.get_timeline()
        assert timeline == {'blocks': []}

    def test_thinking_block_coalescing(self):
        """Test that consecutive thinking events are coalesced into one block."""
        coalescer = TimelineCoalescer()

        events = [
            {
                'type': 'agent.thinking',
                'data': {'text': 'First thought', 'agent_name': 'TestAgent'},
                'timestamp': 1000
            },
            {
                'type': 'agent.thinking',
                'data': {'text': 'Second thought', 'agent_name': 'TestAgent'},
                'timestamp': 1100
            }
        ]

        for event in events:
            coalescer.process_event(event)

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 1
        block = timeline['blocks'][0]
        assert block['type'] == 'thinking_block'
        assert block['content'] == 'First thoughtSecond thought'
        assert block['agent_name'] == 'TestAgent'
        assert block['timestamp_start'] == 1000
        assert block['timestamp_end'] == 1100
        assert block['duration_ms'] == 100
        assert block['is_complete'] == True

    def test_message_block_coalescing(self):
        """Test that consecutive message delta events are coalesced into one block."""
        coalescer = TimelineCoalescer()

        events = [
            {
                'type': 'agent.message.delta',
                'data': {'delta': 'Hello ', 'agent_name': 'TestAgent'},
                'timestamp': 2000
            },
            {
                'type': 'agent.message.delta',
                'data': {'delta': 'world!', 'agent_name': 'TestAgent'},
                'timestamp': 2100
            }
        ]

        for event in events:
            coalescer.process_event(event)

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 1
        block = timeline['blocks'][0]
        assert block['type'] == 'message_block'
        assert block['content'] == 'Hello world!'
        assert block['agent_name'] == 'TestAgent'

    def test_tool_execution_block(self):
        """Test tool execution block creation and completion."""
        coalescer = TimelineCoalescer()

        # Tool start
        coalescer.process_event({
            'type': 'agent.tool_execution.started',
            'data': {
                'tool_call_id': 'call123',
                'tool_name': 'search_knowledge',
                'tool_args': {'query': 'test'}
            },
            'timestamp': 3000
        })

        # Tool completion with matching tool_call_id
        coalescer.process_event({
            'type': 'agent.tool_execution.completed',
            'data': {'tool_call_id': 'call123', 'result': 'success'},
            'timestamp': 3200
        })

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 1
        block = timeline['blocks'][0]
        assert block['type'] == 'tool_execution_block'
        assert block['tool_call_id'] == 'call123'
        assert block['tool_name'] == 'search_knowledge'
        assert block['tool_args'] == {'query': 'test'}
        assert block['status'] == 'completed'
        assert block['output'] == 'success'
        assert block['duration_ms'] == 200

    def test_workflow_blocks(self):
        """Test workflow start and end blocks."""
        coalescer = TimelineCoalescer()

        # Workflow start
        coalescer.process_event({
            'type': 'agent.workflow.started',
            'data': {'trace_id': 'trace123', 'agent_name': 'TestAgent'},
            'timestamp': 1000
        })

        # Workflow end
        coalescer.process_event({
            'type': 'agent.workflow.completed',
            'data': {'trace_id': 'trace123'},
            'timestamp': 1500
        })

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 2

        start_block = timeline['blocks'][0]
        assert start_block['type'] == 'workflow_start'
        assert start_block['trace_id'] == 'trace123'
        assert start_block['agent_name'] == 'TestAgent'

        end_block = timeline['blocks'][1]
        assert end_block['type'] == 'workflow_end'
        assert end_block['status'] == 'completed'
        assert end_block['total_duration_ms'] == 500

    def test_mixed_event_types(self):
        """Test that different event types create separate blocks."""
        coalescer = TimelineCoalescer()

        events = [
            # Workflow start
            {'type': 'agent.workflow.started', 'data': {'trace_id': 'trace123'}, 'timestamp': 1000},

            # Thinking
            {'type': 'agent.thinking', 'data': {'text': 'Thinking...', 'agent_name': 'Agent'}, 'timestamp': 1100},

            # Message
            {'type': 'agent.message.delta', 'data': {'delta': 'Hello', 'agent_name': 'Agent'}, 'timestamp': 1200},

            # Tool execution
            {'type': 'agent.tool_execution.started', 'data': {'tool_call_id': 'call1', 'tool_name': 'search'}, 'timestamp': 1300},
            {'type': 'agent.tool_execution.completed', 'data': {}, 'timestamp': 1400},

            # Workflow end
            {'type': 'agent.workflow.completed', 'data': {'trace_id': 'trace123'}, 'timestamp': 1500}
        ]

        for event in events:
            coalescer.process_event(event)

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 5
        block_types = [block['type'] for block in timeline['blocks']]
        assert block_types == [
            'workflow_start',
            'thinking_block',
            'message_block',        # Message (1200) comes before tool (1300)
            'tool_execution_block',
            'workflow_end'
        ]

    def test_unknown_event_type(self):
        """Test that unknown event types are ignored."""
        coalescer = TimelineCoalescer()

        coalescer.process_event({
            'type': 'unknown.event',
            'data': {},
            'timestamp': 1000
        })

        timeline = coalescer.get_timeline()
        assert timeline == {'blocks': []}

    def test_incomplete_tool_execution(self):
        """Test that incomplete tool executions are marked as failed."""
        coalescer = TimelineCoalescer()

        # Start a tool execution but don't complete it
        coalescer.process_event({
            'type': 'agent.tool_execution.started',
            'data': {
                'tool_call_id': 'call123',
                'tool_name': 'search_knowledge',
                'tool_args': {'query': 'test'}
            },
            'timestamp': 3000
        })

        # Get timeline (this should mark incomplete tools as failed)
        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 1
        block = timeline['blocks'][0]
        assert block['type'] == 'tool_execution_block'
        assert block['status'] == 'failed'
        assert block['error'] == 'Tool execution was interrupted or timed out'
        assert 'timestamp_end' in block
        assert 'duration_ms' in block

    def test_alternative_data_structures(self):
        """Test that coalescer handles different field names for the same data."""
        coalescer = TimelineCoalescer()

        # Test thinking with thinking_text field (actual AI core format)
        coalescer.process_event({
            'type': 'agent.thinking',
            'data': {'thinking_text': 'Actual thinking content from AI core', 'agent_name': 'RSInsight Agent', 'is_complete': True},
            'timestamp': 1000
        })

        # Test tool with different field names
        coalescer.process_event({
            'type': 'tool.call',
            'data': {'call_id': 'call456', 'name': 'web_search', 'args': {'query': 'test'}},
            'timestamp': 2000
        })

        coalescer.process_event({
            'type': 'tool.result',
            'data': {'call_id': 'call456', 'output': 'Search results'},
            'timestamp': 2500
        })

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 2

        thinking_block = timeline['blocks'][0]
        assert thinking_block['type'] == 'thinking_block'
        assert thinking_block['content'] == 'Actual thinking content from AI core'

        tool_block = timeline['blocks'][1]
        assert tool_block['type'] == 'tool_execution_block'
        assert tool_block['tool_call_id'] == 'call456'
        assert tool_block['tool_name'] == 'web_search'
        assert tool_block['status'] == 'completed'
        assert tool_block['output'] == 'Search results'

    def test_empty_thinking_events(self):
        """Test that thinking events with empty content still create timing blocks."""
        coalescer = TimelineCoalescer()

        # Simulate thinking events with empty content (what might be happening)
        coalescer.process_event({
            'type': 'agent.thinking',
            'data': {'thinking_text': '', 'agent_name': 'RSInsight Agent', 'is_complete': False},
            'timestamp': 1000
        })

        coalescer.process_event({
            'type': 'agent.thinking',
            'data': {'thinking_text': '', 'agent_name': 'RSInsight Agent', 'is_complete': True},
            'timestamp': 1500
        })

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 1
        thinking_block = timeline['blocks'][0]
        assert thinking_block['type'] == 'thinking_block'
        assert thinking_block['content'] == ''  # Empty content
        assert thinking_block['duration_ms'] == 500  # But timing is preserved

    def test_create_basic_timeline(self):
        """Test creating a basic timeline for regular AI messages"""
        message_text = "This is a regular AI response without streaming events."

        timeline = TimelineCoalescer.create_basic_timeline(message_text)

        assert 'blocks' in timeline
        assert len(timeline['blocks']) == 1

        block = timeline['blocks'][0]
        assert block['id'] == 'block_000'
        assert block['sequence'] == 0
        assert block['type'] == 'message_block'
        assert block['content'] == message_text
        assert block['agent_name'] == 'RSInsight Agent'
        assert block['duration_ms'] == 0.0

        # Check timestamps are reasonable (recent)
        assert block['timestamp_start'] > 0
        assert block['timestamp_end'] == block['timestamp_start']

    def test_create_basic_timeline_custom_agent(self):
        """Test creating a basic timeline with custom agent name"""
        message_text = "Response from custom agent"
        agent_name = "Custom Agent"

        timeline = TimelineCoalescer.create_basic_timeline(message_text, agent_name)

        block = timeline['blocks'][0]
        assert block['content'] == message_text
        assert block['agent_name'] == agent_name

    def test_cancelled_response_handling(self):
        """Test that cancelled responses properly mark incomplete blocks as cancelled"""
        coalescer = TimelineCoalescer()

        # Add some events
        coalescer.process_event({
            'type': 'agent.thinking',
            'data': {'text': 'Thinking about this...', 'agent_name': 'RSInsight Agent'},
            'timestamp': 1000
        })

        coalescer.process_event({
            'type': 'agent.tool_execution.started',
            'data': {'tool_call_id': 'call_123', 'tool_name': 'search_knowledge'},
            'timestamp': 1500
        })

        # Get timeline as if cancelled
        timeline = coalescer.get_timeline(is_cancelled=True)

        assert len(timeline['blocks']) == 2

        # Check thinking block is marked as cancelled
        thinking_block = timeline['blocks'][0]
        assert thinking_block['type'] == 'thinking_block'
        assert thinking_block['is_complete'] == False
        assert thinking_block['is_cancelled'] == True

        # Check tool execution is marked as cancelled
        tool_block = timeline['blocks'][1]
        assert tool_block['type'] == 'tool_execution_block'
        assert tool_block['status'] == 'cancelled'
        assert tool_block['error'] == 'Tool execution was cancelled'

    def test_cancelled_during_tool_execution(self):
        """Test that when cancelled during tool execution, completed thinking stays complete"""
        coalescer = TimelineCoalescer()

        # Thinking starts
        coalescer.process_event({
            'type': 'agent.thinking',
            'data': {'text': 'Let me search for that...', 'agent_name': 'RSInsight Agent'},
            'timestamp': 1000
        })

        # Thinking completes
        coalescer.process_event({
            'type': 'agent.thinking',
            'data': {'text': '', 'is_complete': True, 'agent_name': 'RSInsight Agent'},
            'timestamp': 1500
        })

        # Tool execution starts
        coalescer.process_event({
            'type': 'agent.tool_execution.started',
            'data': {'tool_call_id': 'call_123', 'tool_name': 'search_knowledge'},
            'timestamp': 2000
        })

        # User cancels during tool execution
        timeline = coalescer.get_timeline(is_cancelled=True)

        assert len(timeline['blocks']) == 2

        # Check thinking block remains complete (not cancelled)
        thinking_block = timeline['blocks'][0]
        assert thinking_block['type'] == 'thinking_block'
        assert thinking_block['is_complete'] == True
        assert thinking_block.get('is_cancelled') is None or thinking_block.get('is_cancelled') == False

        # Check tool execution is marked as cancelled
        tool_block = timeline['blocks'][1]
        assert tool_block['type'] == 'tool_execution_block'
        assert tool_block['status'] == 'cancelled'
        assert tool_block['error'] == 'Tool execution was cancelled'

    def test_failed_response_handling(self):
        """Test that failed responses mark incomplete blocks as failed (not cancelled)"""
        coalescer = TimelineCoalescer()

        # Add some events
        coalescer.process_event({
            'type': 'agent.thinking',
            'data': {'text': 'Thinking about this...', 'agent_name': 'RSInsight Agent'},
            'timestamp': 1000
        })

        coalescer.process_event({
            'type': 'agent.tool_execution.started',
            'data': {'tool_call_id': 'call_123', 'tool_name': 'search_knowledge'},
            'timestamp': 1500
        })

        # Get timeline as if failed (not cancelled)
        timeline = coalescer.get_timeline(is_cancelled=False)

        assert len(timeline['blocks']) == 2

        # Check thinking block is marked as complete (not cancelled)
        thinking_block = timeline['blocks'][0]
        assert thinking_block['type'] == 'thinking_block'
        assert thinking_block['is_complete'] == True
        assert thinking_block.get('is_cancelled') is None

        # Check tool execution is marked as failed
        tool_block = timeline['blocks'][1]
        assert tool_block['type'] == 'tool_execution_block'
        assert tool_block['status'] == 'failed'
        assert tool_block['error'] == 'Tool execution was interrupted or timed out'

    def test_message_blocks_separated_by_tool_calls(self):
        """Test that message blocks are separated when tool calls occur between message deltas"""
        coalescer = TimelineCoalescer()

        events = [
            # First message block
            {'type': 'agent.message.delta', 'data': {'delta': 'Hello ', 'agent_name': 'Agent'}, 'timestamp': 1000},
            {'type': 'agent.message.delta', 'data': {'delta': 'world!', 'agent_name': 'Agent'}, 'timestamp': 1100},

            # Tool execution separates message blocks
            {'type': 'agent.tool_execution.started', 'data': {'tool_call_id': 'call1', 'tool_name': 'search'}, 'timestamp': 1200},
            {'type': 'agent.tool_execution.completed', 'data': {'tool_call_id': 'call1', 'result': 'success'}, 'timestamp': 1300},

            # Second message block (should be separate from first)
            {'type': 'agent.message.delta', 'data': {'delta': 'How are you?', 'agent_name': 'Agent'}, 'timestamp': 1400},
        ]

        for event in events:
            coalescer.process_event(event)

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 3

        # Check first message block
        first_message = timeline['blocks'][0]
        assert first_message['type'] == 'message_block'
        assert first_message['content'] == 'Hello world!'
        assert first_message['sequence'] == 0

        # Check tool execution block
        tool_block = timeline['blocks'][1]
        assert tool_block['type'] == 'tool_execution_block'
        assert tool_block['sequence'] == 1

        # Check second message block (separate from first)
        second_message = timeline['blocks'][2]
        assert second_message['type'] == 'message_block'
        assert second_message['content'] == 'How are you?'
        assert second_message['sequence'] == 2

    def test_context_summarization_events(self):
        """Test that context summarization events create summarization blocks."""
        coalescer = TimelineCoalescer()

        events = [
            # Summarization started
            {
                'type': 'context.summarizing',
                'data': {'session_id': 'session123', 'message_count': 10},
                'timestamp': 1000
            },
            # Summarization completed
            {
                'type': 'context.pruning_completed',
                'data': {'session_id': 'session123', 'items_after_pruning': 5},
                'timestamp': 2000
            }
        ]

        for event in events:
            coalescer.process_event(event)

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 1
        block = timeline['blocks'][0]
        assert block['type'] == 'summarization_block'
        assert block['status'] == 'completed'
        assert block['message_count'] == 10
        assert block['items_after_pruning'] == 5
        assert block['timestamp_start'] == 1000
        assert block['timestamp_end'] == 2000

    def test_context_summarization_error(self):
        """Test that context pruning errors mark summarization as failed."""
        coalescer = TimelineCoalescer()

        events = [
            # Summarization started
            {
                'type': 'context.summarizing',
                'data': {'session_id': 'session456'},
                'timestamp': 1000
            },
            # Summarization failed
            {
                'type': 'context.pruning_error',
                'data': {'session_id': 'session456', 'error': 'LLM rate limited'},
                'timestamp': 1500
            }
        ]

        for event in events:
            coalescer.process_event(event)

        timeline = coalescer.get_timeline()

        assert len(timeline['blocks']) == 1
        block = timeline['blocks'][0]
        assert block['type'] == 'summarization_block'
        assert block['status'] == 'failed'
        assert block['error'] == 'LLM rate limited'
        assert block['timestamp_end'] == 1500

    def test_context_summarization_cancelled(self):
        """Test that incomplete summarization is marked as cancelled when stream is cancelled."""
        coalescer = TimelineCoalescer()

        # Start summarization but don't complete it
        coalescer.process_event({
            'type': 'context.summarizing',
            'data': {'session_id': 'session789'},
            'timestamp': 1000
        })

        # Get timeline with cancellation flag
        timeline = coalescer.get_timeline(is_cancelled=True)

        assert len(timeline['blocks']) == 1
        block = timeline['blocks'][0]
        assert block['type'] == 'summarization_block'
        assert block['status'] == 'cancelled'

    def test_summarization_mixed_with_other_events(self):
        """Test summarization events interleaved with other event types."""
        coalescer = TimelineCoalescer()

        events = [
            # Thinking
            {'type': 'agent.thinking', 'data': {'text': 'Planning...', 'is_complete': True}, 'timestamp': 1000},
            # Summarization during tool execution
            {'type': 'context.summarizing', 'data': {'session_id': 'abc'}, 'timestamp': 1500},
            {'type': 'agent.tool_execution.started', 'data': {'tool_call_id': 't1', 'tool_name': 'search'}, 'timestamp': 1600},
            {'type': 'context.pruning_completed', 'data': {'session_id': 'abc'}, 'timestamp': 1800},
            {'type': 'agent.tool_execution.completed', 'data': {'tool_call_id': 't1', 'result': 'found'}, 'timestamp': 2000},
            # Message after
            {'type': 'agent.message.delta', 'data': {'delta': 'Done!'}, 'timestamp': 2100},
        ]

        for event in events:
            coalescer.process_event(event)

        timeline = coalescer.get_timeline()

        # Should have: thinking, summarization, tool, message
        assert len(timeline['blocks']) == 4
        block_types = [b['type'] for b in timeline['blocks']]
        assert block_types == ['thinking_block', 'summarization_block', 'tool_execution_block', 'message_block']
        
        # Check summarization completed
        summarization_block = timeline['blocks'][1]
        assert summarization_block['status'] == 'completed'
