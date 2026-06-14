import json
from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from app.schemas.todo import TodoCreate, TodoItem, TodoListResponse, TodoUpdate


class TodoService:
    def __init__(self, file_path: Path) -> None:
        self._path = file_path

    def _load(self) -> list[TodoItem]:
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text() or "[]")
        return [TodoItem(**item) for item in raw]

    def _save(self, items: list[TodoItem]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps([i.model_dump() for i in items], indent=2))

    def list(self) -> TodoListResponse:
        return TodoListResponse(items=self._load())

    def create(self, payload: TodoCreate) -> TodoItem:
        items = self._load()
        next_id = (max((i.id or 0) for i in items) + 1) if items else 1
        item = TodoItem(id=next_id, title=payload.title, done=False)
        items.append(item)
        self._save(items)
        return item

    def update(self, todo_id: int, payload: TodoUpdate) -> TodoItem | None:
        items = self._load()
        for i, item in enumerate(items):
            if item.id == todo_id:
                if payload.title is not None:
                    item.title = payload.title
                if payload.done is not None:
                    item.done = payload.done
                items[i] = item
                self._save(items)
                return item
        return None

    def delete(self, todo_id: int) -> bool:
        items = self._load()
        remaining = [i for i in items if i.id != todo_id]
        if len(remaining) == len(items):
            return False
        self._save(remaining)
        return True


def get_todo_service(list_name: str) -> TodoService:
    # Whitelist guards against path traversal via the {list_name} path param.
    if list_name not in settings.todo_lists:
        raise HTTPException(status_code=404, detail=f"Unknown list: {list_name}")
    path = Path(settings.todo_dir) / f"todos-{list_name}.json"
    return TodoService(path)
