from pathlib import Path
from aegis.indexer.python_indexer import PythonASTIndexer
from aegis.indexer.js_ts_indexer import JavaScriptTypeScriptIndexer
from aegis.indexer.go_indexer import GoIndexer
from aegis.indexer.base import SymbolType, RelationType


def test_python_ast_indexer():
    indexer = PythonASTIndexer()
    code = """
import os
from app.models import User

class UserService:
    def __init__(self, repo):
        self.repo = repo

    def get_user(self, user_id: int) -> User:
        return self.repo.find(user_id)

@app.get("/api/v1/users")
def list_users():
    return []

def test_user_service():
    pass
"""
    indexed = indexer.index_file(workspace_root=".", relative_path="app/services.py", content=code)
    assert indexed.file_path == "app/services.py"
    assert len(indexed.symbols) >= 5

    sym_names = [s.name for s in indexed.symbols]
    assert "UserService" in sym_names
    assert "get_user" in sym_names
    assert "GET /api/v1/users" in sym_names
    assert "test_user_service" in sym_names

    # Check relation types
    rel_types = [r.relation for r in indexed.relationships]
    assert RelationType.IMPORTS in rel_types
    assert RelationType.EXPOSES_API in rel_types
    assert RelationType.TESTS in rel_types


def test_js_ts_indexer():
    indexer = JavaScriptTypeScriptIndexer()
    code = """
import React from 'react';
import { fetchUsers } from './api';

export interface UserProps {
  id: number;
}

export class UserProfile extends React.Component {
  render() { return <div>User</div>; }
}

export function UserCard(props: UserProps) {
  fetch('/api/users');
  return <div>Card</div>;
}

it('should render card', () => {
  expect(true).toBe(true);
});
"""
    indexed = indexer.index_file(workspace_root=".", relative_path="src/UserCard.tsx", content=code)
    assert indexed.language == "typescript"
    sym_types = [s.symbol_type for s in indexed.symbols]
    assert SymbolType.INTERFACE in sym_types
    assert SymbolType.COMPONENT in sym_types
    assert SymbolType.TEST in sym_types

    rel_types = [r.relation for r in indexed.relationships]
    assert RelationType.IMPORTS in rel_types
    assert RelationType.CONSUMES_API in rel_types


def test_go_indexer():
    indexer = GoIndexer()
    code = """
package service

import (
    "fmt"
    "example.com/goservice/repo"
)

type UserService struct {
    Repo *repo.UserRepository
}

func (s *UserService) GetUser(id int) string {
    return "user"
}

func TestUserService(t *testing.T) {
}
"""
    indexed = indexer.index_file(workspace_root=".", relative_path="service/user_service.go", content=code)
    assert indexed.language == "go"
    sym_names = [s.name for s in indexed.symbols]
    assert "UserService" in sym_names
    assert "GetUser" in sym_names
    assert "TestUserService" in sym_names

    rel_types = [r.relation for r in indexed.relationships]
    assert RelationType.IMPORTS in rel_types
    assert RelationType.CONTAINS in rel_types
