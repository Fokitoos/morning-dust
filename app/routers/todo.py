from fastapi import APIRouter, Depends, HTTPException

from app.schemas.todo import TodoCreate, TodoItem, TodoListResponse, TodoUpdate
from app.services.todo_service import TodoService, get_todo_service

router = APIRouter()


@router.get("", response_model=TodoListResponse)
def list_todos(
    service: TodoService = Depends(get_todo_service),
) -> TodoListResponse:
    return service.list()


@router.post("", response_model=TodoItem, status_code=201)
def create_todo(
    payload: TodoCreate,
    service: TodoService = Depends(get_todo_service),
) -> TodoItem:
    return service.create(payload)


@router.patch("/{todo_id}", response_model=TodoItem)
def update_todo(
    todo_id: int,
    payload: TodoUpdate,
    service: TodoService = Depends(get_todo_service),
) -> TodoItem:
    updated = service.update(todo_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return updated


@router.delete("/{todo_id}", status_code=204)
def delete_todo(
    todo_id: int,
    service: TodoService = Depends(get_todo_service),
) -> None:
    if not service.delete(todo_id):
        raise HTTPException(status_code=404, detail="Todo not found")
