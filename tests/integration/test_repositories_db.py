import pytest

from domain import Borehole


@pytest.mark.integration
def test_db_first_project_structure_roundtrip(db_storage, temp_dir):
    project_id = db_storage.create_project("DB-first")
    borehole_row = db_storage.get_or_create_borehole_for_project(project_id, "DB-first")
    borehole_id = borehole_row["borehole_id"]

    borehole = Borehole("DB-first", str(temp_dir), id_=borehole_id)
    borehole.add_section("sec-1", depth_=100, length_=4.2)
    borehole.section_list[0].add_step(1)
    borehole.section_list[0].add_step(2)
    borehole.save_to_db(db_storage, borehole_id)

    loaded = Borehole("DB-first", str(temp_dir), id_=borehole_id)
    loaded.load_from_db(db_storage, borehole_id)

    assert len(loaded.section_list) == 1
    assert loaded.section_list[0].name == "sec-1"
    assert sorted(step.number for step in loaded.section_list[0].step_list) == [1, 2]


@pytest.mark.integration
def test_files_repository_upsert_and_list(db_storage, temp_dir):
    project_id = db_storage.create_project("files")
    borehole_id = db_storage.get_or_create_borehole_for_project(project_id, "files")["borehole_id"]

    payload = {"header": {}, "data": {"y": [1]}, "stats": {"max_y": 1, "min_y": 1, "mean_y": 1}}
    file_id = db_storage.upsert_file_data(
        borehole_id=borehole_id,
        file_path=str(temp_dir / "DEFAULT_A_0mm_1.csv"),
        file_name="DEFAULT_A_0mm_1.csv",
        part_of_file_id=1,
        payload=payload,
    )
    assert file_id

    updated = db_storage.upsert_file_data(
        borehole_id=borehole_id,
        file_path=str(temp_dir / "DEFAULT_A_0mm_1.csv"),
        file_name="DEFAULT_A_0mm_1.csv",
        part_of_file_id=2,
        payload=payload,
        file_id=file_id,
    )
    assert updated == file_id

    rows = db_storage.list_files_for_borehole(borehole_id)
    assert len(rows) == 1
    assert rows[0]["part_of_file_id"] == 2


@pytest.mark.integration
def test_graph_link_tables_are_replaced(db_storage):
    project_id = db_storage.create_project("graphs")
    borehole_id = db_storage.get_or_create_borehole_for_project(project_id, "graphs")["borehole_id"]
    file_id = db_storage.upsert_file_data(
        borehole_id=borehole_id,
        file_path="f.csv",
        file_name="f.csv",
        part_of_file_id=1,
        payload={"header": {}, "data": {"y": [1]}, "stats": {"max_y": 1, "min_y": 1, "mean_y": 1}},
    )

    db_storage.replace_frequency_characteristics_for_borehole(borehole_id, [(file_id, 3)])
    db_storage.replace_frequency_characteristics_for_borehole(borehole_id, [(file_id, 2)])
    freq_rows = db_storage.cursor.execute(
        "SELECT frequency_characteristic_id FROM frequency_characteristics WHERE borehole_id = ?;",
        (borehole_id,),
    ).fetchall()
    assert [row["frequency_characteristic_id"] for row in freq_rows] == [2]

    db_storage.replace_wind_roses_for_borehole(borehole_id, [(file_id, 4, 9)])
    db_storage.replace_wind_roses_for_borehole(borehole_id, [(file_id, 7, 11)])
    wind_rows = db_storage.cursor.execute(
        "SELECT wind_rose_id, measurement_id FROM wind_roses WHERE borehole_id = ?;",
        (borehole_id,),
    ).fetchall()
    assert [(r["wind_rose_id"], r["measurement_id"]) for r in wind_rows] == [(7, 11)]
