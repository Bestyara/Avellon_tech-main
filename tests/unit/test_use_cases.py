import os

from use_cases import FileConverter, FileDirector, XYDataFrame, is_float, try_create_dir


def test_is_float_handles_valid_and_invalid_values():
    assert is_float("1.25")
    assert is_float("-3")
    assert not is_float("text")


def test_try_create_dir_creates_unique_folder_names(temp_dir):
    first = try_create_dir(str(temp_dir), "Converted data")
    second = try_create_dir(str(temp_dir), "Converted data")

    assert os.path.basename(first) == "Converted data"
    assert os.path.basename(second) == "Converted data (0)"


def test_file_converter_default_name_generation():
    converter = FileConverter("/tmp/src.csv", "/tmp", sensor_num_=2, crash_deep_=15, measurement_num_=11)
    assert converter.new_basename == "DEFAULT_C_15mm_B.csv"


def test_file_director_stops_after_limit(monkeypatch, temp_dir):
    calls = []

    class StubConverter:
        def __init__(self, filename, save_dir, sensor_num, crash_deep, measurement_num):
            calls.append((filename, measurement_num))

        def convert(self):
            return True

    monkeypatch.setattr("use_cases.FileConverter", StubConverter)
    files = [str(temp_dir / f"f{i}.csv") for i in range(5)]
    director = FileDirector(files, sensor_num_=0, crash_deep_=1, start_measurement_num_=35, converted_folder_path_=str(temp_dir))

    assert director.convert()
    assert [m for _, m in calls] == [35, 36]


def test_xy_dataframe_load_from_db_row():
    xy = XYDataFrame.__new__(XYDataFrame)
    xy.active = False
    xy.data = None
    xy.header = None
    xy.max_y = None
    xy.min_y = None
    xy.mean_y = None
    xy.db_file_id = None

    ok = xy._load_from_db_row(
        {
            "file_id": "f-1",
            "data": {
                "header": {"Data Uint": "mV"},
                "data": {"y": [1, 2, 3]},
                "stats": {"max_y": 3, "min_y": 1, "mean_y": 2},
            },
        }
    )

    assert ok
    assert xy.db_file_id == "f-1"
    assert xy.max_y == 3
