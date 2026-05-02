import numpy as np
from uuid import uuid4
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QDialog
from PySide6.QtCore import QPoint, QRect
from pyqtgraph import PlotWidget, mkPen, QtGui, QtCore
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from ui.common import AxisXDialog
import config as cf
import pyqtgraph as pg
from scipy.signal import butter, filtfilt
from use_cases import MaxesDataFrame, MinDataFrame, XYDataFrame

class AbstractQtGraphWidget(PlotWidget):
    def __init__(self, data_frames_, parent_: QWidget = None):
        super().__init__(parent_)
        self.id = uuid4()
        self.data_frames = data_frames_
        self.dict_data_x = dict()
        self.base_init()
        self.lines = []
        self.legend = self.addLegend()

    def base_init(self):
        self.setBackground('w')
        self.showGrid(x=True, y=True)

    def graph_init(self) -> None: ...

    def data_x_init(self) -> None: ...

    def recreate(self, data_frames_, **kwargs) -> None:
        for line in self.lines:
            line.clear()
        self.data_frames = data_frames_
        self.data_x_init()
        self.base_init()
        self.graph_init()


class OscilloscopeGraphWidget(AbstractQtGraphWidget):
    def __init__(self, data_frames_: dict, parent_: QWidget = None):
        super().__init__(data_frames_, parent_)
        self.graph_init()
        self.setTitle("Данные осциллографа")
        self.setLabel('left', 'Напряжение (мВ)')
        self.setLabel('bottom', 'Время (с)')

        # Добавляем текстовый элемент для отображения координат
        self.coordinates_text = pg.TextItem("", anchor=(1, 1))
        self.addItem(self.coordinates_text)

        # Включаем отслеживание мыши
        self.setMouseTracking(True)

        # Подключаем событие движения мыши
        self.scene().sigMouseMoved.connect(self.on_mouse_move)

    def on_mouse_move(self, pos):
        """ Обработчик движения мыши для отображения координат на графике """
        # Преобразуем позицию в координаты графика
        mouse_point = self.plotItem.vb.mapSceneToView(pos)
        x = mouse_point.x()
        y = mouse_point.y()

        # Найдём ближайшую точку данных
        closest_x, closest_y = self.find_closest_point(x, y)

        # Обновляем текстовый элемент с координатами
        self.coordinates_text.setText(f"X: {closest_x:.2f}, Y: {closest_y:.2f}")
        self.coordinates_text.setPos(closest_x, closest_y)
        self.coordinates_text.setColor((0, 0, 0))

    def find_closest_point(self, x, y):
        """ Метод для нахождения ближайшей точки к позиции курсора """
        min_dist = float('inf')
        closest_x, closest_y = None, None

        for line in self.lines:
            data_x = line.xData  # Данные по оси X для текущей линии
            data_y = line.yData  # Данные по оси Y для текущей линии

            # Ищем ближайшую точку
            for i in range(len(data_x)):
                dist = (data_x[i] - x) ** 2 + (data_y[i] - y) ** 2  # Евклидово расстояние
                if dist < min_dist:
                    min_dist = dist
                    closest_x, closest_y = data_x[i], data_y[i]

        return closest_x, closest_y

    def data_x_init(self) -> None:
        self.dict_data_x = dict()
        for key in self.data_frames.keys():
            for dataframe in self.data_frames[key]:
                if dataframe.header[cf.DATA_POINTS_HEADER] not in self.dict_data_x:
                    self.dict_data_x[dataframe.header[cf.DATA_POINTS_HEADER]] = dict()
                if dataframe.header[cf.TIME_BASE_HEADER] not in self.dict_data_x[
                    dataframe.header[cf.DATA_POINTS_HEADER]]:
                    self.dict_data_x[dataframe.header[cf.DATA_POINTS_HEADER]][dataframe.header[cf.TIME_BASE_HEADER]] \
                        = XYDataFrame.get_data_x(dataframe.header[cf.DATA_POINTS_HEADER],
                                                 dataframe.header[cf.TIME_BASE_HEADER])

    def graph_init(self) -> None:
        self.legend.clear()
        if len(self.data_frames.keys()) < 1:
            return
        color_i, c = 0, 0
        for key in self.data_frames.keys():
            for i in range(len(self.data_frames[key])):
                # Вычисляем среднее значение оси Y для текущего набора данных
                y_data = self.data_frames[key][i].data["y"]
                if color_i >= len(cf.COLOR_NAMES):
                    color_i = 0
                if c >= len(self.lines):
                    self.lines.append(
                        self.plot(
                            self.dict_data_x[self.data_frames[key][i].header[cf.DATA_POINTS_HEADER]]
                            [self.data_frames[key][i].header[cf.TIME_BASE_HEADER]]['x'],
                            y_data,
                            pen=mkPen(cf.COLOR_NAMES[color_i])
                        )
                    )
                elif self.data_frames[key][i].active:
                    self.lines[c].setData(
                        self.dict_data_x[self.data_frames[key][i].header[cf.DATA_POINTS_HEADER]]
                        [self.data_frames[key][i].header[cf.TIME_BASE_HEADER]]['x'],
                        y_data
                    )
                self.legend.addItem(self.lines[c], self.data_frames[key][i].name)
                c += 1
                color_i += 1

    def apply_filter(self, filter_type: str, cutoff_freq: float, sample_rate: float = 1000):
        """
        Применяет фильтр к данным.
        :param filter_type: Тип фильтра ("high" для ФВЧ, "low" для ФНЧ).
        :param cutoff_freq: Частота среза в Гц.
        :param sample_rate: Частота дискретизации сигнала (по умолчанию 1000 Гц).
        """
        for key in self.data_frames.keys():
            for dataframe in self.data_frames[key]:
                if dataframe.active:
                    # Получаем данные сигнала
                    y_data = dataframe.data['y']

                    # Применяем фильтр
                    filtered_data = self._butter_filter(y_data, cutoff_freq, sample_rate, filter_type)

                    # Обновляем данные
                    dataframe.data['y'] = filtered_data

        # Перестраиваем график
        self.recreate(self.data_frames)

    def _butter_filter(self, data, cutoff_freq, sample_rate, filter_type, order=5):
        """
        Применяет фильтр Баттерворта к данным.
        :param data: Исходные данные (список значений).
        :param cutoff_freq: Частота среза в Гц.
        :param sample_rate: Частота дискретизации сигнала.
        :param filter_type: Тип фильтра ("high" для ФВЧ, "low" для ФНЧ).
        :param order: Порядок фильтра (по умолчанию 5).
        :return: Отфильтрованные данные.
        """
        nyquist_freq = 0.5 * sample_rate
        normal_cutoff = cutoff_freq / nyquist_freq

        # Создаем фильтр Баттерворта
        b, a = butter(order, normal_cutoff, btype=filter_type, analog=False)

        # Применяем фильтр с нулевой фазовой задержкой
        filtered_data = filtfilt(b, a, data)
        return filtered_data


class FrequencyResponseGraphWidget(AbstractQtGraphWidget):
    def __init__(self, data_frames_: dict, parent_: QWidget = None):
        super().__init__(data_frames_, parent_)
        self.axis_x_start = None
        self.axis_x_step = None
        self.graph_init()
        self.setTitle("Частотная характеристика")
        self.setLabel('left', 'U, мВ')
        self.setLabel('bottom', 'f, кГц')

        # Добавляем текст для отображения координат
        self.annot = pg.TextItem("", anchor=(0, 1))
        self.addItem(self.annot)
        self.annot.setPos(0, 0)
        self.annot.hide()

        # Подключаем событие для отслеживания движения мыши
        self.scene().sigMouseMoved.connect(self.onMouseMoved)

    def data_x_init(self) -> None:
        self.dict_data_x = {21: MaxesDataFrame.get_data_x(21, 4, 2)}

    def _get_x_data(self, len_data: int) -> list:
        if len_data not in self.dict_data_x:
            self.dict_data_x[len_data] = MaxesDataFrame.get_data_x(len_data, 4, 2)
        return self.dict_data_x[len_data]["x"]

    def graph_init(self) -> None:
        self.legend.clear()
        for line in self.lines:
            self.removeItem(line)
        self.lines = []
        self.plotted_points = []
        if len(self.data_frames.keys()) < 1:
            return
        color_i, c = 0, 0
        max_len = 0
        x_min, x_max = float("inf"), float("-inf")
        y_min, y_max = float("inf"), float("-inf")
        for key in self.data_frames.keys():
            for i in range(len(self.data_frames[key])):
                y_data = self.data_frames[key][i].data['y']
                y_data = [abs(y) for y in y_data]
                if color_i >= len(cf.COLOR_NAMES):
                    color_i = 0
                len_data = len(self.data_frames[key][i].data['y'])
                max_len = max(max_len, len_data)

                x_data = self._get_x_data(len_data)
                if x_data and y_data:
                    x_min = min(x_min, min(x_data))
                    x_max = max(x_max, max(x_data))
                    y_min = min(y_min, min(y_data))
                    y_max = max(y_max, max(y_data))
                # Добавляем линию графика
                if c >= len(self.lines):
                    self.lines.append(self.plot(x_data, y_data, pen=mkPen(cf.COLOR_NAMES[color_i], width=3)))
                elif self.data_frames[key][i].active:
                    self.lines[c].setData(x_data, y_data)

                # Сохраняем данные точек для дальнейшей обработки при наведении
                self.plotted_points.append((x_data, y_data))

                self.legend.addItem(self.lines[c], self.data_frames[key][i].name)
                c += 1
                color_i += 1
        if (
            self.axis_x_start is not None
            and self.axis_x_step is not None
            and max_len > 0
        ):
            x_left = float(self.axis_x_start)
            x_right = x_left + float(self.axis_x_step) * max(0, max_len - 1)
            self.setXRange(x_left, x_right, padding=0.0)
        elif x_min != float("inf") and x_max != float("-inf"):
            self.setXRange(x_min, x_max, padding=0.05)
        if y_min != float("inf") and y_max != float("-inf"):
            self.setYRange(y_min, y_max, padding=0.05)

    def onMouseMoved(self, evt):
        # Получаем положение мыши в координатах графика
        mouse_point = self.plotItem.vb.mapSceneToView(evt)
        x_mouse = mouse_point.x()
        y_mouse = mouse_point.y()

        # Ищем ближайшую точку к положению курсора
        closest_point = None
        min_dist = float('inf')

        # Проверяем все точки на графике
        for points in self.plotted_points:
            x_data, y_data = points
            for x, y in zip(x_data, y_data):
                dist = ((x - x_mouse) ** 2 + (y - y_mouse) ** 2) ** 0.5  # Евклидово расстояние
                if dist < min_dist:
                    min_dist = dist
                    closest_point = (x, y)

        # Если нашли ближайшую точку, показываем аннотацию
        if closest_point and min_dist < 0.9:  # Пороговое расстояние
            self.annot.setPos(closest_point[0], closest_point[1])

            # Изменение цвета и стиля текста через HTML
            self.annot.setHtml(f'<span style="color: #FF0000; font-size: 12pt;">f={closest_point[0]:.2f} кГц, U={closest_point[1]:.2f} мВ</span>')

            self.annot.show()
        else:
            self.annot.hide()

    def update_axis_x(self, start_value: float, step_value: float):
        """
        Обновляет данные по оси X на основе начального значения и шага.
        :param start_value: Начальное значение по оси X.
        :param step_value: Шаг по оси X.
        """
        self.axis_x_start = float(start_value)
        self.axis_x_step = float(step_value)
        self.recreate(self.data_frames)

    def recreatey(self, data_frames):
        """
        Перестраивает график на основе обновленных данных.
        """
        for line in self.lines:
            self.removeItem(line)
        self.lines = []
        self.plotted_points = []
        self.graph_init_new()  # Инициализируем график заново

    def graph_init_new(self) -> None:
        """
        Инициализирует график на основе обновленных данных.
        """
        self.legend.clear()
        if len(self.data_frames.keys()) < 1:
            return

        color_i, c = 0, 0

        x_min, x_max = float('inf'), float('-inf')  # Для вычисления диапазона оси X
        y_min, y_max = float('inf'), float('-inf')  # Для вычисления диапазона оси Y

        for key in self.data_frames.keys():
            for i in range(len(self.data_frames[key])):
                y_data = self.data_frames[key][i].data["y"]
                y_data = [abs(y) for y in y_data]
                if color_i >= len(cf.COLOR_NAMES):
                    color_i = 0
                len_data = len(self.data_frames[key][i].data["y"])

                # Используем обновленные данные по оси X
                x_data = self.data_frames[key][i].data.get('x', [])
                if not x_data:  # Если данные по оси X отсутствуют, пропускаем
                    continue

                # Обновляем диапазоны осей
                x_min = min(x_min, min(x_data))
                x_max = max(x_max, max(x_data))
                y_min = min(y_min, min(y_data))
                y_max = max(y_max, max(y_data))

                # Добавляем линию графика
                if c >= len(self.lines):
                    self.lines.append(self.plot(x_data, y_data, pen=mkPen(cf.COLOR_NAMES[color_i], width=3)))
                elif self.data_frames[key][i].active:
                    self.lines[c].setData(x_data, y_data)

                # Сохраняем данные точек для дальнейшей обработки при наведении
                self.plotted_points.append((x_data, y_data))

                self.legend.addItem(self.lines[c], self.data_frames[key][i].name)
                c += 1
                color_i += 1

        # Устанавливаем диапазоны осей
        if x_min != float('inf') and x_max != float('-inf'):
            self.setXRange(x_min, x_max)
        if y_min != float('inf') and y_max != float('-inf'):
            self.setYRange(y_min, y_max)

class AmplitudeTimeGraphWidget(AbstractQtGraphWidget):
    def __init__(self, data_frames_: dict, parent_: QWidget = None):
        super().__init__(data_frames_, parent_)
        self.section_name_mode = None
        self.mean_mode = -1
        self.sensor_num = -1
        self.is_relative = False
        self.graph_init()
        self.setTitle("Зависимость амплитуды во времени")
        self.setLabel('left', 'Значение')
        self.setLabel('bottom', 'Шаг')

    def data_x_init(self) -> None:
        pass

    def graph_init(self) -> None:
        self.legend.clear()
        if len(self.data_frames.keys()) < 1:
            return
        color_i, c = 0, 0
        range_list = {'x': [None, None], 'y': [None, None]}
        if self.section_name_mode is not None:
            if self.section_name_mode not in self.data_frames:
                return
            for i in self.data_frames[self.section_name_mode].keys():
                if i < 0:
                    continue
                if color_i >= len(cf.COLOR_NAMES):
                    color_i = 0
                minmaxes = {'x': [min(self.data_frames[self.section_name_mode][i].data['x']),
                                  max(self.data_frames[self.section_name_mode][i].data['x'])],
                            'y': [min(
                                self.data_frames[self.section_name_mode][i].data['ry' if self.is_relative else "y"]),
                                max(self.data_frames[self.section_name_mode][i].data[
                                        'ry' if self.is_relative else "y"])]}
                range_list['x'][0] = minmaxes['x'][0] if range_list['x'][0] is None else min(minmaxes['x'][0],
                                                                                             range_list['x'][0])
                range_list['x'][1] = minmaxes['x'][1] if range_list['x'][1] is None else max(minmaxes['x'][1],
                                                                                             range_list['x'][1])
                range_list['y'][0] = minmaxes['y'][0] if range_list['y'][0] is None else min(minmaxes['y'][0],
                                                                                             range_list['y'][0])
                range_list['y'][1] = minmaxes['y'][1] if range_list['y'][1] is None else max(minmaxes['y'][1],
                                                                                             range_list['y'][1])
                if c >= len(self.lines):
                    self.lines.append(self.plot(self.data_frames[self.section_name_mode][i].data['x'],
                                                self.data_frames[self.section_name_mode][i].data[
                                                    'ry' if self.is_relative else "y"],
                                                pen=mkPen(cf.COLOR_NAMES[color_i])))
                elif self.data_frames[self.section_name_mode][i].active:
                    self.lines[c].setData(self.data_frames[self.section_name_mode][i].data["x"],
                                          self.data_frames[self.section_name_mode][i].data[
                                              'ry' if self.is_relative else "y"])
                self.legend.addItem(self.lines[c], self.data_frames[self.section_name_mode][i].name)
                c += 1
                color_i += 1
        else:
            i = self.mean_mode if self.mean_mode < 0 else self.sensor_num
            for key in self.data_frames.keys():
                if i not in self.data_frames[key]:
                    continue
                if color_i >= len(cf.COLOR_NAMES):
                    color_i = 0
                minmaxes = {'x': [min(self.data_frames[key][i].data['x']), max(self.data_frames[key][i].data['x'])],
                            'y': [min(self.data_frames[key][i].data['ry' if self.is_relative else "y"]),
                                  max(self.data_frames[key][i].data['ry' if self.is_relative else "y"])]}
                range_list['x'][0] = minmaxes['x'][0] if range_list['x'][0] is None else min(minmaxes['x'][0],
                                                                                             range_list['x'][0])
                range_list['x'][1] = minmaxes['x'][1] if range_list['x'][1] is None else max(minmaxes['x'][1],
                                                                                             range_list['x'][1])
                range_list['y'][0] = minmaxes['y'][0] if range_list['y'][0] is None else min(minmaxes['y'][0],
                                                                                             range_list['y'][0])
                range_list['y'][1] = minmaxes['y'][1] if range_list['y'][1] is None else max(minmaxes['y'][1],
                                                                                             range_list['y'][1])
                if c >= len(self.lines):
                    self.lines.append(self.plot(self.data_frames[key][i].data["x"],
                                                self.data_frames[key][i].data['ry' if self.is_relative else "y"],
                                                pen=mkPen(cf.COLOR_NAMES[color_i])))
                elif self.data_frames[key][i].active:
                    self.lines[c].setData(self.data_frames[key][i].data["x"],
                                          self.data_frames[key][i].data['ry' if self.is_relative else "y"])
                self.legend.addItem(self.lines[c], self.data_frames[key][i].name)
                c += 1
                color_i += 1
        self.setXRange(range_list['x'][0], range_list['x'][1], padding=0.2)
        self.setYRange(range_list['y'][0], range_list['y'][1], padding=0.1)

    def recreate(self, data_frames_, **kwargs) -> None:
        self.is_relative = kwargs['is_relative'] if 'is_relative' in kwargs else False
        self.section_name_mode = kwargs['section_name'] if 'section_name' in kwargs else None
        self.mean_mode = kwargs['mean_mode'] if 'mean_mode' in kwargs else 0
        self.sensor_num = kwargs['sensor_num'] if 'sensor_num' in kwargs else -1
        super().recreate(data_frames_, **kwargs)


class DepthResponseGraphWidget(AbstractQtGraphWidget):
    def __init__(self, data_frames_: dict, parent_: QWidget = None):
        super().__init__(data_frames_, parent_)
        self.is_relative = False
        self.mean_mode = -1
        self.sensor_num = -1
        self.step_num = -1
        self.graph_init()
        self.setTitle("График соотношения глубины и абсолютной величины мощности сигнала")
        self.setLabel('left', 'Глубина (м)')
        self.setLabel('bottom', 'Мощность сигнала')

    def data_x_init(self) -> None:
        pass

    def graph_init(self) -> None:
        self.legend.clear()
        if len(self.data_frames.keys()) < 1:
            return
        color_i, c = 0, 0
        if self.step_num not in self.data_frames:
            return
        range_list = {'x': [None, None], 'y': [None, None]}
        for section_depth in self.data_frames[self.step_num].keys():
            if self.mean_mode >= 0 and self.sensor_num not in self.data_frames[self.step_num][section_depth]:
                continue
            if color_i >= len(cf.COLOR_NAMES):
                color_i = 0
            data_y_list = [section_depth + 8, section_depth]
            range_list['y'][0] = min(data_y_list[1] if range_list['y'][0] is None else range_list['y'][0],
                                     data_y_list[1])
            range_list['y'][1] = max(data_y_list[0] if range_list['y'][1] is None else range_list['y'][1],
                                     data_y_list[0])
            data_x_list = [self.data_frames[self.step_num][section_depth][
                               self.mean_mode if self.mean_mode < 0 else self.sensor_num][
                               'rx' if self.is_relative else "x"]] * 2
            range_list['x'][0] = min(data_x_list[0] if range_list['x'][0] is None else range_list['x'][0],
                                     data_x_list[0])
            range_list['x'][1] = max(data_x_list[1] if range_list['x'][1] is None else range_list['x'][1],
                                     data_x_list[1])
            if c >= len(self.lines):
                self.lines.append(self.plot(data_x_list, data_y_list, pen=mkPen(cf.COLOR_NAMES[color_i], width=5)))
            else:
                self.lines[c].setData(data_x_list, data_y_list)
            self.legend.addItem(self.lines[c], 'section=' + str(section_depth))
            c += 1
            color_i += 1
        self.setXRange(range_list['x'][0], range_list['x'][1], padding=2.0)
        self.setYRange(range_list['y'][0], range_list['y'][1], padding=0.1)

    def recreate(self, data_frames_, **kwargs) -> None:
        self.is_relative = kwargs['is_relative'] if 'is_relative' in kwargs else False
        self.mean_mode = kwargs['mean_mode'] if 'mean_mode' in kwargs else 0
        self.sensor_num = kwargs['sensor_num'] if 'sensor_num' in kwargs else -1
        self.step_num = kwargs['step_num'] if 'step_num' in kwargs else -1
        super().recreate(data_frames_, **kwargs)

    def on_mouse_move(self, event):
        """ Обработчик движения мыши для отображения координат на графике """
        pos = event  # Получаем позицию мыши в виде QPointF

        # Преобразуем позицию в координаты графика
        if self.plotItem.sceneBoundingRect().contains(pos):
            mouse_point = self.plotItem.vb.mapSceneToView(pos)
            x = mouse_point.x()
            y = mouse_point.y()

            # Найдём ближайшую точку данных
            closest_x, closest_y = self.find_closest_point(x, y)

            # Обновляем текстовый элемент с координатами
            self.coordinates_text.setText(f"X: {closest_x:.2f}, Y: {closest_y:.2f}")
            self.coordinates_text.setPos(closest_x, closest_y)

        def find_closest_point(self, x, y):
            """ Метод для нахождения ближайшей точки к позиции курсора """
            min_dist = float('inf')
            closest_x, closest_y = None, None

            for line in self.lines:
                data_x = line.xData  # Данные по оси X для текущей линии
                data_y = line.yData  # Данные по оси Y для текущей линии

                # Ищем ближайшую точку
                for i in range(len(data_x)):
                    dist = (data_x[i] - x) ** 2 + (data_y[i] - y) ** 2  # Евклидово расстояние
                    if dist < min_dist:
                        min_dist = dist
                        closest_x, closest_y = data_x[i], data_y[i]

            return closest_x, closest_y


# MATPLOTLIB GRAPH
class MplCanvas(FigureCanvasQTAgg):
    def __init__(self):
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111, projection='polar')
        self.sensor_name_list = ['A', '', 'B', '', 'C', '', 'D', '']
        self.axes_init()
        FigureCanvasQTAgg.__init__(self, self.fig)
        FigureCanvasQTAgg.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvasQTAgg.updateGeometry(self)

    def axes_init(self, top_y_lim_: int = 1) -> None:
        self.ax.set_title("Label", va='bottom')
        angle_and_name_list = self.sensor_name_list.copy()
        for i in range(len(angle_and_name_list)):
            angle_and_name_list[i] = str(45 * i) + '° ' + angle_and_name_list[i]
        # Устанавливаем фиксированные деления на оси X
        ticks = range(len(angle_and_name_list))  # Количество делений равно количеству меток
        self.ax.set_xticks(ticks)

        # Устанавливаем метки для делений
        self.ax.set_xticklabels(angle_and_name_list)
        self.ax.set_ylim(0, top_y_lim_)


class WindRoseGraphWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.canvas = MplCanvas()
        self.vbl = QVBoxLayout()
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)

        self.theta = np.array([0, 90, 180, 270, 360]) / 180 * np.pi

    def set_data(self, data_frame_dict_: dict, index_: int = 0, is_relative_: bool = False):
        top_y_lim = float('-inf')
        for section_name in data_frame_dict_.keys():
            is_active = True
            data_list = [0] * (cf.DEFAULT_SENSOR_AMOUNT + 1)
            for dataframe in data_frame_dict_[section_name]:
                if not dataframe.is_correct_read() or not dataframe.active or \
                        len(dataframe.data['ry' if is_relative_ else 'y']) <= index_ and \
                        int(dataframe.name) < cf.DEFAULT_SENSOR_AMOUNT + 1:
                    is_active = False
                    continue
                if dataframe.max() > top_y_lim:
                    top_y_lim = dataframe.max()
                data_list[int(dataframe.name)] = dataframe.data['ry' if is_relative_ else 'y'][index_]
            data_list[-1] = data_list[0]
            if is_active:
                self.canvas.ax.plot(self.theta, data_list, label=section_name)
        self.canvas.ax.set_ylim(0, 1 if is_relative_ or top_y_lim == float('-inf') else top_y_lim)
        self.canvas.ax.legend()
        self.canvas.draw()

    def clear(self):
        self.canvas.ax.clear()
        self.canvas.axes_init()
