"""
Database setup script.
Creates tables and initializes the database.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from src.database.models import Base
from src.config import settings


def setup_database():
    """Create all database tables."""
    print("=" * 60)
    print("Setting up Polymarket Bot Database")
    print("=" * 60)

    # Convert asyncpg URL to psycopg2 for SQLAlchemy create_all
    db_url = settings.database.database_url.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg2://"
    )

    print(f"Database URL: {db_url.split('@')[1]}")  # Hide credentials

    try:
        # Create engine
        engine = create_engine(db_url)

        # Create all tables
        print("\nCreating tables...")
        Base.metadata.create_all(engine)

        print("✅ Database setup complete!")
        print("\nTables created:")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")

    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    setup_database()
