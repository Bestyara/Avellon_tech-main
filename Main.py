import sys
from PySide6.QtWidgets import QApplication

from db_storage import DbStorage
from main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    db = DbStorage()
    window = MainWindow(app, db)
    window.showMaximized()
    app.exec()


if __name__ == '__main__':
    main()
