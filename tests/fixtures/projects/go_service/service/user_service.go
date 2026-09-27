package service

import "example.com/goservice/repository"

type UserService struct {
	Repo *repository.UserRepository
}

func (s *UserService) GetUser(id int) *repository.User {
	return s.Repo.FindByID(id)
}
