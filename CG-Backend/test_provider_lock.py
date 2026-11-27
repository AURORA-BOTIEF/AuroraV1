#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lambda"))

from provider_lock import (
    image_provider_for,
    normalize_text_provider,
    providers_for,
    simulate_assignments,
    uses_image_provider,
    _unwrap_event,
)


def test_normalize_text_provider():
    assert normalize_text_provider("bedrock") == "bedrock"
    assert normalize_text_provider("openai") == "openai"
    assert normalize_text_provider("google") == "google"
    assert normalize_text_provider("gemini") == "google"
    assert normalize_text_provider("GEMINI") == "google"
    assert normalize_text_provider(None) == "bedrock"
    assert normalize_text_provider("unknown") == "bedrock"


def test_image_provider_for():
    assert image_provider_for("gpt-image-2") == "openai"
    assert image_provider_for("models/gemini-2.5-flash-image") == "google"
    assert image_provider_for("models/gemini-3-pro-image-preview") == "google"
    assert image_provider_for(None) == "google"
    assert image_provider_for("") == "google"


def test_uses_image_provider():
    assert uses_image_provider("ppt") is False
    assert uses_image_provider("course", content_type="labs") is False
    assert uses_image_provider("course", resume_from="post_theory") is False
    assert uses_image_provider("course", content_type="theory") is True
    assert uses_image_provider("course", content_type="both") is True
    assert uses_image_provider("course", content_type=None) is True


def test_providers_for_user_example_overlap_on_bedrock():
    a = providers_for(
        job_kind="course",
        model_provider="bedrock",
        image_model="models/gemini-2.5-flash-image",
        content_type="both",
    )
    b = providers_for(
        job_kind="course",
        model_provider="bedrock",
        image_model="gpt-image-2",
        content_type="both",
    )
    assert a == ["bedrock", "google"]
    assert b == ["bedrock", "openai"]
    assert set(a) & set(b) == {"bedrock"}


def test_providers_for_no_overlap_can_run_parallel():
    a = providers_for(
        job_kind="course",
        model_provider="bedrock",
        image_model="models/gemini-2.5-flash-image",
        content_type="both",
    )
    b = providers_for(
        job_kind="course",
        model_provider="openai",
        image_model="gpt-image-2",
        content_type="both",
    )
    assert set(a) & set(b) == set()


def test_providers_for_google_text_and_gemini_images_share_google():
    providers = providers_for(
        job_kind="course",
        model_provider="google",
        image_model="models/gemini-3-pro-image-preview",
        content_type="both",
    )
    assert providers == ["google"]


def test_providers_for_openai_text_and_gpt_image_share_openai():
    providers = providers_for(
        job_kind="course",
        model_provider="openai",
        image_model="gpt-image-2",
        content_type="both",
    )
    assert providers == ["openai"]


def test_providers_for_ppt_is_text_only():
    assert providers_for(job_kind="ppt", model_provider="bedrock") == ["bedrock"]
    assert providers_for(
        job_kind="ppt",
        model_provider="openai",
        image_model="models/gemini-2.5-flash-image",
    ) == ["openai"]


def test_providers_for_labs_and_resume_skip_images():
    assert providers_for(
        job_kind="course",
        model_provider="bedrock",
        image_model="models/gemini-2.5-flash-image",
        content_type="labs",
    ) == ["bedrock"]
    assert providers_for(
        job_kind="course",
        model_provider="bedrock",
        image_model="models/gemini-2.5-flash-image",
        resume_from="post_theory",
        content_type="both",
    ) == ["bedrock"]


def test_simulate_fifo_oldest_conflicting_job_wins():
    pending = [
        {"execution_arn": "A", "providers": ["bedrock", "google"]},
        {"execution_arn": "B", "providers": ["bedrock", "openai"]},
    ]
    assigned = simulate_assignments(pending, {})
    assert assigned["bedrock"] == "A"
    assert assigned["google"] == "A"
    assert "openai" not in assigned
    assert assigned.get("openai") is None


def test_simulate_non_overlapping_job_proceeds_behind_held_lock():
    held = {"bedrock": "A"}
    pending = [
        {"execution_arn": "B", "providers": ["bedrock", "openai"]},
        {"execution_arn": "C", "providers": ["openai"]},
    ]
    assigned = simulate_assignments(pending, held)
    assert assigned["bedrock"] == "A"
    assert assigned["openai"] == "C"


def test_simulate_after_holder_releases_oldest_waiter_gets_locks():
    pending = [
        {"execution_arn": "B", "providers": ["bedrock", "openai"]},
        {"execution_arn": "C", "providers": ["openai"]},
    ]
    assigned = simulate_assignments(pending, {})
    assert assigned["bedrock"] == "B"
    assert assigned["openai"] == "B"


def test_simulate_course_and_ppt_same_provider_serialize():
    pending = [
        {"execution_arn": "course", "providers": ["bedrock", "google"]},
        {"execution_arn": "ppt", "providers": ["bedrock"]},
    ]
    assigned = simulate_assignments(pending, {})
    assert assigned["bedrock"] == "course"
    assert assigned["google"] == "course"


def test_simulate_ppt_bedrock_parallel_with_google_course():
    held = {"google": "course"}
    pending = [{"execution_arn": "ppt", "providers": ["bedrock"]}]
    assigned = simulate_assignments(pending, held)
    assert assigned["google"] == "course"
    assert assigned["bedrock"] == "ppt"


def test_unwrap_eventbridge_release():
    event = {
        "source": "aws.states",
        "detail-type": "Step Functions Execution Status Change",
        "detail": {
            "executionArn": "arn:aws:states:us-east-1:1:execution:CourseGeneratorStateMachine:x",
            "status": "FAILED",
        },
    }
    payload = _unwrap_event(event)
    assert payload["action"] == "release"
    assert payload["execution_arn"].endswith(":x")


def test_unwrap_nested_execution_input():
    event = {
        "action": "acquire",
        "job_kind": "course",
        "execution_arn": "arn:exec:1",
        "execution_input": {
            "model_provider": "bedrock",
            "image_model": "gpt-image-2",
            "content_type": "both",
            "project_folder": "20260831-demo",
        },
    }
    payload = _unwrap_event(event)
    assert payload["action"] == "acquire"
    assert payload["job_kind"] == "course"
    assert payload["execution_arn"] == "arn:exec:1"
    assert payload["model_provider"] == "bedrock"
    assert payload["image_model"] == "gpt-image-2"
    assert providers_for(**{
        "job_kind": payload["job_kind"],
        "model_provider": payload["model_provider"],
        "image_model": payload["image_model"],
        "content_type": payload["content_type"],
    }) == ["bedrock", "openai"]
