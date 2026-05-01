from types import SimpleNamespace

import pytest

from domain import Borehole
from ui.windows import BoreHoleDialog, BoreholeMenuWindowWidget, FrequencyResponseGraphWindowWidget, WindRoseGraphWindowWidget


@pytest.mark.integration
def test_plot_graph_action_interface_activates_selected_widget():
    borehole_window = BoreholeMenuWindowWidget.__new__(BoreholeMenuWindowWidget)
    active_flags = {"a": None, "b": None}
    borehole_window.borehole_menu_widget = SimpleNamespace(activate=lambda *_args, **_kwargs: None)
    borehole_window.graph_window_widgets = {
        "a": SimpleNamespace(activate=lambda state=True: active_flags.__setitem__("a", state)),
        "b": SimpleNamespace(activate=lambda state=True: active_flags.__setitem__("b", state)),
    }

    borehole_window._BoreholeMenuWindowWidget__plot_graph_action_interface("b")

    assert active_flags["b"] is True


@pytest.mark.integration
def test_borehole_dialog_rebuilds_domain_structure(temp_dir):
    borehole = Borehole("proj", str(temp_dir))
    dialog = BoreHoleDialog.__new__(BoreHoleDialog)
    dialog.borehole = borehole
    data_dir = temp_dir / "sec" / "2"
    data_dir.mkdir(parents=True, exist_ok=True)
    file_path = data_dir / "DEFAULT_A_0mm_1.csv"
    file_path.write_text("stub", encoding="utf-8")
    file_widget = SimpleNamespace(path=str(file_path), id="f1", is_selected=lambda: True)
    step_widget = SimpleNamespace(
        number=2,
        id="st1",
        is_selected=lambda: True,
        file_list=SimpleNamespace(widget_list=[file_widget]),
    )
    section_widget = SimpleNamespace(
        name="sec",
        depth=10,
        length=4.5,
        id="s1",
        is_selected=lambda: True,
        step_list=SimpleNamespace(widget_list=[step_widget]),
    )
    dialog.section_list_widget = SimpleNamespace(widget_list=[section_widget])

    dialog._rebuild_borehole_from_widgets()

    assert len(dialog.borehole.section_list) == 1
    assert dialog.borehole.section_list[0].step_list[0].number == 2
    assert len(dialog.borehole.section_list[0].step_list[0].data_list) == 1


@pytest.mark.integration
def test_frequency_links_persist_by_file_id(db_storage, temp_dir):
    project_id = db_storage.create_project("ui-freq")
    borehole_id = db_storage.get_or_create_borehole_for_project(project_id, "ui-freq")["borehole_id"]
    file_id = db_storage.upsert_file_data(
        borehole_id=borehole_id,
        file_path=str(temp_dir / "DEFAULT_A_0mm_0.csv"),
        file_name="DEFAULT_A_0mm_0.csv",
        part_of_file_id=1,
        payload={"header": {}, "data": {"y": [1]}, "stats": {"max_y": 1, "min_y": 1, "mean_y": 1}},
    )
    borehole = Borehole("ui-freq", str(temp_dir), id_=borehole_id)
    borehole.add_section("s")
    borehole.section_list[0].add_step(1)
    borehole.section_list[0].step_list[0].add_file("DEFAULT_A_0mm_0.csv", allow_virtual_=True, db_file_id_=file_id)

    widget = FrequencyResponseGraphWindowWidget.__new__(FrequencyResponseGraphWindowWidget)
    widget.borehole_window = SimpleNamespace(
        main_window=SimpleNamespace(db=db_storage),
        borehole_id=borehole_id,
        borehole=borehole,
    )

    widget._persist_frequency_characteristics_links()
    rows = db_storage.cursor.execute(
        "SELECT file_id, frequency_characteristic_id FROM frequency_characteristics WHERE borehole_id = ?;",
        (borehole_id,),
    ).fetchall()
    assert [(r["file_id"], r["frequency_characteristic_id"]) for r in rows] == [(file_id, 0)]


@pytest.mark.integration
def test_wind_rose_links_persist_measurement_and_sensor(db_storage, temp_dir):
    project_id = db_storage.create_project("ui-wind")
    borehole_id = db_storage.get_or_create_borehole_for_project(project_id, "ui-wind")["borehole_id"]
    file_id = db_storage.upsert_file_data(
        borehole_id=borehole_id,
        file_path=str(temp_dir / "DEFAULT_A_0mm_5.csv"),
        file_name="DEFAULT_A_0mm_5.csv",
        part_of_file_id=1,
        payload={"header": {}, "data": {"y": [1]}, "stats": {"max_y": 1, "min_y": 1, "mean_y": 1}},
    )
    borehole = Borehole("ui-wind", str(temp_dir), id_=borehole_id)
    borehole.add_section("s")
    borehole.section_list[0].add_step(1)
    borehole.section_list[0].step_list[0].add_file("DEFAULT_A_0mm_5.csv", allow_virtual_=True, db_file_id_=file_id)

    widget = WindRoseGraphWindowWidget.__new__(WindRoseGraphWindowWidget)
    widget.borehole_window = SimpleNamespace(
        main_window=SimpleNamespace(db=db_storage),
        borehole_id=borehole_id,
        borehole=borehole,
    )

    widget._persist_wind_rose_links()
    rows = db_storage.cursor.execute(
        "SELECT file_id, wind_rose_id, measurement_id FROM wind_roses WHERE borehole_id = ?;",
        (borehole_id,),
    ).fetchall()
    assert [(r["file_id"], r["wind_rose_id"], r["measurement_id"]) for r in rows] == [(file_id, 0, 5)]
