package repository

type User struct {
	ID   int
	Name string
}

type UserRepository struct{}

func (r *UserRepository) FindByID(id int) *User {
	return &User{ID: id, Name: "Alice"}
}
