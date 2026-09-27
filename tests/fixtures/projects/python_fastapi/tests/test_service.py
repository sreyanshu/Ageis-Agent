from app.services import UserService

def test_find_user():
    service = UserService()
    user = service.find_user(1)
    assert user is not None

def test_register_user():
    service = UserService()
    user = service.register_user("john_doe")
    assert user is not None
