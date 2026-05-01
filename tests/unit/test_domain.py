from types import SimpleNamespace

import pytest

import config as cf
from domain import Borehole, DataFile, Step, configure_domain_dependencies, get_num_file_by_default


def test_get_num_file_by_default_parses_sensor_and_measurement():
    measurement_num, sensor_num = get_num_file_by_default("DEFAULT_A_0mm_5.csv", cf.DEFAULT_SENSOR_AMOUNT)
    assert measurement_num == 5
    assert sensor_num == 0


def test_get_num_file_by_default_returns_invalid_for_bad_name():
    assert get_num_file_by_default("bad.csv", cf.DEFAULT_SENSOR_AMOUNT) == [-1, -1]


def test_datafile_get_xy_dataframe_uses_injected_factory():
    expected = SimpleNamespace(active=True, max_y=12.5, min_y=-3.2, db_file_id="db-1")
    configure_domain_dependencies(
        xy_dataframe_factory=lambda *_args, **_kwargs: expected,
        maxes_dataframe_factory=lambda *_args, **_kwargs: None,
        min_dataframe_factory=lambda *_args, **_kwargs: None,
        warning_handler=lambda *_args, **_kwargs: None,
    )
    data_file = DataFile("DEFAULT_A_0mm_5.csv", "/tmp")

    xy = data_file.get_xy_dataframe()

    assert xy is expected
    assert data_file.max_value == 12.5
    assert data_file.min_value == -3.2
    assert data_file.db_file_id == "db-1"


def test_step_add_file_allows_virtual_when_enabled():
    step = Step(1, "/tmp/section")
    step.add_file("DEFAULT_A_0mm_0.csv", allow_virtual_=True, db_file_id_="f-1")

    assert len(step.data_list) == 1
    assert step.data_list[0].db_file_id == "f-1"


def test_borehole_load_from_db_attaches_files_by_step(db_storage, temp_dir):
    project_id = db_storage.create_project("proj")
    borehole_row = db_storage.get_or_create_borehole_for_project(project_id, "proj")
    borehole_id = borehole_row["borehole_id"]
    db_storage.replace_borehole_structure(
        borehole_id,
        [{"name": "s1", "steps": [{"number": 3}, {"number": 7}]}],
    )
    file_id = db_storage.upsert_file_data(
        borehole_id=borehole_id,
        file_path=str(temp_dir / "DEFAULT_A_0mm_3.csv"),
        file_name="DEFAULT_A_0mm_3.csv",
        part_of_file_id=7,
        payload={"header": {}, "data": {"y": [1]}, "stats": {"max_y": 1, "min_y": 1, "mean_y": 1}},
    )

    borehole = Borehole("proj", str(temp_dir), id_=borehole_id)
    borehole.load_from_db(db_storage, borehole_id)

    steps = borehole.section_list[0].step_list
    step_by_number = {s.number: s for s in steps}
    assert len(step_by_number[7].data_list) == 1
    assert step_by_number[7].data_list[0].db_file_id == file_id
    assert len(step_by_number[3].data_list) == 0

