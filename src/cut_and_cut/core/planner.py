from cut_and_cut.core.models import ClipPlan, PlanError, PlanResult

# Ignore a leftover shorter than this so float noise does not become a clip.
_REMAINDER_EPSILON_S = 0.05


def plan_clips(duration_s: float, segment_s: float, count: int | None) -> PlanResult:
    """Split ``duration_s`` into fixed-length clips.

    An empty count keeps every full segment. A trailing piece shorter than the
    requested length is included and marked ``shorter``. A count past what the
    video can hold is capped and reported in ``warning``.
    """
    if duration_s <= 0:
        raise PlanError("A duração do vídeo precisa ser maior que zero.")
    if segment_s <= 0:
        raise PlanError("A duração de cada corte precisa ser maior que zero.")
    if segment_s >= duration_s:
        raise PlanError("A duração de cada corte é maior ou igual à duração do vídeo.")
    if count is not None and count < 1:
        raise PlanError("A quantidade de cortes precisa ser um número inteiro maior que zero.")

    available = _available_segments(duration_s, segment_s)
    warning = None
    if count is None:
        selected = available
    elif count > len(available):
        selected = available
        warning = (
            f"A quantidade pedida ({count}) é maior do que o vídeo comporta "
            f"({len(available)}). Os cortes foram limitados a {len(available)}."
        )
    else:
        selected = available[:count]

    clips = tuple(
        ClipPlan(
            index=index,
            start_s=start,
            end_s=end,
            duration_s=end - start,
            shorter=shorter,
            title=f"Corte {index:02d}",
        )
        for index, (start, end, shorter) in enumerate(selected, start=1)
    )
    return PlanResult(clips=clips, warning=warning)


def _available_segments(duration_s: float, segment_s: float) -> list[tuple[float, float, bool]]:
    full_count = int(duration_s // segment_s)
    segments: list[tuple[float, float, bool]] = []
    for index in range(full_count):
        start = index * segment_s
        segments.append((start, start + segment_s, False))

    remainder = duration_s - full_count * segment_s
    if remainder > _REMAINDER_EPSILON_S:
        start = full_count * segment_s
        segments.append((start, duration_s, True))
    return segments
