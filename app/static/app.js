const REFRESH_MS = 60_000;
const TODO_REFRESH_MS = 30_000;
const CALENDAR_REFRESH_MS = 5 * 60_000;

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
    commute: document.getElementById("commute"),
    commuteRoute: document.getElementById("commute-route"),
    commuteDuration: document.getElementById("commute-duration"),
    commuteMeta: document.getElementById("commute-meta"),
    commuteRefresh: document.getElementById("commute-refresh"),
    calendar: document.getElementById("calendar"),
    calendarList: document.getElementById("calendar-list"),
    calendarEmpty: document.getElementById("calendar-empty"),
    taskList: document.getElementById("task-list"),
    taskForm: document.getElementById("task-form"),
    taskInput: document.getElementById("task-input"),
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

const groceries = createTodoList({
    listName: "groceries",
    listEl: els.todoList,
    formEl: els.todoForm,
    inputEl: els.todoInput,
});

const tasks = createTodoList({
    listName: "tasks",
    listEl: els.taskList,
    formEl: els.taskForm,
    inputEl: els.taskInput,
});

function renderCommute(data) {
    els.commuteRoute.textContent = `${data.origin} → ${data.destination}`;
    if (data.status === "no_api_key") {
        els.commuteDuration.textContent = "--";
        els.commuteMeta.textContent = "set MORNING_DUST_TOMTOM_API_KEY";
        els.commute.classList.add("stale");
        return;
    }
    if (data.status === "not_configured") {
        els.commuteDuration.textContent = "--";
        els.commuteMeta.textContent = "set origin & destination in settings";
        els.commute.classList.add("stale");
        return;
    }
    if (data.duration_minutes != null) {
        let label = `${data.duration_minutes} min`;
        if (data.traffic_delay_minutes != null && data.traffic_delay_minutes > 0) {
            label += ` (+${data.traffic_delay_minutes})`;
        }
        els.commuteDuration.textContent = label;
    } else {
        els.commuteDuration.textContent = "--";
    }
    const parts = [];
    if (data.typical_duration_minutes != null) {
        parts.push(`usually ${data.typical_duration_minutes} min`);
    }
    if (data.distance_km != null) parts.push(`${data.distance_km} km`);
    if (data.last_updated) {
        const t = new Date(data.last_updated);
        parts.push(`updated ${formatTime(t)}`);
    }
    if (data.status === "error") parts.push("(refresh failed)");
    if (data.status === "stale") parts.push("(awaiting first refresh)");
    els.commuteMeta.textContent = parts.join(" • ") || "—";
    els.commute.classList.toggle("stale", data.status !== "ok");
}

async function refreshCommute() {
    try {
        const resp = await fetch("/api/commute", { cache: "no-store" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        renderCommute(await resp.json());
    } catch (err) {
        els.commute.classList.add("stale");
    }
}

async function triggerCommuteRefresh() {
    els.commuteRefresh.classList.add("spinning");
    els.commuteRefresh.disabled = true;
    try {
        const resp = await fetch("/api/commute/refresh", { method: "POST" });
        if (resp.ok) renderCommute(await resp.json());
    } finally {
        els.commuteRefresh.classList.remove("spinning");
        els.commuteRefresh.disabled = false;
    }
}

function sameDay(a, b) {
    return a.getFullYear() === b.getFullYear()
        && a.getMonth() === b.getMonth()
        && a.getDate() === b.getDate();
}

function dayChip(date) {
    const today = new Date();
    const tomorrow = new Date();
    tomorrow.setDate(today.getDate() + 1);
    if (sameDay(date, today)) return "Today";
    if (sameDay(date, tomorrow)) return "Tomorrow";
    return date.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short" });
}

function renderCalendar(data) {
    els.calendarList.replaceChildren();
    els.calendar.classList.toggle("stale", data.status !== "ok");

    if (data.status === "not_configured") {
        els.calendarEmpty.textContent = "set MORNING_DUST_CALENDAR_ICS_URLS";
        return;
    }
    if (!data.events || data.events.length === 0) {
        els.calendarEmpty.textContent =
            data.status === "error" ? "calendar unavailable" : "nothing coming up";
        return;
    }
    els.calendarEmpty.textContent = "";

    for (const ev of data.events) {
        const start = new Date(ev.start);

        const li = document.createElement("li");
        li.className = "calendar-item";

        const when = document.createElement("div");
        when.className = "calendar-when";
        const day = document.createElement("span");
        day.className = "calendar-day";
        day.textContent = dayChip(start);
        when.append(day, document.createTextNode(ev.all_day ? "all day" : formatTime(start)));

        const body = document.createElement("div");
        body.className = "calendar-body";
        const title = document.createElement("div");
        title.className = "calendar-title";
        title.textContent = ev.title;
        body.append(title);
        if (ev.location) {
            const loc = document.createElement("div");
            loc.className = "calendar-location";
            loc.textContent = ev.location;
            body.append(loc);
        }

        li.append(when, body);
        els.calendarList.append(li);
    }
}

async function refreshCalendar() {
    try {
        const resp = await fetch("/api/calendar", { cache: "no-store" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        renderCalendar(await resp.json());
    } catch (err) {
        els.calendar.classList.add("stale");
        els.calendarEmpty.textContent = "calendar offline";
    }
}

els.commuteRefresh.addEventListener("click", triggerCommuteRefresh);

tickClock();
setInterval(tickClock, 1000);

refreshWeather();
setInterval(refreshWeather, REFRESH_MS);

groceries.refresh();
setInterval(groceries.refresh, TODO_REFRESH_MS);

tasks.refresh();
setInterval(tasks.refresh, TODO_REFRESH_MS);

refreshCommute();
setInterval(refreshCommute, 5 * 60_000);

refreshCalendar();
setInterval(refreshCalendar, CALENDAR_REFRESH_MS);
