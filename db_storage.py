import os
import pathlib
import sqlite3
from typing import Any, Dict, List, Optional
from uuid import uuid4


class DbStorage:
    """
    SQLite storage.

    Schema v1:
    - UUIDs stored as TEXT (uuid4())
    - projects have a stable project_path (TEXT UNIQUE)
    """

    SCHEMA_VERSION = 1

    def __init__(self, file_path: str = "db_storage.dat"):
        self.cursor = None
        self.conn = None
        self.file_path = file_path
        self.connect()

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
                project_path TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )

        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS boreholes (
                borehole_id TEXT NOT NULL PRIMARY KEY,
                borehole_name TEXT NOT NULL,
                length REAL,
                depth REAL,
                fissure_inside INTEGER,
                project_id TEXT NOT NULL REFERENCES projects (project_id) ON DELETE CASCADE
            );
            """
        )

        # Borehole structure (Stage 2): sections & steps
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
                creation_date TEXT,
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
            "CREATE INDEX IF NOT EXISTS idx_projects_project_path ON projects(project_path);"
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

    def _migrate_legacy_to_v1(self) -> None:
        """
        Best-effort migration from legacy (no project_path, bigint ids) to schema v1.
        """
        legacy_tables = ["wind_roses", "frequency_characteristics", "files", "boreholes", "projects"]
        has_any_legacy = any(self._table_exists(t) for t in legacy_tables)
        if not has_any_legacy:
            self._create_schema_v1()
            self._set_user_version(self.SCHEMA_VERSION)
            return

        if not self._table_exists("projects") or self._table_has_column("projects", "project_path"):
            self._create_schema_v1()
            self._set_user_version(self.SCHEMA_VERSION)
            return

        with self.conn:
            for t in legacy_tables:
                if self._table_exists(t):
                    self.cursor.execute(f"ALTER TABLE {t} RENAME TO {t}_old;")

            self._create_schema_v1()

            if self._table_exists("projects_old"):
                self.cursor.execute(
                    """
                    INSERT INTO projects(project_id, project_name, project_path, created_at)
                    SELECT
                        CAST(project_id AS TEXT),
                        project_name,
                        'legacy:' || CAST(project_id AS TEXT),
                        datetime('now')
                    FROM projects_old;
                    """
                )

            if self._table_exists("boreholes_old"):
                self.cursor.execute(
                    """
                    INSERT INTO boreholes(borehole_id, borehole_name, length, depth, fissure_inside, project_id)
                    SELECT
                        CAST(borehole_id AS TEXT),
                        borehole_name,
                        length,
                        depth,
                        fissure_inside,
                        CAST(project_id AS TEXT)
                    FROM boreholes_old;
                    """
                )

            if self._table_exists("files_old"):
                self.cursor.execute(
                    """
                    INSERT INTO files(file_id, file_name, borehole_id, part_of_file_id, creation_date, data)
                    SELECT
                        CAST(file_id AS TEXT),
                        file_name,
                        CAST(borehole_id AS TEXT),
                        part_of_file_id,
                        creation_date,
                        data
                    FROM files_old;
                    """
                )

            if self._table_exists("frequency_characteristics_old"):
                self.cursor.execute(
                    """
                    INSERT INTO frequency_characteristics(borehole_id, file_id, frequency_characteristic_id)
                    SELECT
                        CAST(borehole_id AS TEXT),
                        CAST(file_id AS TEXT),
                        frequency_characteristic_id
                    FROM frequency_characteristics_old;
                    """
                )

            if self._table_exists("wind_roses_old"):
                self.cursor.execute(
                    """
                    INSERT INTO wind_roses(borehole_id, file_id, wind_rose_id, measurement_id)
                    SELECT
                        CAST(borehole_id AS TEXT),
                        CAST(file_id AS TEXT),
                        wind_rose_id,
                        measurement_id
                    FROM wind_roses_old;
                    """
                )

            for t in legacy_tables:
                old = f"{t}_old"
                if self._table_exists(old):
                    self.cursor.execute(f"DROP TABLE {old};")

            self._set_user_version(self.SCHEMA_VERSION)

    def _ensure_schema(self) -> None:
        version = self._get_user_version()
        if version >= self.SCHEMA_VERSION:
            self._create_schema_v1()
            self.conn.commit()
            return
        if self._table_exists("projects") and not self._table_has_column("projects", "project_path"):
            self._migrate_legacy_to_v1()
            self.conn.commit()
            return
        self._create_schema_v1()
        self._set_user_version(self.SCHEMA_VERSION)
        self.conn.commit()

    @staticmethod
    def _normalize_project_path(path: str) -> str:
        return str(pathlib.Path(path).expanduser().resolve())

    def create_project(self, name: str, path: str) -> str:
        project_id = str(uuid4())
        project_path = self._normalize_project_path(path)
        with self.conn:
            try:
                self.cursor.execute(
                    """
                    INSERT INTO projects(project_id, project_name, project_path)
                    VALUES (?, ?, ?);
                    """,
                    (project_id, name, project_path),
                )
            except sqlite3.IntegrityError as e:
                raise ValueError(f"Проект с путём уже существует: {project_path}") from e
        return project_id

    def get_project_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        project_path = self._normalize_project_path(path)
        row = self.cursor.execute(
            """
            SELECT project_id, project_name, project_path, created_at
            FROM projects
            WHERE project_path = ?
            LIMIT 1;
            """,
            (project_path,),
        ).fetchone()
        return dict(row) if row else None

    def get_project_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        row = self.cursor.execute(
            """
            SELECT project_id, project_name, project_path, created_at
            FROM projects
            WHERE project_id = ?
            LIMIT 1;
            """,
            (project_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_or_create_borehole_for_project(
        self,
        project_id: str,
        borehole_name: str,
        length: Optional[float] = None,
        depth: Optional[float] = None,
        fissure_inside: Optional[bool] = None,
    ) -> Dict[str, Any]:
        row = self.cursor.execute(
            """
            SELECT borehole_id, borehole_name, length, depth, fissure_inside, project_id
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
                INSERT INTO boreholes(borehole_id, borehole_name, length, depth, fissure_inside, project_id)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    borehole_id,
                    borehole_name,
                    length,
                    depth,
                    None if fissure_inside is None else (1 if fissure_inside else 0),
                    project_id,
                ),
            )
        return {
            "borehole_id": borehole_id,
            "borehole_name": borehole_name,
            "length": length,
            "depth": depth,
            "fissure_inside": None if fissure_inside is None else (1 if fissure_inside else 0),
            "project_id": project_id,
        }

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

    def get_borehole_structure(self, borehole_id: str) -> List[Dict[str, Any]]:
        """
        Returns borehole structure as:
        [
          {section_id, name, depth, length, is_selected, sort_order, steps: [...]},
          ...
        ]
        """
        sections = self.get_sections(borehole_id)
        for s in sections:
            s["steps"] = self.get_steps(s["section_id"])
        return sections

    def replace_borehole_structure(self, borehole_id: str, sections: List[Dict[str, Any]]) -> None:
        """
        Replaces all sections/steps for the borehole in a single transaction.
        Expected input:
        sections = [
          {
            name: str, depth: float|int, length: float|int, is_selected: bool|int,
            steps: [{number: int, is_selected: bool|int}, ...]
          },
          ...
        ]
        """
        with self.conn:
            # Delete existing structure (CASCADE deletes steps).
            self.cursor.execute("DELETE FROM sections WHERE borehole_id = ?;", (borehole_id,))

            for section_order, s in enumerate(sections):
                section_id = str(uuid4())
                self.cursor.execute(
                    """
                    INSERT INTO sections(section_id, borehole_id, name, depth, length, is_selected, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        section_id,
                        borehole_id,
                        s["name"],
                        float(s.get("depth", 0) or 0),
                        float(s.get("length", 0) or 0),
                        1 if s.get("is_selected", True) else 0,
                        int(s.get("sort_order", section_order)),
                    ),
                )

                steps = s.get("steps") or []
                for step_order, st in enumerate(steps):
                    step_id = str(uuid4())
                    self.cursor.execute(
                        """
                        INSERT INTO steps(step_id, section_id, number, is_selected, sort_order)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (
                            step_id,
                            section_id,
                            int(st["number"]),
                            1 if st.get("is_selected", True) else 0,
                            int(st.get("sort_order", step_order)),
                        ),
                    )