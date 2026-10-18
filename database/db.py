
import aiosqlite

from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "bookingbot.db"


async def init_db() -> None:
    """Создаёт таблицы и добавляет демонстрационные услуги."""

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                price INTEGER NOT NULL CHECK (price >= 0),
                duration_minutes INTEGER NOT NULL
                    CHECK (duration_minutes > 0),
                is_active INTEGER NOT NULL DEFAULT 1
                    CHECK (is_active IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                is_available INTEGER NOT NULL DEFAULT 1
                    CHECK (is_available IN (0, 1)),
                CHECK (ends_at > starts_at),
                UNIQUE (starts_at, ends_at)
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                slot_id INTEGER NOT NULL,
                client_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'confirmed'
                    CHECK (
                        status IN (
                            'confirmed',
                            'cancelled',
                            'completed'
                        )
                    ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (user_id)
                    REFERENCES users(user_id),

                FOREIGN KEY (service_id)
                    REFERENCES services(id),

                FOREIGN KEY (slot_id)
                    REFERENCES slots(id)
            );

            CREATE UNIQUE INDEX IF NOT EXISTS
                unique_active_booking_per_slot
            ON bookings(slot_id)
            WHERE status IN ('confirmed', 'completed');

            CREATE INDEX IF NOT EXISTS bookings_by_user
            ON bookings(user_id);

            CREATE INDEX IF NOT EXISTS bookings_by_date
            ON bookings(slot_id, status);
            """
        )

        await db.executemany(
            """
            INSERT OR IGNORE INTO services
                (name, description, price, duration_minutes)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    "Мужская стрижка",
                    "Классическая мужская стрижка",
                    1500,
                    60,
                ),
                (
                    "Стрижка бороды",
                    "Коррекция и оформление бороды",
                    700,
                    30,
                ),
                (
                    "Комплекс",
                    "Стрижка и оформление бороды",
                    2000,
                    90,
                ),
            ],
        )

        await db.commit()


async def get_active_services() -> list[dict]:
    """Возвращает все активные услуги."""

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT id, name, description, price, duration_minutes
            FROM services
            WHERE is_active = 1
            ORDER BY id
            """
        )

        rows = await cursor.fetchall()
        await cursor.close()

        return [dict(row) for row in rows]
