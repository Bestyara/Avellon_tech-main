import json
import os
import pathlib
from typing import Any, Optional
from uuid import uuid4

import numpy as np
import pandas as pd

import config as cf
from repositories import DbStorage
from domain import Borehole, DataFile, Section, Step, configure_domain_dependencies
from ui.common import MyWarning, MessageBox, get_num_file_by_default


class AbstractDataFrame:
    def __init__(self, name_: str, parent_: Any = None):
        self.name = name_
        self.id = uuid4()
        self.active = True
        self.data = None
        self.header = None
        self.parent = parent_

    def __eq__(self, other_) -> bool:
        return self.id == other_

    def is_correct_read(self) -> bool:
        return self.data is not None

    def clear(self):
        self.active = False
        self.data = self.header = None

    def data_init(self):
        ...


class XYDataFrame(AbstractDataFrame):
    _db_instance = None
    _active_borehole_id = None

    @staticmethod
    def _get_db():
        if XYDataFrame._db_instance is not None:
            return XYDataFrame._db_instance
        try:
            XYDataFrame._db_instance = DbStorage()
        except Exception:
            XYDataFrame._db_instance = None
        return XYDataFrame._db_instance

    @staticmethod
    def set_active_borehole_id(borehole_id: Optional[str]) -> None:
        XYDataFrame._active_borehole_id = borehole_id

    def __init__(self, filename_: str, parent_: Any = None, file_id_: Optional[str] = None):
        super().__init__(os.path.basename(filename_), parent_)
        self.filename = filename_
        self.file_id = None if file_id_ is None else str(file_id_)
        self.db_file_id = self.file_id
        self.data = None
        self.max_y = None
        self.min_y = None
        self.mean_y = None
        is_exception = False

        if self.file_id:
            loaded_from_db = self._load_from_db_by_id()
            if not loaded_from_db:
                self.clear()
            return

        if not os.path.exists(self.filename) or not os.path.isfile(self.filename):
            MessageBox().warning(
                cf.FILE_NOT_EXIST_WARNING_TITLE,
                cf.FILE_NOT_EXIST_WARNING_MESSAGE_F(self.filename),
            )
        else:
            self.data = pd.read_csv(
                self.filename,
                header=None,
                on_bad_lines="skip",
                dtype=np.dtype(str),
            )
        try:
            self.header = self.header_init()
        except MyWarning as mw:
            MessageBox().warning(mw.exception_title, mw.message)
            is_exception = True
        except Exception:
            MessageBox().warning(cf.UNKNOWN_WARNING_TITLE, cf.UNKNOWN_WARNING_MESSAGE)
            is_exception = True

        if is_exception:
            self.clear()
            return

        self.data_init()
        saved_file_id = self._save_to_db()
        if saved_file_id:
            self.db_file_id = str(saved_file_id)

    def clear(self):
        self.active = False
        self.data = self.header = self.max_y = self.min_y = None

    def is_correct_read(self) -> bool:
        return self.data is not None and self.header is not None

    def header_init(self) -> dict:
        res = dict()
        for i in range(cf.CSV_FILE_HEADER_SIZE):
            dot_index = self.data.iloc[i][0].find(":")
            if dot_index == -1 or self.data.iloc[i][0][:dot_index] not in cf.CSV_FILE_HEADER_CONTENT:
                raise MyWarning(
                    cf.INCORRECT_FILE_CONTENT_WARNING_TITLE,
                    cf.INCORRECT_FILE_HEADER_WARNING_MESSAGE_F(self.filename),
                )
            header_name = self.data.iloc[i][0][:dot_index]
            res[header_name] = cf.CSV_FILE_HEADER_CONTENT[header_name].get(self.data.iloc[i][0][dot_index + 1 :])
            if header_name == cf.TIME_BASE_HEADER:
                res[header_name] *= 1 if self.data.iloc[i][0][dot_index + 1 :].find("mV") else 10**-3
        return res

    def data_init(self) -> None:
        if not self.is_correct_read():
            return
        self.data = self.data.drop(index=[0, 1, 2, 3, 4, 5])
        y_data = self.data[0].astype(float).values.tolist()
        self.mean_y = round(sum(y_data) / len(y_data), 1) if y_data else 0
        self.data = {"y": [round(y + abs(self.mean_y), 1) for y in y_data]}
        self.max_y = max(self.data["y"])
        self.min_y = min(self.data["y"])

    def _load_from_db_by_id(self) -> bool:
        db = self._get_db()
        if db is None or not self.file_id:
            return False
        try:
            row = db.get_file_by_id(self.file_id)
        except Exception:
            return False
        return self._load_from_db_row(row)

    def _load_from_db_row(self, row: Optional[dict]) -> bool:
        if not row:
            return False

        raw_data = row.get("data")
        try:
            payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        except Exception:
            return False

        if not isinstance(payload, dict):
            return False

        header = payload.get("header") or {}
        data = payload.get("data") or {}
        stats = payload.get("stats") or {}

        if not isinstance(header, dict) or not isinstance(data, dict):
            return False
        if "y" not in data:
            return False

        self.header = header
        self.data = data
        self.max_y = stats.get("max_y")
        self.min_y = stats.get("min_y")
        self.mean_y = stats.get("mean_y")
        if row.get("file_id"):
            self.db_file_id = str(row.get("file_id"))
        self.active = True
        return self.is_correct_read()

    def _save_to_db(self) -> Optional[str]:
        if not self.is_correct_read():
            return None

        db = self._get_db()
        if db is None:
            return None

        try:
            file_path = str(pathlib.Path(self.filename).expanduser().resolve())
        except Exception:
            return None

        borehole_id = XYDataFrame._active_borehole_id
        if not borehole_id:
            return None

        measurement_num, sensor_num = get_num_file_by_default(
            os.path.basename(self.filename),
            cf.DEFAULT_SENSOR_AMOUNT,
        )

        payload = {
            "header": self.header or {},
            "data": self.data or {},
            "stats": {
                "max_y": self.max_y,
                "min_y": self.min_y,
                "mean_y": self.mean_y,
            },
        }

        meta = {}
        if measurement_num != -1:
            meta["measurement_num"] = measurement_num
        if sensor_num != -1:
            meta["sensor_num"] = sensor_num
        if meta:
            payload["meta"] = meta

        try:
            return db.upsert_file_data(
                borehole_id=borehole_id,
                file_path=file_path,
                file_name=os.path.basename(self.filename),
                part_of_file_id=0,
                payload=payload,
                file_id=self.db_file_id,
            )
        except Exception:
            return None

    @staticmethod
    def get_data_x(data_points_: int, time_base_: int) -> dict:
        x_data = {"x": []}
        step = time_base_ * 16 / data_points_ * 0.001
        for i in range(data_points_):
            x_data["x"].append((i - 1) * step)
        return x_data


class MaxesDataFrame(AbstractDataFrame):
    def __init__(self, name_: str, maxes_: list, parent_: Any = None, max_value_: float = None, **kwargs):
        super().__init__(name_, parent_)
        self.data = {"x": [], "y": maxes_, "ry": []}
        if "x_list" in kwargs:
            self.data["x"] = kwargs["x_list"]
        self.max_value = None
        self.data_init(max_value_)
        self.tmp_value = None

    def max(self, max_value_: float = None) -> float:
        if max_value_ is not None:
            self.max_value = max_value_
        if self.max_value is None and len(self.data["y"]):
            self.max_value = max(self.data["y"])
        return self.max_value

    def data_init(self, max_value_: float = None) -> None:
        self.compute_relative_data(max_value_)

    def compute_relative_data(self, max_value_: float = None) -> None:
        max_of_maxes = max_value_
        if max_of_maxes is None:
            max_of_maxes = self.max()
        for max_ in self.data["y"]:
            self.data["ry"].append(max_ / max_of_maxes)

    @staticmethod
    def get_data_x(data_points_: int, start_point_: int = 0, step_: int = 1) -> dict:
        x_dataframe = {"x": []}
        for i in range(start_point_, start_point_ + data_points_ * step_, step_):
            x_dataframe["x"].append(i)
        return x_dataframe


class MinDataFrame(AbstractDataFrame):
    def __init__(self, name_: str, mins_: list, parent_: Any = None, min_value_: float = None, **kwargs):
        super().__init__(name_, parent_)
        self.data = {"x": [], "y": mins_, "ry": []}
        if "x_list" in kwargs:
            self.data["x"] = kwargs["x_list"]
        self.min_value = None
        self.data_init(min_value_)
        self.tmp_value = None

    def min(self, min_value_: float = None) -> float:
        if min_value_ is not None:
            self.min_value = min_value_
        if self.min_value is None and len(self.data["y"]):
            self.min_value = min(self.data["y"])
        return self.min_value

    def data_init(self, min_value_: float = None) -> None:
        self.compute_relative_data(min_value_)

    def compute_relative_data(self, min_value_: float = None) -> None:
        min_of_mins = min_value_
        if min_of_mins is None:
            min_of_mins = self.min()
        for min_ in self.data["y"]:
            self.data["ry"].append(min_ / min_of_mins)

    @staticmethod
    def get_data_x(data_points_: int, start_point_: int = 0, step_: int = 1) -> dict:
        x_dataframe = {"x": []}
        for i in range(start_point_, start_point_ + data_points_ * step_, step_):
            x_dataframe["x"].append(i)
        return x_dataframe


def try_create_dir(parent_path_: str, name_: str, num_: int = -1) -> str:
    tmp_name = name_
    if num_ > -1:
        tmp_name += f" ({num_})"
    for filename in pathlib.Path(parent_path_).glob("*"):
        if os.path.basename(filename) == tmp_name:
            return try_create_dir(parent_path_, name_, num_ + 1)
    tmp_name = parent_path_ + "/" + tmp_name
    os.mkdir(tmp_name)
    return tmp_name


def is_float(s_: str) -> bool:
    try:
        float(s_)
        return True
    except ValueError:
        return False


class FileConverter:
    def __init__(self, filename_: str, save_dir_: str, sensor_num_: int, crash_deep_: int, measurement_num_: int):
        self.old_filename = filename_
        self.old_basename = os.path.basename(self.old_filename)
        self.new_basename = (
            f"DEFAULT_{self.get_sensor_num(sensor_num_)}_{crash_deep_}mm_{self.get_measurement_num(measurement_num_)}.csv"
        )
        self.new_filename = save_dir_ + "/" + self.new_basename

    def get_measurement_num(self, measurement_num_: int) -> str:
        return chr(ord("A") + measurement_num_ - 10) if measurement_num_ > 9 else str(measurement_num_)

    def get_sensor_num(self, sensor_num_: int) -> str:
        return chr(ord("A") + sensor_num_)

    def convert(self) -> bool:
        if not pathlib.Path(self.old_filename).is_file():
            return False
        old_file = open(self.old_filename, "r", encoding=cf.DEFAULT_ENCODING)
        new_file = open(self.new_filename, "w", encoding=cf.DEFAULT_ENCODING)
        if (
            not self.__header_line_convert(old_file, new_file, cf.TIME_BASE_HEADER)
            or not self.__header_line_convert(old_file, new_file, cf.SAMPLING_RATE_HEADER)
            or not self.__header_line_convert(old_file, new_file, cf.AMPLITUDE_HEADER)
            or not self.__header_line_convert(old_file, new_file, cf.AMPLITUDE_RESOLUTION_HEADER)
            or not self.__header_line_convert(old_file, new_file, cf.DATA_UINT_HEADER)
            or not self.__header_line_convert(old_file, new_file, cf.DATA_POINTS_HEADER)
            or not self.__data_convert(old_file, new_file)
        ):
            os.remove(self.new_filename)
            return False
        return True

    def __header_line_convert(self, old_file_, new_file_, header_name_: str) -> bool:
        time_base = self.__get_clear_header_line(old_file_.readline(), header_name_)
        if time_base is not None:
            new_file_.write(time_base)
            return True
        return False

    def __get_clear_header_line(self, line_: str, header_name_: str) -> str:
        index = line_.find(header_name_ + ":")
        if index == -1:
            return None
        return f'{header_name_}:{line_[index + len(header_name_ + ":"):]}'

    def __data_convert(self, old_file_, new_file_) -> bool:
        for line in old_file_:
            index = line.find(",")
            new_line = line if index == -1 else line[:index]
            if not is_float(new_line):
                return False
            if new_line[-1] != "\n":
                new_line += "\n"
            new_file_.write(new_line)
        return True


class FileDirector:
    def __init__(
        self,
        filename_list_: list,
        sensor_num_: int,
        crash_deep_: int,
        start_measurement_num_: int,
        converted_folder_name_: str = cf.DEFAULT_CONVERTED_DATA_FOLDER,
        converted_folder_path_: str = None,
        in_exist_: bool = False,
    ):
        self.filename_list = filename_list_
        self.sensor_num = sensor_num_
        self.crash_deep = crash_deep_
        self.start_measurement_num = start_measurement_num_
        self.save_dir = str(
            (pathlib.Path().resolve() if converted_folder_path_ is None else pathlib.Path(converted_folder_path_))
            / converted_folder_name_
        )
        if not in_exist_ or not os.path.isdir(self.save_dir):
            self.save_dir = (
                try_create_dir(str(pathlib.Path(filename_list_[0]).parent), converted_folder_name_)
                if converted_folder_path_ is None
                else try_create_dir(converted_folder_path_, converted_folder_name_)
            )

    def convert(self) -> bool:
        measurement_num = self.start_measurement_num
        for filename in self.filename_list:
            if measurement_num > 36:
                return True
            file_converter = FileConverter(filename, self.save_dir, self.sensor_num, self.crash_deep, measurement_num)
            if not file_converter.convert():
                return False
            measurement_num += 1
        return True


class BoreholeUseCases:
    @staticmethod
    def add_section(borehole: Borehole, name_: str, depth_: int = 0, length_: float = 0.0, id_: str = None) -> None:
        borehole.add_section(name_, depth_, length_, id_)

    @staticmethod
    def remove_section(borehole: Borehole, **kwargs) -> None:
        borehole.remove_section(**kwargs)

    @staticmethod
    def add_step(section: Section, number_: int, id_: str = None) -> None:
        section.add_step(number_, id_)

    @staticmethod
    def remove_step(section: Section, **kwargs) -> None:
        section.remove_step(**kwargs)

    @staticmethod
    def add_file(
        step: Step,
        file_name_: str,
        id_: str = None,
        allow_virtual_: bool = False,
        db_file_id_: str = None,
    ) -> None:
        step.add_file(file_name_, id_=id_, allow_virtual_=allow_virtual_, db_file_id_=db_file_id_)

    @staticmethod
    def remove_file(step: Step, **kwargs) -> None:
        step.remove_file(**kwargs)

    @staticmethod
    def select_data_file(data_file: DataFile, is_select_: bool = True) -> None:
        data_file.select(is_select_)


configure_domain_dependencies(
    xy_dataframe_factory=XYDataFrame,
    maxes_dataframe_factory=MaxesDataFrame,
    min_dataframe_factory=MinDataFrame,
    warning_handler=MessageBox().warning,
)


__all__ = [
    "AbstractDataFrame",
    "XYDataFrame",
    "MaxesDataFrame",
    "MinDataFrame",
    "try_create_dir",
    "is_float",
    "FileConverter",
    "FileDirector",
    "BoreholeUseCases",
]
