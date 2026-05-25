from pydantic import BaseModel


class TodoItem(BaseModel):
    id: int | None = None
    title: str
    done: bool = False


class TodoListResponse(BaseModel):
    items: list[TodoItem]
