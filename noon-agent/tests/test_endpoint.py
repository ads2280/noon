import json
import sys
import time
import urllib.request
import urllib.error


BASE_URL = "http://127.0.0.1:8080"


def post_json(path: str, payload: dict) -> dict:
	data = json.dumps(payload).encode("utf-8")
	req = urllib.request.Request(
		url=f"{BASE_URL}{path}",
		data=data,
		headers={"Content-Type": "application/json"},
		method="POST",
	)
	with urllib.request.urlopen(req, timeout=10) as resp:
		return json.loads(resp.read().decode("utf-8"))


def assert_keys(d: dict, keys):
	for k in keys:
		if k not in d:
			raise AssertionError(f"Missing key: {k}")


def test_noop():
	resp = post_json(
		"/calendar-agent/get-args",
		{
			"query": "do nothing thanks",
			"defaultCalendarId": "primary",
			"timeZone": "America/Los_Angeles",
		},
	)
	assert resp["model"]
	# Print operations (expected to be empty)
	print("Operations returned (noop):")
	for i, op in enumerate(resp["operations"], start=1):
		print(f"  {i}. {op.get('op')} -> {json.dumps(op.get('args', {}), default=str)}")
	assert isinstance(resp["operations"], list)
	assert len(resp["operations"]) == 0, f"Expected 0 operations, got {len(resp['operations'])}"
	assert "reasoning" in resp


def test_list_today():
	resp = post_json(
		"/calendar-agent/get-args",
		{
			"query": "what's on my calendar today?",
			"defaultCalendarId": "primary",
			"timeZone": "America/Los_Angeles",
		},
	)
	assert resp["model"]
	ops = resp["operations"]
	# Print all operations with args
	print("Operations returned (today):")
	for i, op in enumerate(ops, start=1):
		print(f"  {i}. {op.get('op')} -> {json.dumps(op.get('args', {}), default=str)}")
	assert isinstance(ops, list) and len(ops) >= 1
	first = ops[0]
	assert first["op"] == "list_events"
	args = first["args"]
	assert_keys(args, ["calendarId", "singleEvents", "maxResults"])
	if args.get("orderBy") == "startTime":
		assert args.get("singleEvents") is True


def test_get_event_details():
	resp = post_json(
		"/calendar-agent/get-args",
		{
			"query": "show me details for event abc123",
			"defaultCalendarId": "primary",
			"timeZone": "America/Los_Angeles",
		},
	)
	ops = resp["operations"]
	# Print all operations with args
	print("Operations returned (details):")
	for i, op in enumerate(ops, start=1):
		print(f"  {i}. {op.get('op')} -> {json.dumps(op.get('args', {}), default=str)}")
	assert any(op["op"] == "get_event" for op in ops)
	get_ops = [op for op in ops if op["op"] == "get_event"]
	args = get_ops[0]["args"]
	assert_keys(args, ["calendarId", "eventId"])
	assert args["eventId"] == "abc123"


def test_broad_search_query():
	resp = post_json(
		"/calendar-agent/get-args",
		{
			"query": "find lunch events next month",
			"defaultCalendarId": "primary",
			"timeZone": "America/Los_Angeles",
		},
	)
	ops = resp["operations"]
	# Print all operations with args
	print("Operations returned (broad search):")
	for i, op in enumerate(ops, start=1):
		print(f"  {i}. {op.get('op')} -> {json.dumps(op.get('args', {}), default=str)}")
	assert len(ops) >= 1
	first = ops[0]
	assert first["op"] == "list_events"
	args = first["args"]
	assert args.get("q") is not None
	assert args["calendarId"] == "primary"


def test_multi_ops_today_and_details():
	resp = post_json(
		"/calendar-agent/get-args",
		{
			"query": "what's on my calendar today? show me details for event abc123",
			"defaultCalendarId": "primary",
			"timeZone": "America/Los_Angeles",
			"maxOperations": 5,
		},
	)
	assert resp["model"]
	ops = resp["operations"]
	assert isinstance(ops, list) and len(ops) >= 2, f"Expected at least 2 operations, got {len(ops)}"
	# Print each operation and its extracted arguments
	print("Operations returned (today + details):")
	for i, op in enumerate(ops, start=1):
		print(f"  {i}. {op.get('op')} -> {json.dumps(op.get('args', {}), default=str)}")
	# Ensure both list and get operations are present and eventId is extracted
	assert any(op["op"] == "list_events" for op in ops), "Expected a list_events operation"
	get_ops = [op for op in ops if op["op"] == "get_event"]
	assert get_ops, "Expected a get_event operation"
	assert get_ops[0]["args"]["eventId"] == "abc123"


def test_multi_ops_next_week_and_details():
	resp = post_json(
		"/calendar-agent/get-args",
		{
			"query": "list my schedule next week and show details for event def456",
			"defaultCalendarId": "primary",
			"timeZone": "America/Los_Angeles",
			"maxOperations": 5,
		},
	)
	assert resp["model"]
	ops = resp["operations"]
	assert isinstance(ops, list) and len(ops) >= 2, f"Expected at least 2 operations, got {len(ops)}"
	# Print each operation and its extracted arguments
	print("Operations returned (next week + details):")
	for i, op in enumerate(ops, start=1):
		print(f"  {i}. {op.get('op')} -> {json.dumps(op.get('args', {}), default=str)}")
	# Ensure both list and get operations are present and eventId is extracted
	assert any(op["op"] == "list_events" for op in ops), "Expected a list_events operation"
	get_ops = [op for op in ops if op["op"] == "get_event"]
	assert get_ops, "Expected a get_event operation"
	assert get_ops[0]["args"]["eventId"] == "def456"


def main():
	# Basic readiness check in case server is just starting
	for _ in range(30):
		try:
			with urllib.request.urlopen(f"{BASE_URL}/", timeout=2) as resp:
				if resp.getcode() == 200:
					break
		except Exception:
			time.sleep(0.2)
	else:
		print("Server not responding at / after waiting.", file=sys.stderr)
		sys.exit(1)

	# Run tests
	tests = [
		test_noop,
		test_list_today,
		test_get_event_details,
		test_broad_search_query,
		test_multi_ops_today_and_details,
		test_multi_ops_next_week_and_details,
	]
	failures = 0
	for t in tests:
		try:
			t()
			print(f"OK: {t.__name__}")
		except AssertionError as e:
			failures += 1
			print(f"FAIL: {t.__name__} -> {e}", file=sys.stderr)
		except urllib.error.HTTPError as e:
			failures += 1
			body = None
			try:
				body = e.read().decode("utf-8")
			except Exception:
				body = "<no body>"
			print(f"HTTP ERROR: {t.__name__} -> {e}\n{body}", file=sys.stderr)
		except Exception as e:
			failures += 1
			print(f"ERROR: {t.__name__} -> {e}", file=sys.stderr)
	if failures:
		print(f"{failures} tests failed", file=sys.stderr)
		sys.exit(1)
	print("All tests passed")


if __name__ == "__main__":
	main()


