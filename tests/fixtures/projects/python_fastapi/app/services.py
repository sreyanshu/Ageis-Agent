from app.repositories import UserRepository, ItemRepository
from app.models import User, Item

class UserService:
    def __init__(self, repo: UserRepository = None):
        self.repo = repo or UserRepository()

    def find_user(self, user_id: int) -> User:
        return self.repo.get_by_id(user_id)

    def register_user(self, username: str) -> User:
        return self.repo.create(username)

class ItemService:
    def __init__(self, repo: ItemRepository = None):
        self.repo = repo or ItemRepository()

    def get_items(self) -> list[Item]:
        return self.repo.list_all()
