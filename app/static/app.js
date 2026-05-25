const REFRESH_MS = 60_000;
const TODO_REFRESH_MS = 30_000;

const els = {
    weather: document.getElementById("weather"),
    weatherLocation: document.getElementById("weather-location"),
    weatherTemp: document.getElementById("weather-temp"),
    weatherCondition: document.getElementById("weather-condition"),
    weatherHigh: document.getElementById("weather-high"),
    weatherLow: document.getElementById("weather-low"),
    weatherUpdated: document.getElementById("weather-updated"),
    clockTime: document.getElementById("clock-time"),
    clockDate: document.getElementById("clock-date"),
    todoList: document.getElementById("todo-list"),
    todoForm: document.getElementById("todo-form"),
    todoInput: document.getElementById("todo-input"),
};

function formatTime(date) {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDate(date) {
    return date.toLocaleDateString([], {
        weekday: "long",
        day: "numeric",
        month: "long",
    });
}

function formatTemp(value) {
    return value == null ? "--°" : `${Math.round(value)}°`;
}

async function refreshWeather() {
    try {
        const resp = await fetch("/api/weather", { cache: "no-store" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        els.weatherLocation.textContent = data.location;
        els.weatherTemp.textContent = formatTemp(data.temperature_c);
        els.weatherCondition.textContent = data.condition;
        els.weatherHigh.textContent = formatTemp(data.temperature_max_c);
        els.weatherLow.textContent = formatTemp(data.temperature_min_c);
        els.weatherUpdated.textContent = `updated ${formatTime(new Date())}`;
        els.weather.classList.remove("stale");
    } catch (err) {
        els.weather.classList.add("stale");
        els.weatherUpdated.textContent = `offline — last try ${formatTime(new Date())}`;
    }
}

function tickClock() {
    const now = new Date();
    els.clockTime.textContent = formatTime(now);
    els.clockDate.textContent = formatDate(now);
}

function renderTodos(items) {
    els.todoList.replaceChildren();
    for (const item of items) {
        const li = document.createElement("li");
        li.className = "todo-item" + (item.done ? " done" : "");

        const label = document.createElement("span");
        label.className = "todo-check";
        label.textContent = item.title;
        label.addEventListener("click", () => toggleTodo(item));

        const del = document.createElement("span");
        del.className = "todo-delete";
        del.textContent = "×";
        del.addEventListener("click", () => deleteTodo(item.id));

        li.append(label, del);
        els.todoList.append(li);
    }
}

async function refreshTodos() {
    try {
        const resp = await fetch("/api/todo", { cache: "no-store" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const data = await resp.json();
        renderTodos(data.items);
    } catch (err) {
        /* leave existing list visible */
    }
}

async function toggleTodo(item) {
    await fetch(`/api/todo/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ done: !item.done }),
    });
    refreshTodos();
}

async function deleteTodo(id) {
    await fetch(`/api/todo/${id}`, { method: "DELETE" });
    refreshTodos();
}

els.todoForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = els.todoInput.value.trim();
    if (!title) return;
    els.todoInput.value = "";
    await fetch("/api/todo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
    });
    refreshTodos();
});

tickClock();
setInterval(tickClock, 1000);

refreshWeather();
setInterval(refreshWeather, REFRESH_MS);

refreshTodos();
setInterval(refreshTodos, TODO_REFRESH_MS);
