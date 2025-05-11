import sys
from PySide6.QtWidgets import (
    QApplication, QDialog, QLabel, QComboBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QTextEdit
)
import psycopg2

def get_values_from_postgres(query):
    conn = psycopg2.connect(
        dbname="Avellon_v8",
        user="postgres",
        password="postgres",
        host="localhost",
        port=5432
    )
    cur = conn.cursor()
    cur.execute(query)
    result = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return result

# class IndicatorLabel(QLabel):
#     def __init__(self, color="green", diameter=12):
#         super().__init__()
#         self.setFixedSize(diameter, diameter)
#         self.set_color(color)
#
#     def set_color(self, color):
#         self.setStyleSheet(f"""
#             background-color: {color};
#             border-radius: {self.width() // 2}px;
#             border: 1px solid black;
#         """)

class DefectDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Добавление дефекта")
        self.resize(400, 300)

        # # Надпись и индикатор
        # label = QLabel("Сегмент:")
        # self.indicator = IndicatorLabel("green")  # начальный цвет
        #
        # layout = QHBoxLayout()
        # layout.addWidget(label)
        # layout.addWidget(self.indicator)
        # layout.addStretch()

        # --- Сектор ---
        sector_label = QLabel("Сектор:")
        self.sector_combo = QComboBox()
        self.sector_combo.addItems(get_values_from_postgres("SELECT sector_code FROM sectors"))

        sector_layout = QHBoxLayout()
        sector_layout.addWidget(sector_label)
        sector_layout.addWidget(self.sector_combo)

        # --- Объект контроля ---
        control_object_label = QLabel("Объект контроля:")
        self.control_object_combo = QComboBox()
        self.control_object_combo.addItems(get_values_from_postgres("SELECT object_name FROM control_objects"))

        control_object_layout = QHBoxLayout()
        control_object_layout.addWidget(control_object_label)
        control_object_layout.addWidget(self.control_object_combo)

        # --- Тип дефекта ---
        defect_label = QLabel("Тип дефекта:")
        self.defect_combo = QComboBox()
        self.defect_combo.addItems(get_values_from_postgres("SELECT type_name FROM defect_types"))

        defect_layout = QHBoxLayout()
        defect_layout.addWidget(defect_label)
        defect_layout.addWidget(self.defect_combo)

        # --- Степень критичности ---
        criticality_degree_label = QLabel("Степень критичности:")
        self.criticality_degree_combo = QComboBox()
        self.criticality_degree_combo.addItems(get_values_from_postgres("SELECT criticality_name FROM criticality_degrees"))

        criticality_degree_layout = QHBoxLayout()
        criticality_degree_layout.addWidget(criticality_degree_label)
        criticality_degree_layout.addWidget(self.criticality_degree_combo)

        # --- Комментарий ---
        comment_label = QLabel("Комментарий:")
        self.comment_text = QTextEdit()

        # --- Кнопка OK ---
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)

        # --- Основной layout ---
        main_layout = QVBoxLayout()
        main_layout.addLayout(sector_layout)
        main_layout.addLayout(defect_layout)
        main_layout.addLayout(control_object_layout)
        main_layout.addLayout(criticality_degree_layout)
        # main_layout.addLayout(layout)
        main_layout.addWidget(comment_label)
        main_layout.addWidget(self.comment_text)
        main_layout.addWidget(ok_button)

        self.setLayout(main_layout)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = DefectDialog()
    if dialog.exec():
        print("Выбранный сектор:", dialog.sector_combo.currentText())
        print("Выбранный тип дефекта:", dialog.defect_combo.currentText())
        print("Комментарий:", dialog.comment_text.toPlainText())