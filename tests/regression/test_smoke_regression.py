import pytest

from domain import Borehole


@pytest.mark.smoke
def test_smoke_create_save_load_roundtrip(db_storage, temp_dir):
    project_id = db_storage.create_project("smoke")
    borehole_id = db_storage.get_or_create_borehole_for_project(project_id, "smoke")["borehole_id"]

    borehole = Borehole("smoke", str(temp_dir), id_=borehole_id)
    borehole.add_section("s1", depth_=10, length_=3.0)
    borehole.section_list[0].add_step(1)
    file_id = db_storage.upsert_file_data(
        borehole_id=borehole_id,
        file_path=str(temp_dir / "DEFAULT_A_0mm_1.csv"),
        file_name="DEFAULT_A_0mm_1.csv",
        part_of_file_id=1,
        payload={"header": {}, "data": {"y": [1]}, "stats": {"max_y": 1, "min_y": 1, "mean_y": 1}},
    )
    borehole.section_list[0].step_list[0].add_file("DEFAULT_A_0mm_1.csv", allow_virtual_=True, db_file_id_=file_id)
    borehole.save_to_db(db_storage, borehole_id)

    loaded = Borehole("smoke", str(temp_dir), id_=borehole_id)
    loaded.load_from_db(db_storage, borehole_id)

    assert loaded.section_list[0].name == "s1"
    assert loaded.section_list[0].step_list[0].number == 1
    assert loaded.section_list[0].step_list[0].data_list[0].db_file_id == file_id


@pytest.mark.smoke
def test_smoke_graph_links_replace_old_values(db_storage):
    project_id = db_storage.create_project("smoke-graph")
    borehole_id = db_storage.get_or_create_borehole_for_project(project_id, "smoke-graph")["borehole_id"]
    file_id = db_storage.upsert_file_data(
        borehole_id=borehole_id,
        file_path="smoke.csv",
        file_name="smoke.csv",
        part_of_file_id=1,
        payload={"header": {}, "data": {"y": [1]}, "stats": {"max_y": 1, "min_y": 1, "mean_y": 1}},
    )

    db_storage.replace_frequency_characteristics_for_borehole(borehole_id, [(file_id, 1)])
    db_storage.replace_frequency_characteristics_for_borehole(borehole_id, [(file_id, 2)])
    rows = db_storage.cursor.execute(
        "SELECT frequency_characteristic_id FROM frequency_characteristics WHERE borehole_id = ?;",
        (borehole_id,),
    ).fetchall()
    assert [r["frequency_characteristic_id"] for r in rows] == [2]
