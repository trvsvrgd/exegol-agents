from app import main


def _reset_execution_state() -> None:
    with main._state_lock:
        main._execution_state.clear()
        main._execution_state.update(
            {
                "status": "idle",
                "current_node": None,
                "messages": [],
                "current_plan": "",
                "evaluation_result": None,
            }
        )


def test_consume_stream_marks_done_for_regular_events():
    _reset_execution_state()
    stream = [
        (
            "planner",
            {
                "messages": [{"role": "planner", "content": "Task"}],
                "current_plan": "Task",
            },
        ),
        ("coder", {"messages": [{"role": "coder", "content": "Done"}]}),
    ]

    main._consume_stream(stream, thread_id="thread-1")

    with main._state_lock:
        assert main._execution_state["status"] == "done"
        assert main._execution_state["current_node"] == "coder"
        assert main._execution_state["messages"] == [{"role": "coder", "content": "Done"}]
        assert main._execution_state["current_plan"] == "Task"


def test_consume_stream_sets_awaiting_approval_on_interrupt():
    _reset_execution_state()
    stream = [
        (
            "__interrupt__",
            {
                "interrupt": {"question": "approve?"},
                "thread_id": "thread-2",
                "merged": {
                    "messages": [{"role": "planner", "content": "Need approval"}],
                    "current_plan": "Need approval",
                },
            },
        ),
        ("coder", {"messages": [{"role": "coder", "content": "Should not run"}]}),
    ]

    main._consume_stream(stream, thread_id="thread-1")

    with main._state_lock:
        assert main._execution_state["status"] == "awaiting_approval"
        assert main._execution_state["current_node"] == "approval"
        assert main._execution_state["thread_id"] == "thread-2"
        assert main._execution_state["__interrupt__"] == {"question": "approve?"}
        assert main._execution_state["messages"] == [
            {"role": "planner", "content": "Need approval"}
        ]
