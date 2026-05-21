"""Add session_id and user_id to messages table

Chạy file này 1 lần để cập nhật database schema.
Dùng: python migrate_add_session.py
"""
from app.core.database import engine
from sqlalchemy import text


def migrate():
    with engine.connect() as conn:
        # Thêm cột session_id nếu chưa có
        try:
            conn.execute(text(
                "ALTER TABLE messages ADD COLUMN session_id VARCHAR(36)"
            ))
            print("✅ Thêm cột session_id thành công")
        except Exception as e:
            print(f"⚠️  session_id đã tồn tại hoặc lỗi: {e}")

        # Thêm cột user_id nếu chưa có
        try:
            conn.execute(text(
                "ALTER TABLE messages ADD COLUMN user_id INTEGER REFERENCES users(id)"
            ))
            print("✅ Thêm cột user_id thành công")
        except Exception as e:
            print(f"⚠️  user_id đã tồn tại hoặc lỗi: {e}")

        # Tạo index cho session_id để query nhanh hơn
        try:
            conn.execute(text(
                "CREATE INDEX idx_messages_session_id ON messages(session_id)"
            ))
            print("✅ Tạo index session_id thành công")
        except Exception as e:
            print(f"⚠️  Index đã tồn tại: {e}")

        conn.commit()
        print("\n✅ Migration hoàn tất!")


if __name__ == "__main__":
    migrate()