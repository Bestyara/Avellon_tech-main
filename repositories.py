import json
import os
import pathlib
import sqlite3
from typing import Any, Dict, List, Optional
from uuid import uuid4


class BaseRepository:
    def __init__(self, storage: "DbStorage"):
        self.storage = storage

    @property
    def conn(self):
        return self.storage.conn

    @property
    def cursor(self):
        return self.storage.cursor


class ProjectsRepository(BaseRepository):
    @staticmethod
    def _normalize_project_name(name: str) -> str:
        return (name or "").strip()

    def create_project(self, name: str) -> str:
        project_name = self._normalize_project_name(name)
        if not project_name:
            raise ValueError("Название проекта не может быть пустым.")

        existing = self.cursor.execute(
            """
            SELECT project_id
            FROM projects
            WHERE lower(trim(project_name)) = lower(trim(?))
            LIMIT 1;
            """,
            (project_name,),
        ).fetchone()
        if existing:
            return str(existing["project_id"])

        project_id = str(uuid4())
        with self.conn:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO projects(project_id, project_name)
                    VALUES (?, ?);
                    """,
                    (project_id, project_name),
                )
            except sqlite3.IntegrityError as e:
                raise ValueError("Не удалось создать проект из-за конфликта данных.") from e
        return project_id

    def get_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        project_name = self._normalize_project_name(name)
        if not project_name:
            return None
        row = self.cursor.execute(
            """
            SELECT project_id, project_name, created_at
            FROM projects
            WHERE lower(trim(project_name)) = lower(trim(?))
            ORDER BY datetime(created_at) DESC
            LIMIT 1;
            """,
            (project_name,),
        ).fetchone()
        return dict(row) if row else None

    def update_project_last_opened(self, project_id: Optional[str]) -> None:
        if not project_id:
            return

        with self.conn:
            self.cursor.execute(
                """
                UPDATE projects
                SET last_time_opened = datetime('now')
                WHERE project_id = ?;
                """,
                (project_id,),
            )

    def get_last_opened_project(self) -> Optional[Dict[str, Any]]:
        row = self.cursor.execute(
            """
            SELECT project_id,
                   project_name,
                   created_at,
                   last_time_opened
            FROM projects
            ORDER BY COALESCE(last_time_opened, created_at) DESC,
                     created_at DESC,
                     rowid DESC
            LIMIT 1;
            """
        ).fetchone()
        return dict(row) if row else None

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        row = self.cursor.execute(
            """
            SELECT project_id, project_name, created_at
            FROM projects
            WHERE project_id = ?
            LIMIT 1;
            """,
            (project_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_project_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self.get_project(project_id)

    def list_projects(self) -> List[Dict[str, Any]]:
        rows = self.cursor.execute(
            """
            SELECT project_id, project_name, created_at
            FROM projects
            ORDER BY datetime(created_at) DESC, project_name ASC;
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def get_or_create_borehole_for_project(
        self,
        project_id: str,
        borehole_name: str,
    ) -> Dict[str, Any]:
        row = self.cursor.execute(
            """
            SELECT borehole_id, borehole_name, project_id
            FROM boreholes
            WHERE project_id = ? AND borehole_name = ?
            LIMIT 1;
            """,
            (project_id, borehole_name),
        ).fetchone()
        if row:
            return dict(row)

        borehole_id = str(uuid4())
        with self.conn:
            self.cursor.execute(
                """
                INSERT INTO boreholes(borehole_id, borehole_name, project_id)
                VALUES (?, ?, ?);
                """,
                (
                    borehole_id,
                    borehole_name,
                    project_id,
                ),
            )
        return {
            "borehole_id": borehole_id,
            "borehole_name": borehole_name,
            "project_id": project_id,
        }


class SectionsRepository(BaseRepository):
    def get_sections(self, borehole_id: str) -> List[Dict[str, Any]]:
        rows = self.cursor.execute(
            """
            SELECT section_id, borehole_id, name, depth, length, is_selected, sort_order
            FROM sections
            WHERE borehole_id = ?
            ORDER BY sort_order ASC, name ASC;
            """,
            (borehole_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def replace_borehole_structure(self, borehole_id: str, sections: List[Dict[str, Any]]) -> None:
        with self.conn:
            self.cursor.execute("DELETE FROM sections WHERE borehole_id = ?;", (borehole_id,))
            for section_order, section_data in enumerate(sections):
                section_id = str(uuid4())
                self.cursor.execute(
                    """
                    INSERT INTO sections(section_id, borehole_id, name, depth, length, is_selected, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        section_id,
                        borehole_id,
                        section_data["name"],
                        float(section_data.get("depth", 0) or 0),
                        float(section_data.get("length", 0) or 0),
                        1 if section_data.get("is_selected", True) else 0,
                        int(section_data.get("sort_order", section_order)),
                    ),
                )

                steps = section_data.get("steps") or []
                for step_order, step_data in enumerate(steps):
                    self.cursor.execute(
                        """
                        INSERT INTO steps(step_id, section_id, number, is_selected, sort_order)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (
                            str(uuid4()),
                            section_id,
                            int(step_data["number"]),
                            1 if step_data.get("is_selected", True) else 0,
                            int(step_data.get("sort_order", step_order)),
                        ),
                    )


class StepsRepository(BaseRepository):
    def get_steps(self, section_id: str) -> List[Dict[str, Any]]:
        rows = self.cursor.execute(
            """
            SELECT step_id, section_id, number, is_selected, sort_order
            FROM steps
            WHERE section_id = ?
            ORDER BY sort_order ASC, number ASC;
            """,
            (section_id,),
        ).fetchall()
        return [dict(r) for r in rows]


class FilesRepository(BaseRepository):
    @staticmethod
    def _normalize_file_path(path: str) -> str:
        return str(pathlib.Path(path).expanduser().resolve())

    def get_file_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        if not file_id:
            return None
        has_file_path = self.storage._table_has_column("files", "file_path")
        select_file_path = ", file_path" if has_file_path else ""
        try:
            row = self.cursor.execute(
                f"""
                SELECT file_id,
                       file_name,
                       borehole_id,
                       part_of_file_id,
                       creation_date,
                       data
                       {select_file_path}
                FROM files
                WHERE file_id = ?
                LIMIT 1;
                """,
                (str(file_id),),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(row) if row else None

    def list_files_for_borehole(self, borehole_id: str) -> List[Dict[str, Any]]:
        has_file_path = self.storage._table_has_column("files", "file_path")
        select_file_path = ", file_path" if has_file_path else ""
        try:
            rows = self.cursor.execute(
                f"""
                SELECT file_id,
                       file_name,
                       borehole_id,
                       part_of_file_id,
                       creation_date,
                       data
                       {select_file_path}
                FROM files
                WHERE borehole_id = ?
                ORDER BY datetime(creation_date) DESC, rowid DESC;
                """,
                (borehole_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(r) for r in rows]

    def upsert_file_data(
        self,
        borehole_id: str,
        file_path: str,
        file_name: str,
        part_of_file_id: int,
        payload: Dict[str, Any],
        file_id: Optional[str] = None,
    ) -> Optional[str]:
        serialized = json.dumps(payload, ensure_ascii=False)
        normalized_path = None
        try:
            if file_path:
                normalized_path = self._normalize_file_path(file_path)
        except Exception:
            normalized_path = None

        try:
            with self.conn:
                if file_id:
                    existing = self.cursor.execute(
                        "SELECT file_id FROM files WHERE file_id = ? LIMIT 1;",
                        (str(file_id),),
                    ).fetchone()
                    if not existing:
                        return None
                    if self.storage._table_has_column("files", "file_path"):
                        self.cursor.execute(
                            """
                            UPDATE files
                            SET file_name = ?,
                                borehole_id = ?,
                                part_of_file_id = ?,
                                creation_date = datetime('now'),
                                data = ?,
                                file_path = COALESCE(?, file_path)
                            WHERE file_id = ?;
                            """,
                            (
                                file_name,
                                borehole_id,
                                int(part_of_file_id),
                                serialized,
                                normalized_path,
                                str(file_id),
                            ),
                        )
                    else:
                        self.cursor.execute(
                            """
                            UPDATE files
                            SET file_name = ?,
                                borehole_id = ?,
                                part_of_file_id = ?,
                                creation_date = datetime('now'),
                                data = ?
                            WHERE file_id = ?;
                            """,
                            (
                                file_name,
                                borehole_id,
                                int(part_of_file_id),
                                serialized,
                                str(file_id),
                            ),
                        )
                    return str(file_id)

                file_id = str(uuid4())
                if self.storage._table_has_column("files", "file_path"):
                    self.cursor.execute(
                        """
                        INSERT INTO files(
                            file_id,
                            file_name,
                            borehole_id,
                            part_of_file_id,
                            creation_date,
                            data,
                            file_path
                        )
                        VALUES (?, ?, ?, ?, datetime('now'), ?, ?);
                        """,
                        (
                            file_id,
                            file_name,
                            borehole_id,
                            int(part_of_file_id),
                            serialized,
                            normalized_path,
                        ),
                    )
                else:
                    self.cursor.execute(
                        """
                        INSERT INTO files(
                            file_id,
                            file_name,
                            borehole_id,
                            part_of_file_id,
                            creation_date,
                            data
                        )
                        VALUES (?, ?, ?, ?, datetime('now'), ?);
                        """,
                        (
                            file_id,
                            file_name,
                            borehole_id,
                            int(part_of_file_id),
                            serialized,
                        ),
                    )
                return file_id
        except sqlite3.OperationalError:
            return None


class GraphsRepository(BaseRepository):
    def replace_frequency_characteristics_for_borehole(
        self,
        borehole_id: str,
        rows: List[tuple[str, int]],
    ) -> None:
        with self.conn:
            self.cursor.execute(
                "DELETE FROM frequency_characteristics WHERE borehole_id = ?;",
                (borehole_id,),
            )
            if not rows:
                return
            self.cursor.executemany(
                """
                INSERT INTO frequency_characteristics(borehole_id, file_id, frequency_characteristic_id)
                VALUES (?, ?, ?);
                """,
                [
                    (borehole_id, str(file_id), int(frequency_characteristic_id))
                    for file_id, frequency_characteristic_id in rows
                ],
            )

    def replace_wind_roses_for_borehole(
        self,
        borehole_id: str,
        rows: List[tuple[str, int, int]],
    ) -> None:
        with self.conn:
            self.cursor.execute(
                "DELETE FROM wind_roses WHERE borehole_id = ?;",
                (borehole_id,),
            )
            if not rows:
                return
            self.cursor.executemany(
                """
                INSERT INTO wind_roses(borehole_id, file_id, wind_rose_id, measurement_id)
                VALUES (?, ?, ?, ?);
                """,
                [
                    (borehole_id, str(file_id), int(wind_rose_id), int(measurement_id))
                    for file_id, wind_rose_id, measurement_id in rows
                ],
            )


class DbStorage:
    SCHEMA_VERSION = 1

    def __init__(self, file_path: str = "storage.dat"):
        self.cursor = None
        self.conn = None
        self.file_path = file_path
        self.connect()

        self.projects = ProjectsRepository(self)
        self.sections = SectionsRepository(self)
        self.steps = StepsRepository(self)
        self.files = FilesRepository(self)
        self.graphs = GraphsRepository(self)
        self._repos = (
            self.projects,
            self.sections,
            self.steps,
            self.files,
            self.graphs,
        )

    def connect(self) -> None:
        os.makedirs(str(pathlib.Path(self.file_path).parent or "."), exist_ok=True)
        self.conn = sqlite3.connect(self.file_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.cursor.execute("PRAGMA foreign_keys = ON;")
        self._ensure_schema()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
        self.conn = None
        self.cursor = None

    def _get_user_version(self) -> int:
        row = self.cursor.execute("PRAGMA user_version;").fetchone()
        return int(row[0]) if row else 0

    def _set_user_version(self, version: int) -> None:
        self.cursor.execute(f"PRAGMA user_version = {int(version)};")

    def _table_exists(self, name: str) -> bool:
        row = self.cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?;",
            (name,),
        ).fetchone()
        return row is not None

    def _table_has_column(self, table: str, column: str) -> bool:
        rows = self.cursor.execute(f"PRAGMA table_info({table});").fetchall()
        return any(r["name"] == column for r in rows)

    def _create_schema_v1(self) -> None:
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT NOT NULL PRIMARY KEY,
                project_name TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_time_opened TIMESTAMP
            );
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS boreholes (
                borehole_id TEXT NOT NULL PRIMARY KEY,
                borehole_name TEXT NOT NULL,
                project_id TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE
            );
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sections (
                section_id TEXT NOT NULL PRIMARY KEY,
                borehole_id TEXT NOT NULL REFERENCES boreholes (borehole_id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                depth REAL NOT NULL DEFAULT 0,
                length REAL NOT NULL DEFAULT 0,
                is_selected INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                UNIQUE (borehole_id, name)
            );
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS steps (
                step_id TEXT NOT NULL PRIMARY KEY,
                section_id TEXT NOT NULL REFERENCES sections (section_id) ON DELETE CASCADE,
                number INTEGER NOT NULL,
                is_selected INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                UNIQUE (section_id, number)
            );
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT NOT NULL PRIMARY KEY,
                file_name TEXT NOT NULL,
                borehole_id TEXT NOT NULL REFERENCES boreholes (borehole_id) ON DELETE CASCADE,
                part_of_file_id INTEGER NOT NULL,
                creation_date TIMESTAMP,
                data JSON NOT NULL
            );
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS frequency_characteristics (
                borehole_id TEXT NOT NULL REFERENCES boreholes (borehole_id) ON DELETE CASCADE,
                file_id TEXT NOT NULL REFERENCES files (file_id) ON DELETE CASCADE,
                frequency_characteristic_id INTEGER NOT NULL
            );
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wind_roses (
                borehole_id TEXT NOT NULL REFERENCES boreholes (borehole_id) ON DELETE CASCADE,
                file_id TEXT NOT NULL REFERENCES files (file_id) ON DELETE CASCADE,
                wind_rose_id INTEGER NOT NULL,
                measurement_id INTEGER NOT NULL
            );
            """
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_boreholes_project_id ON boreholes(project_id);"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sections_borehole_id ON sections(borehole_id);"
        )
        self.cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_steps_section_id ON steps(section_id);"
        )

    def _ensure_schema(self) -> None:
        self._create_schema_v1()
        self._set_user_version(self.SCHEMA_VERSION)
        self.conn.commit()

    def get_borehole_structure(self, borehole_id: str) -> List[Dict[str, Any]]:
        sections = self.sections.get_sections(borehole_id)
        for section in sections:
            section["steps"] = self.steps.get_steps(section["section_id"])
        return sections

    def __getattr__(self, item: str):
        for repo in self._repos:
            if hasattr(repo, item):
                return getattr(repo, item)
        raise AttributeError(f"{self.__class__.__name__!s} has no attribute {item!r}")
