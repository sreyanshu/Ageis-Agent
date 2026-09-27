from app.models import User, Item

class UserRepository:
    def get_by_id(self, user_id: int) -> User:
        return User()

    def create(self, username: str) -> User:
        return User()

class ItemRepository:
    def list_all(self) -> list[Item]:
        return []
