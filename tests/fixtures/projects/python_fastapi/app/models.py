"""
Database Models for FastAPI Fixture
"""

class Base:
    pass

class User(Base):
    id: int
    username: str
    email: str

class Item(Base):
    id: int
    title: str
    owner_id: int
