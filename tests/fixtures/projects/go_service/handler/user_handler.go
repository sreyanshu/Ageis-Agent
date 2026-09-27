package handler

import (
	"net/http"
	"github.com/gin-gonic/gin"
	"example.com/goservice/service"
)

type UserHandler struct {
	Service *service.UserService
}

func (h *UserHandler) GetUser(c *gin.Context) {
	user := h.Service.GetUser(1)
	c.JSON(http.StatusOK, user)
}
