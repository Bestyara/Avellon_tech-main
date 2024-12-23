import os
import sys
import pathlib
from PySide6.QtWidgets import QFileDialog, QVBoxLayout, QPushButton, QWidget, \
    QFormLayout, QLineEdit, QDialog
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt
from third_party import MessageBox, AbstractToolDialog
from loadlabel import loading
import config as cf


def try_create_dir(parent_path_: str, name_: str, num_: int = -1) -> str:
    tmp_name = name_
    if num_ > -1:
        tmp_name += f' ({num_})'
    for filename in pathlib.Path(parent_path_).glob('*'):
        if os.path.basename(filename) == tmp_name:
            return try_create_dir(parent_path_, name_, num_ + 1)
    tmp_name = parent_path_ + '/' + tmp_name
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
        self.new_basename = f'DEFAULT_{self.get_sensor_num(sensor_num_)}_{crash_deep_}mm_{self.get_measurement_num(measurement_num_)}.csv'
        self.new_filename = save_dir_ + '/' + self.new_basename

    def get_measurement_num(self, measurement_num_: int) -> str:
        return chr(ord('A') + measurement_num_ - 10) if measurement_num_ > 9 else str(measurement_num_)

    def get_sensor_num(self, sensor_num_: int) -> str:
        return chr(ord('A') + sensor_num_)

    def convert(self) -> bool:
        if not pathlib.Path(self.old_filename).is_file():
            return False
        old_file = open(self.old_filename, 'r', encoding=cf.DEFAULT_ENCODING)
        new_file = open(self.new_filename, 'w', encoding=cf.DEFAULT_ENCODING)
        if not self.__header_line_convert(old_file, new_file, cf.TIME_BASE_HEADER) or \
                not self.__header_line_convert(old_file, new_file, cf.SAMPLING_RATE_HEADER) or \
                not self.__header_line_convert(old_file, new_file, cf.AMPLITUDE_HEADER) or \
                not self.__header_line_convert(old_file, new_file, cf.AMPLITUDE_RESOLUTION_HEADER) or \
                not self.__header_line_convert(old_file, new_file, cf.DATA_UINT_HEADER) or \
                not self.__header_line_convert(old_file, new_file, cf.DATA_POINTS_HEADER) or \
                not self.__data_convert(old_file, new_file):
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
        index = line_.find(header_name_ + ':')
        if index == -1:
            return None
        return f'{header_name_}:{line_[index + len(header_name_ + ":"):]}'

    def __data_convert(self, old_file_, new_file_) -> bool:
        for line in old_file_:
            index = line.find(',')
            new_line = line if index == -1 else line[:index]
            if not is_float(new_line):
                return False
            if new_line[-1] != '\n':
                new_line += '\n'
            new_file_.write(new_line)
        return True


class FileDirector:
    def __init__(self, filename_list_: list, sensor_num_: int, crash_deep_: int, start_measurement_num_: int,
                 converted_folder_name_: str = cf.DEFAULT_CONVERTED_DATA_FOLDER, converted_folder_path_: str = None,
                 in_exist_: bool = False):
        self.filename_list = filename_list_
        self.sensor_num = sensor_num_
        self.crash_deep = crash_deep_
        self.start_measurement_num = start_measurement_num_
        self.save_dir = str((pathlib.Path().resolve() if converted_folder_path_ is None
                             else pathlib.Path(converted_folder_path_))  / converted_folder_name_)
        if not in_exist_ or not os.path.isdir(self.save_dir):
            self.save_dir = try_create_dir(str(pathlib.Path(filename_list_[0]).parent), converted_folder_name_) \
                if converted_folder_path_ is None else try_create_dir(converted_folder_path_, converted_folder_name_)

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


class ConverterDialog(AbstractToolDialog):
    def __init__(self, parent_: QWidget = None):
        super().__init__(cf.DATA_CONVERTER_DIALOG_TITLE, parent_)
        self.sensor_num = 0
        self.crash_deep = 0
        self.start_measurement_num = 0
        self.setWindowModality(Qt.ApplicationModal)

        self.sensor_editor = QLineEdit(self)
        self.crash_deep_editor = QLineEdit(self)
        self.measurement_editor = QLineEdit(self)
        self.__editor_init()
        self.__values_to_editors()

        self.files_button = QPushButton('Выбрать Файлы', self)
        self.folder_files_button = QPushButton('Выбрать папку с файлами', self)
        self.folder_folders_button = QPushButton('Выбрать папку с папками', self)
        self.exit_button = QPushButton('Выход', self)
        self.__button_init()

        self.__all_widgets_to_layout()

    def __editor_init(self) -> None:
        self.sensor_editor.setAlignment(Qt.AlignRight)
        self.sensor_editor.textChanged.connect(self.sensor_num_edit_action)

        self.crash_deep_editor.setAlignment(Qt.AlignRight)
        self.crash_deep_editor.setValidator(QIntValidator())
        self.crash_deep_editor.textChanged.connect(self.crash_deep_edit_action)

        self.measurement_editor.setAlignment(Qt.AlignRight)
        self.measurement_editor.setValidator(QIntValidator())
        self.measurement_editor.textChanged.connect(self.measurement_num_edit_action)

    def __values_to_editors(self) -> None:
        self.sensor_num_edit_action(str(self.sensor_num))
        self.crash_deep_editor.setText(str(self.crash_deep))
        self.measurement_editor.setText(str(self.start_measurement_num))

    def __button_init(self) -> None:
        self.files_button.clicked.connect(self.files_conversion_action)
        self.folder_files_button.clicked.connect(self.folder_files_conversion_action)
        self.folder_folders_button.clicked.connect(self.folder_folders_conversion_action)
        self.exit_button.clicked.connect(self.cancel_action)
        self.exit_button.setShortcut("Shift+Esc")

    def __all_widgets_to_layout(self) -> None:
        flo = QFormLayout()
        flo.addRow('Номер датчика', self.sensor_editor)
        flo.addRow('Глубина трещины', self.crash_deep_editor)
        flo.addRow('Номер первого измерения', self.measurement_editor)

        core_layout = QVBoxLayout()
        core_layout.addLayout(flo)
        core_layout.addWidget(self.files_button)
        core_layout.addWidget(self.folder_files_button)
        core_layout.addWidget(self.folder_folders_button)
        core_layout.addWidget(self.exit_button)
        self.setLayout(core_layout)

    def sensor_num_edit_action(self, text_: str) -> None:
        len_text = len(text_)
        if len_text < 1:
            self.sensor_num = 0
            return
        elif len_text > 1 or not (text_.isalpha() or text_.isdigit()) or ord(text_) > ord('H'):
            self.sensor_num = ord('H') - ord('A')
        elif text_.isdigit():
            self.sensor_num = int(float(text_))
        else:
            self.sensor_num = ord(text_) - ord('A')
        self.sensor_editor.setText(chr(ord('A') + self.sensor_num))

    def crash_deep_edit_action(self, text_: str) -> None:
        if text_.find('-') != -1:
            text_ = '0'
            self.crash_deep_editor.setText(text_)
        self.crash_deep = 0 if len(text_) < 1 else int(float(text_))

    def measurement_num_edit_action(self, text_: str) -> None:
        if text_.find('-') != -1:
            text_ = '0'
            self.crash_deep_editor.setText(text_)
        self.start_measurement_num = 0 if len(text_) < 1 else int(float(text_))


    def files_conversion_action(self) -> None:
        filename_list, useless_filter = QFileDialog.getOpenFileNames(self, dir=str(pathlib.Path().resolve()),
                                                                     filter=cf.FILE_DIALOG_CSV_FILTER)
        if len(filename_list) < 1:
            return 
        print(filename_list)
        print(self.sensor_num, self.crash_deep, self.start_measurement_num)
        self.conversion(filename_list)

    def folder_files_conversion_action(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, cf.SELECT_FOLDER_FILE_DIALOG_TITLE)
        if len(dir_path) < 1 or not os.path.isdir(dir_path):
            return
        print(dir_path)
        filename_list = []
        for filename in pathlib.Path(dir_path).glob('*.csv'):
            if filename.is_file():
                filename_list.append(str(filename))
        if len(filename_list) < 1:
            return
        self.conversion(filename_list, os.path.basename(dir_path) + ' - converted', str(pathlib.Path(dir_path).parent))

    def folder_folders_conversion_action(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, cf.SELECT_FOLDER_FILE_DIALOG_TITLE)
        if len(dir_path) < 1 or not os.path.isdir(dir_path):
            return
        print(dir_path)
        folder_list = []
        for filename in pathlib.Path(dir_path).glob('*'):
            if filename.is_dir():
                folder_list.append(str(filename))
        if len(folder_list) < 1:
            return
        self.few_conversion(folder_list, os.path.basename(dir_path) + ' - converted', str(pathlib.Path(dir_path).parent))

    @loading('result_conversion', True)
    def conversion(self, filename_list_: list, converted_folder_name_: str = cf.DEFAULT_CONVERTED_DATA_FOLDER,
                   converted_folder_path_: str = None) -> bool:
        file_director = FileDirector(filename_list_, self.sensor_num, self.crash_deep, self.start_measurement_num,
                                     converted_folder_name_, converted_folder_path_)
        return file_director.convert()

    @loading('result_conversion', True)
    def few_conversion(self, folder_list_: list, converted_folder_name_: str, converted_folder_path_: str) -> bool:
        res = True
        sensor_num = 0
        for dirname in folder_list_:
            filename_list = []
            for filename in pathlib.Path(dirname).glob('*.csv'):
                if filename.is_file():
                    filename_list.append(str(filename))
            if len(filename_list) < 1:
                continue
            file_director = FileDirector(filename_list, sensor_num, self.crash_deep, 0,
                                         converted_folder_name_, converted_folder_path_, True)
            res = file_director.convert() and res
            sensor_num += 1
        return res

    def result_conversion(self, is_success_: bool) -> None:
        if is_success_:
            MessageBox().information(cf.CONVERT_COMPLETE_INFO_TITLE, cf.CONVERT_COMPLETE_INFO_MESSAGE)
        else:
            MessageBox().warning(cf.CONVERT_WARNING_TITLE, cf.CONVERT_WARNING_MESSAGE)

    def run(self) -> None:
        self.exec()
