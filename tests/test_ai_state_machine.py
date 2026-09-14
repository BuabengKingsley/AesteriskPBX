import pytest

from app.ai.state_machine import CallEvent, CallState, _TRANSITIONS, next_state


@pytest.mark.parametrize("state_event", list(_TRANSITIONS))
def test_defined_transitions_round_trip(state_event):
    current, event = state_event
    assert next_state(current, event) == _TRANSITIONS[state_event]


def test_undefined_transition_raises():
    with pytest.raises(ValueError):
        next_state(CallState.COMPLETED, CallEvent.OTP_VERIFIED)


@pytest.mark.parametrize("state", list(CallState))
def test_handoff_requested_works_from_any_state(state):
    assert next_state(state, CallEvent.HANDOFF_REQUESTED) == CallState.HUMAN_HANDOFF


@pytest.mark.parametrize("state", list(CallState))
def test_error_works_from_any_state(state):
    assert next_state(state, CallEvent.ERROR) == CallState.SYSTEM_ERROR


@pytest.mark.parametrize("state", list(CallState))
def test_call_ended_works_from_any_state(state):
    assert next_state(state, CallEvent.CALL_ENDED) == CallState.CALL_TERMINATED
