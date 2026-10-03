import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from cut_and_cut.core.models import ClipPlan, CutMode, MediaInfo, PlanResult
from cut_and_cut.ui.clip_card import ClipCard
from cut_and_cut.ui.review_page import ReviewPage
from cut_and_cut.ui.config_page import ConfigPage
from cut_and_cut.ui.export_page import ExportPage
from cut_and_cut.ui.main_window import MainWindow
from cut_and_cut.workers.export_worker import ExportItem


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_window_opens(qapp: QApplication) -> None:
    window = MainWindow(Path("/usr/bin/true"), Path("/usr/bin/true"))
    window.show()
    qapp.processEvents()
    assert window.windowTitle() == "Cut Cut"
    assert window._stack.currentWidget() is window._home
    assert window._home._photo.pixmap() is not None
    assert not window._home._photo.pixmap().isNull()
    start_button = next(button for button in window.findChildren(QPushButton) if button.text() == "Começar")
    start_button.click()
    qapp.processEvents()
    assert window._stack.currentWidget() is window._config
    continue_button = next(button for button in window.findChildren(QPushButton) if button.text() == "Continuar")
    continue_button.click()
    qapp.processEvents()
    assert "nome do projeto" in window._config._error.text().lower()
    window.close()
    qapp.processEvents()


def test_form_plans_ten_minute_video_and_blocks_a_long_segment(qapp: QApplication, tmp_path: Path) -> None:
    del qapp
    destination = tmp_path / "Área de destino"
    destination.mkdir()
    source = destination / "vídeo aula.mp4"
    source.write_bytes(b"")

    page = ConfigPage(Path("/usr/bin/true"))
    page._name.setText("Meu Vídeo")
    page._destination.setText(str(destination))
    page._source.blockSignals(True)
    page._source.setText(str(source))
    page._source.blockSignals(False)
    page._duration.setText("00:01:00")
    page._media = MediaInfo(
        path=source,
        duration_s=600,
        width=1920,
        height=1080,
        video_codec="h264",
        audio_codec="aac",
        container="mp4",
    )
    page._probe_state = "ready"

    _config, _media, plan = page._build()
    assert plan.warning is None
    assert len(plan.clips) == 10
    assert [clip.title for clip in plan.clips] == [f"Corte {index:02d}" for index in range(1, 11)]

    page._duration.setText("00:01:30")
    _config, _media, plan = page._build()
    assert len(plan.clips) == 7
    assert plan.clips[-1].shorter is True

    page._duration.setText("00:01:00")
    page._count.setText("12")
    page._media = MediaInfo(
        path=source,
        duration_s=630,
        width=1280,
        height=720,
        video_codec="h264",
        audio_codec=None,
        container="mp4",
    )
    _config, _media, plan = page._build()
    assert len(plan.clips) == 11
    assert plan.warning is not None

    page._duration.setText("00:10:30")
    with pytest.raises(ValueError, match="maior ou igual"):
        page._build()

    page._duration.setText("abc")
    with pytest.raises(ValueError):
        page._build()


def test_new_project_clears_the_form(qapp: QApplication) -> None:
    window = MainWindow(Path("/usr/bin/true"), Path("/usr/bin/true"))
    window._config._name.setText("Aula")
    window._config._duration.setText("00:01:00")
    window._new_project()
    qapp.processEvents()
    assert window._config._name.text() == ""
    assert window._config._duration.hasAcceptableInput() is False
    assert window._stack.currentWidget() is window._config
    window.close()
    qapp.processEvents()


def test_clip_card_accepts_a_new_end(qapp: QApplication) -> None:
    del qapp
    clip = ClipPlan(1, 0, 30, 30, False, "Corte 01")
    card = ClipCard(clip, media_duration_s=600)
    card._end.setText("00:00:45")
    card._commit_range()
    assert card.range_valid is True
    assert clip.end_s == 45
    assert clip.duration_s == 45
    assert card._duration.text() == "Duração 00:00:45"


def test_clip_card_rejects_an_end_outside_the_video(qapp: QApplication) -> None:
    del qapp
    clip = ClipPlan(1, 0, 30, 30, False, "Corte 01")
    card = ClipCard(clip, media_duration_s=60)
    card._end.setText("00:01:30")
    card._commit_range()
    assert card.range_valid is False
    assert clip.end_s == 30
    assert "00:01:00" in card._range_error.text()


def test_clip_card_keeps_a_rounded_precise_end(qapp: QApplication) -> None:
    del qapp
    clip = ClipPlan(1, 0, 89.6, 89.6, True, "Corte 01")
    card = ClipCard(clip, media_duration_s=89.6)
    card._start.setText("00:00:05")
    card._commit_range()
    assert clip.start_s == 5
    assert clip.end_s == pytest.approx(89.6)
    assert card.consume_thumbnail_refresh() is True


def test_review_export_uses_the_adjusted_range(qapp: QApplication, tmp_path: Path) -> None:
    del qapp
    source = tmp_path / "aula.mp4"
    source.write_bytes(b"")
    page = ReviewPage()
    page.show_plan(
        source=source,
        destination=tmp_path,
        project_name="Aula",
        mode=CutMode.PRECISE,
        plan=PlanResult(clips=(ClipPlan(1, 0, 30, 30, False, "Corte 01"),)),
        ffmpeg=Path("/usr/bin/true"),
        media_duration_s=120,
    )
    card = page._cards[0]
    card._start.setText("00:00:10")
    card._end.setText("00:00:50")
    card._commit_range()
    items = page.export_items()
    page.shutdown()
    assert len(items) == 1
    assert items[0].start_s == 10
    assert items[0].duration_s == 40


def test_redo_deletes_generated_files(qapp: QApplication, tmp_path: Path) -> None:
    del qapp
    output = tmp_path / "Meu_Vídeo_01_Corte_01.mp4"
    output.write_text("parcial", encoding="utf-8")
    page = ExportPage()
    page._items = [ExportItem(1, 0, 60, output, "Corte 01")]
    page._delete_outputs()
    assert not output.exists()
