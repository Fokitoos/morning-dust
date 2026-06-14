// Reusable todo-list widget. Wires a list element + add-form to one named
// backend list (/api/todo/{listName}). Used by both the dashboard groceries
// widget and the standalone tasks page.
function createTodoList({ listName, listEl, formEl, inputEl }) {
    const base = `/api/todo/${listName}`;

    function render(items) {
        listEl.replaceChildren();
        for (const item of items) {
            const li = document.createElement("li");
            li.className = "todo-item" + (item.done ? " done" : "");

            const label = document.createElement("span");
            label.className = "todo-check";
            label.textContent = item.title;
            label.addEventListener("click", () => toggle(item));

            const del = document.createElement("span");
            del.className = "todo-delete";
            del.textContent = "×";
            del.addEventListener("click", () => remove(item.id));

            li.append(label, del);
            listEl.append(li);
        }
    }

    async function refresh() {
        try {
            const resp = await fetch(base, { cache: "no-store" });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            render((await resp.json()).items);
        } catch (err) {
            /* leave existing list visible */
        }
    }

    async function toggle(item) {
        await fetch(`${base}/${item.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ done: !item.done }),
        });
        refresh();
    }

    async function remove(id) {
        await fetch(`${base}/${id}`, { method: "DELETE" });
        refresh();
    }

    formEl.addEventListener("submit", async (e) => {
        e.preventDefault();
        const title = inputEl.value.trim();
        if (!title) return;
        inputEl.value = "";
        await fetch(base, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title }),
        });
        refresh();
    });

    return { refresh };
}
