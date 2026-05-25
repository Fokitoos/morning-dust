from pydantic import BaseModel


class TodoItem(BaseModel):
    id: int | None = None
    title: str
    done: bool = False


class TodoCreate(BaseModel):
    title: str


class TodoUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


class TodoListResponse(BaseModel):
    items: list[TodoItem]
