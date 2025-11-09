# Intent Parser Tests

## Running Tests

### Run all intent parser tests
```bash
pytest tests/unit_tests/test_intent_parser.py -v
```

### Run a specific test class
```bash
pytest tests/unit_tests/test_intent_parser.py::TestTimeInference -v
```

### Run a specific test
```bash
pytest tests/unit_tests/test_intent_parser.py::TestTimeInference::test_coffee_with_only_start_time -v
```

### Run with more detailed output
```bash
pytest tests/unit_tests/test_intent_parser.py -vv
```

### Run with output capture disabled (see print statements)
```bash
pytest tests/unit_tests/test_intent_parser.py -v -s
```

## Test Coverage

The test suite covers:

### ✅ Time Inference (5 tests)
- Coffee meetings default to 1 hour
- Lunch defaults to 12pm with 1.5 hour duration
- Dinner defaults to 7pm with 2 hour duration
- Generic meetings default to 1 hour
- Start and end times never null for create actions

### ✅ Location Inference (4 tests)
- Coffee events get coffee shop locations
- Lunch events get restaurant locations
- Dinner events get restaurant locations
- Explicit locations are respected

### ✅ Friend Email Resolution (2 tests)
- Single friend name resolves to email
- Multiple friend names resolve to emails

### ✅ Timezone Handling (1 test)
- All datetimes are PST timezone-aware

### ✅ CRUD Actions (5 tests)
- Delete action (no required times)
- Delete with event name extraction
- Update action with time inference
- Read action for calendar queries
- Read action for schedule queries

### ✅ Edge Cases (3 tests)
- Brunch gets restaurant and reasonable time
- Explicit durations are handled
- Summary field is populated

### ✅ Model Compatibility (2 tests)
- Default model works
- Custom model parameter accepted

## Determinism

Tests are made deterministic through:
1. **Random seed**: Set to 42 for consistent venue selection
2. **Temperature**: Set to 0.0 for consistent LLM outputs
3. **Fixtures**: `set_random_seed` runs automatically before each test

## Adding New Tests

Use the `get_parser()` helper to ensure deterministic behavior:

```python
@pytest.mark.asyncio
async def test_my_new_feature(self):
    """Test description."""
    parser = get_parser()  # Uses temperature=0 for determinism
    result = await parser.ainvoke({
        "messages": [{"role": "human", "content": "Your test input"}]
    })

    assert result.action == "create"
    # Add your assertions...
```

## Test Results

Current status: **22/22 tests passing** ✅
