import pytest

from cut_and_cut.core.models import PlanError
from cut_and_cut.core.planner import plan_clips


def test_ten_minutes_of_sixty_seconds_makes_ten_clips() -> None:
    result = plan_clips(600, 60, None)
    assert result.warning is None
    assert len(result.clips) == 10
    assert [(clip.start_s, clip.end_s, clip.shorter) for clip in result.clips] == [
        (index * 60, (index + 1) * 60, False) for index in range(10)
    ]
    assert [clip.title for clip in result.clips] == [f"Corte {index:02d}" for index in range(1, 11)]
    assert all(clip.included for clip in result.clips)


def test_remainder_is_marked_shorter_and_included() -> None:
    result = plan_clips(630, 60, None)
    assert len(result.clips) == 11
    tail = result.clips[-1]
    assert tail.shorter is True
    assert tail.included is True
    assert tail.start_s == 600
    assert tail.end_s == 630
    assert tail.duration_s == 30
    assert all(not clip.shorter for clip in result.clips[:-1])


def test_explicit_count_stops_before_the_tail() -> None:
    result = plan_clips(630, 60, 10)
    assert result.warning is None
    assert len(result.clips) == 10
    assert all(not clip.shorter for clip in result.clips)


def test_count_past_the_video_is_capped_with_a_warning() -> None:
    result = plan_clips(630, 60, 12)
    assert len(result.clips) == 11
    assert result.clips[-1].shorter is True
    assert result.warning is not None
    assert "12" in result.warning
    assert "11" in result.warning


def test_exact_fit_has_no_warning() -> None:
    result = plan_clips(630, 60, 11)
    assert len(result.clips) == 11
    assert result.warning is None


def test_float_noise_does_not_create_a_short_clip() -> None:
    result = plan_clips(120.02, 60, None)
    assert len(result.clips) == 2
    assert all(not clip.shorter for clip in result.clips)


def test_segment_as_long_as_the_video_is_rejected() -> None:
    with pytest.raises(PlanError, match="maior ou igual"):
        plan_clips(600, 600, None)
    with pytest.raises(PlanError, match="maior ou igual"):
        plan_clips(600, 601, 1)


def test_invalid_count_and_durations() -> None:
    with pytest.raises(PlanError):
        plan_clips(600, 60, 0)
    with pytest.raises(PlanError):
        plan_clips(0, 60, None)
    with pytest.raises(PlanError):
        plan_clips(600, 0, None)
