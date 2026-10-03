from pathlib import Path

from cut_and_cut.core.naming import build_output_path, sanitize_component


def test_preserves_accents_and_replaces_spaces(tmp_path: Path) -> None:
    destination = tmp_path / "Área de Trabalho"
    path = build_output_path(destination, "Meu Vídeo", 1, "Ação especial", ".mp4")
    assert path == destination / "Meu_Vídeo" / "Meu_Vídeo_01_Ação_especial.mp4"


def test_strips_invalid_windows_characters(tmp_path: Path) -> None:
    path = build_output_path(tmp_path, "proj", 2, 'a:b*c?"<>|', "MP4")
    assert path.name == "proj_02_a_b_c.mp4"
    assert path.parent == tmp_path / "proj"


def test_ten_minute_names(tmp_path: Path) -> None:
    paths = [
        build_output_path(tmp_path, "Aula", index, f"Corte {index:02d}", ".mp4")
        for index in range(1, 11)
    ]
    assert [path.name for path in paths] == [
        f"Aula_{index:02d}_Corte_{index:02d}.mp4" for index in range(1, 11)
    ]
    assert {path.parent for path in paths} == {tmp_path / "Aula"}


def test_limits_length_and_reserved_names() -> None:
    long_title = sanitize_component("á" * 80, fallback="corte", max_length=60)
    assert len(long_title) == 60
    assert "á" in long_title
    assert sanitize_component("CON", fallback="corte") == "CON_arquivo"
    assert sanitize_component("...", fallback="corte") == "corte"
    assert sanitize_component("  fim.  ", fallback="corte") == "fim"


def test_extension_from_original(tmp_path: Path) -> None:
    path = build_output_path(tmp_path, "proj", 3, "Corte 03", ".MKV")
    assert path.suffix == ".mkv"
