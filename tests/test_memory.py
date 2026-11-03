from src.memory_store import session_from_disk, summarize_turn, write_session
from src.profile import TravelerProfile


def test_local_summary_and_session_roundtrip(tmp_path):
    summary, mode, error = summarize_turn(None, "", "Delhi to Jaipur", "When do you want to start?")
    assert mode == "local"
    assert error == ""
    assert "Delhi to Jaipur" in summary

    path = tmp_path / "session.json"
    profile = TravelerProfile(cities=["Delhi", "Jaipur"], origin="Delhi", destination="Jaipur", budget=3000)
    messages = [{"role": "user", "content": "Delhi to Jaipur"}]
    write_session(path, profile, messages, summary, mode, error, "")
    loaded, loaded_messages, loaded_summary, loaded_mode, loaded_error, last_plan, route_cities, route_line, route_source = session_from_disk(path)
    assert loaded.cities == ["Delhi", "Jaipur"]
    assert loaded.budget == 3000
    assert loaded_messages == messages
    assert loaded_summary == summary
    assert loaded_mode == "local"
    assert loaded_error == ""
    assert last_plan == ""
    assert route_cities == []
    assert route_line == []
    assert route_source == ""