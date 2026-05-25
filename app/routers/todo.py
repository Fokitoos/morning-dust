from fastapi import APIRouter

from app.schemas.todo import TodoItem, TodoListResponse

router = APIRouter()


@router.get("", response_model=TodoListResponse)
def list_todos() -> TodoListResponse:
    return TodoListResponse(items=[])


@router.post("", response_model=TodoItem, status_code=201)
def create_todo(item: TodoItem) -> TodoItem:
    return item
