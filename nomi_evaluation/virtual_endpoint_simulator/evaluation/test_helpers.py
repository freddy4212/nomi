#!/usr/bin/env python3
"""Quick test for evaluation harness helper functions."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from evaluation.run_evaluation import (LLMJudge, build_playlist_request,
                                       label_match)

# --- Test label_match ---
tests = [
    ("摔倒", "摔倒", True),
    ("跌倒", "摔倒", True),     # synonym
    ("在廚房料理", "料理", True), # substring
    ("站立", "料理", False),
    ("坐著休息", "坐下", True),  # synonym
    ("走路", "走路", True),
    ("打架", "衝突", True),      # synonym
    ("用餐", "吃飯", True),      # synonym
]

print("=== label_match tests ===")
all_pass = True
for pred, gt, expected in tests:
    result = label_match(pred, gt)
    status = "PASS" if result == expected else "FAIL"
    if result != expected:
        all_pass = False
    print(f"  [{status}] match({pred!r}, {gt!r}) = {result} (expected {expected})")

# --- Test build_playlist_request ---
print("\n=== build_playlist_request tests ===")
req = build_playlist_request(
    "test.skeleton", 5000,
    environment={"room": "Kitchen", "temperature": 26.0, "co2": 700}
)
assert req["items"][0]["file_name"] == "test.skeleton"
assert req["items"][0]["duration_ms"] == 5000
assert req["environment_items"][0]["type"] == "manual"
assert req["environment_items"][0]["temperature"] == 26.0
assert req["environment_items"][0]["co2"] == 700
assert req["environment_items"][0]["content"] == "Kitchen"  # room -> content
print("  [PASS] build_playlist_request with environment")

req2 = build_playlist_request("test2.skeleton", 3000, environment=None)
assert len(req2["environment_items"]) == 0
print("  [PASS] build_playlist_request without environment")

# --- Test LLMJudge initialization ---
print("\n=== LLMJudge tests ===")
judge = LLMJudge()
if judge.enabled:
    print("  [INFO] LLM Judge is enabled, testing with real API call...")

    test_scenario = {
        "id": "TEST",
        "name": "Test scenario",
        "skeleton": {"action_code": "A043"},
        "ground_truth": "摔倒",
        "category": "safety",
        "environment": {"room": "Bathroom", "temperature": 26.0, "humidity": 85.0},
    }

    # Test 1: correct prediction
    v1 = judge.evaluate(
        scenario=test_scenario,
        predicted_label="在浴室跌倒",
        analysis="偵測到跌倒動作，位於浴室，濕滑環境增加風險",
        environment_impact="浴室的高濕度增加了跌倒的危險性",
        safety_flag="高風險 - 浴室跌倒",
        had_environment=True,
    )
    print(f"  [{'PASS' if v1['label_correct'] else 'FAIL'}] Correct prediction judged as: {v1['label_correct']}")
    print(f"    reasoning_quality={v1.get('reasoning_quality')}, env_utilized={v1.get('env_utilized')}")
    print(f"    explanation: {v1.get('explanation', '')}")

    # Test 2: wrong prediction
    v2 = judge.evaluate(
        scenario=test_scenario,
        predicted_label="坐著看書",
        analysis="發現安靜的閱讀活動",
        environment_impact="",
        safety_flag=None,
        had_environment=True,
    )
    print(f"  [{'PASS' if not v2['label_correct'] else 'FAIL'}] Wrong prediction judged as: {v2['label_correct']}")
    print(f"    reasoning_quality={v2.get('reasoning_quality')}")
    print(f"    explanation: {v2.get('explanation', '')}")

    print(f"\n  LLM Judge API calls made: {judge.call_count}")

    if v1['label_correct'] and not v2['label_correct']:
        print("  [PASS] LLM Judge correctly distinguished right/wrong predictions")
    else:
        print("  [WARN] LLM Judge may not have judged correctly, check explanations above")
        all_pass = False
else:
    print("  [SKIP] LLM Judge not enabled (missing API key or google-genai)")
    # Test fallback
    v = judge.evaluate(
        scenario={"ground_truth": "摔倒"},
        predicted_label="跌倒",
        analysis="", environment_impact="", safety_flag=None,
        had_environment=False,
    )
    assert v["label_correct"] is True
    assert v["judge_mode"] == "string_match"
    print("  [PASS] Fallback string matching works correctly")

# --- Summary ---
if all_pass:
    print("\nAll tests passed!")
else:
    print("\nSome tests may have issues - check output above")
    sys.exit(1)
