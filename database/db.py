
import aiosqlite

from datetime import date, datetime, timedelta
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent.parent / "bookingbot.db"

WORKING_HOURS = [10, 12, 14, 16, 18]
SLOT_DURATION_HOURS = 2


async def init_db() -> None:
    """Создаёт таблицы, услуги и расписание на ближайшие 7 дней."""

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

        today = date.today()

        for day_offset in range(7):
            current_date = today + timedelta(days=day_offset)

            for hour in WORKING_HOURS:
                starts_at = datetime(
                    current_date.year,
                    current_date.month,
                    current_date.day,
                    hour,
                    0,
                )
                ends_at = starts_at + timedelta(
                    hours=SLOT_DURATION_HOURS
                )

                await db.execute(
                    """
                    INSERT OR IGNORE INTO slots
                        (starts_at, ends_at, is_available)
                    VALUES (?, ?, 1)
                    """,
                    (
                        starts_at.strftime("%Y-%m-%d %H:%M"),
                        ends_at.strftime("%Y-%m-%d %H:%M"),
                    ),
                )

        await db.commit()


async def get_active_services() -> list[dict]:
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


async def get_all_services() -> list[dict]:
    """Возвращает все услуги, включая отключённые."""

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT id, name, description, price,
                   duration_minutes, is_active
            FROM services
            ORDER BY id
            """
        )

        rows = await cursor.fetchall()
        await cursor.close()

        return [dict(row) for row in rows]


async def add_service(
    name: str,
    description: str,
    price: int,
    duration_minutes: int,
) -> int | None:
    """Добавляет услугу. Возвращает ID или None при дубликате."""

    name = name.strip()
    description = description.strip()

    if not name or price < 0 or duration_minutes <= 0:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        try:
            cursor = await db.execute(
                """
                INSERT INTO services
                    (name, description, price, duration_minutes)
                VALUES (?, ?, ?, ?)
                """,
                (name, description, price, duration_minutes),
            )

            service_id = cursor.lastrowid
            await cursor.close()
            await db.commit()

            return service_id

        except aiosqlite.IntegrityError:
            await db.rollback()
            return None


async def update_service_price(
    service_id: int,
    new_price: int,
) -> bool:
    """Изменяет цену услуги."""

    if new_price < 0:
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE services
            SET price = ?
            WHERE id = ?
            """,
            (new_price, service_id),
        )

        changed = cursor.rowcount == 1
        await cursor.close()
        await db.commit()

        return changed


async def set_service_active(
    service_id: int,
    is_active: bool,
) -> bool:
    """Включает или отключает услугу, сохраняя историю записей."""

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE services
            SET is_active = ?
            WHERE id = ?
            """,
            (1 if is_active else 0, service_id),
        )

        changed = cursor.rowcount == 1
        await cursor.close()
        await db.commit()

        return changed


async def get_available_dates() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT DISTINCT substr(starts_at, 1, 10)
            FROM slots
            WHERE is_available = 1
              AND starts_at >= ?
            ORDER BY starts_at
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M"),),
        )

        rows = await cursor.fetchall()
        await cursor.close()

        return [row[0] for row in rows]


async def get_available_slots(booking_date: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT id, starts_at, ends_at
            FROM slots
            WHERE is_available = 1
              AND substr(starts_at, 1, 10) = ?
              AND starts_at >= ?
            ORDER BY starts_at
            """,
            (
                booking_date,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )

        rows = await cursor.fetchall()
        await cursor.close()

        return [dict(row) for row in rows]


async def create_booking(
    user_id: int,
    username: str | None,
    telegram_full_name: str,
    service_id: int,
    slot_id: int,
    client_name: str,
    phone: str,
) -> int | None:
    """Создаёт запись или возвращает None, если слот занят."""

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        try:
            await db.execute("BEGIN IMMEDIATE")

            cursor = await db.execute(
                """
                SELECT id
                FROM slots
                WHERE id = ?
                  AND is_available = 1
                  AND starts_at >= ?
                """,
                (
                    slot_id,
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ),
            )
            slot = await cursor.fetchone()
            await cursor.close()

            if slot is None:
                await db.rollback()
                return None

            cursor = await db.execute(
                """
                SELECT id
                FROM services
                WHERE id = ? AND is_active = 1
                """,
                (service_id,),
            )
            service = await cursor.fetchone()
            await cursor.close()

            if service is None:
                await db.rollback()
                return None

            await db.execute(
                """
                INSERT INTO users (user_id, username, full_name, phone)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    full_name = excluded.full_name,
                    phone = excluded.phone
                """,
                (user_id, username, telegram_full_name, phone),
            )

            cursor = await db.execute(
                """
                INSERT INTO bookings
                    (user_id, service_id, slot_id, client_name, phone)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, service_id, slot_id, client_name, phone),
            )

            booking_id = cursor.lastrowid
            await cursor.close()

            await db.execute(
                "UPDATE slots SET is_available = 0 WHERE id = ?",
                (slot_id,),
            )

            await db.commit()
            return booking_id

        except aiosqlite.IntegrityError:
            await db.rollback()
            return None

        except Exception:
            await db.rollback()
            raise


async def get_user_bookings(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                b.id AS booking_id,
                s.name AS service_name,
                s.price AS price,
                sl.starts_at AS starts_at,
                sl.ends_at AS ends_at
            FROM bookings b
            JOIN services s ON s.id = b.service_id
            JOIN slots sl ON sl.id = b.slot_id
            WHERE b.user_id = ?
              AND b.status = 'confirmed'
              AND sl.starts_at >= ?
            ORDER BY sl.starts_at
            """,
            (
                user_id,
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )

        rows = await cursor.fetchall()
        await cursor.close()

        return [dict(row) for row in rows]


async def get_cancellable_bookings(user_id: int) -> list[dict]:
    return await get_user_bookings(user_id)


async def cancel_user_booking(
    booking_id: int,
    user_id: int,
) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("BEGIN IMMEDIATE")

            cursor = await db.execute(
                """
                SELECT b.slot_id
                FROM bookings b
                JOIN slots sl ON sl.id = b.slot_id
                WHERE b.id = ?
                  AND b.user_id = ?
                  AND b.status = 'confirmed'
                  AND sl.starts_at >= ?
                """,
                (
                    booking_id,
                    user_id,
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ),
            )

            row = await cursor.fetchone()
            await cursor.close()

            if row is None:
                await db.rollback()
                return False

            slot_id = row[0]

            cursor = await db.execute(
                """
                UPDATE bookings
                SET status = 'cancelled'
                WHERE id = ?
                  AND user_id = ?
                  AND status = 'confirmed'
                """,
                (booking_id, user_id),
            )

            if cursor.rowcount != 1:
                await db.rollback()
                return False

            await cursor.close()

            await db.execute(
                """
                UPDATE slots
                SET is_available = 1
                WHERE id = ?
                """,
                (slot_id,),
            )

            await db.commit()
            return True

        except Exception:
            await db.rollback()
            raise


async def get_all_upcoming_bookings() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT
                b.id AS booking_id,
                b.user_id AS user_id,
                b.client_name AS client_name,
                b.phone AS phone,
                s.name AS service_name,
                s.price AS price,
                sl.starts_at AS starts_at,
                sl.ends_at AS ends_at
            FROM bookings b
            JOIN services s ON s.id = b.service_id
            JOIN slots sl ON sl.id = b.slot_id
            WHERE b.status = 'confirmed'
              AND sl.starts_at >= ?
            ORDER BY sl.starts_at
            """,
            (datetime.now().strftime("%Y-%m-%d %H:%M"),),
        )

        rows = await cursor.fetchall()
        await cursor.close()

        return [dict(row) for row in rows]
