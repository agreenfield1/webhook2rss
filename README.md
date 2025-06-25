# webhook2rss

**webhook2rss** is a lightweight web service that converts incoming webhook data into Atom feeds. You can define multiple feeds using YAML, and handle various webhook formats with pluggable parser functions written in Python.

---

## 🚀 Features

- Converts webhook POSTs into Atom feed entries
- Supports multiple feed types via a simple YAML config
- Customizable parsers for each feed (`parsers.py`)
- Secure feed updates via optional per-feed token
- Runs as a Flask app with Gunicorn (Docker-ready)

---

## 🛠️ Usage

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/webhook2rss.git
cd webhook2rss
```

### 2. Create Feed Definitions

Create a `feeds.yaml` file in `/data`:

```yaml
radarr:
  name: "Radarr Activity"
  description: "Radarr import feed"
  icon_url: "http://localhost:7878/favicon.ico"
  url: "http://localhost:7878"
  token: mysecrettoken
```

### 3. Write Parsers

Define a `parsers.py` file in `/data`:

```python
def parse_radarr(data: dict, feed_id):
    title = f"{data['movie']['title']} ({data['movie']['year']})"
    return [{
        "title": title,
        "description": data['movie'].get('overview', ''),
        "link": f"http://localhost:7878/movie/{data['movie']['tmdbId']}"
    }]
```

> One function per feed: must be named `parse_<feed_id>(data, feed_id)`

---

## 🐳 Running with Docker

### Quickstart:

```bash
docker build -t webhook2rss .
docker run -d -p 8855:8855 \
  -e WEBHOOK2RSS_BASE_URL=https://feeds.example.com \
  -v $(pwd)/data:/data \
  --name webhook2rss webhook2rss
```

> This will expose the app on port 8855 and mount your config from `./data`.

---

## 📥 Webhook Format

Send a POST request to `/webhook/<feed_id>?token=<token>` with JSON body.

```bash
curl -X POST http://localhost:8855/webhook/radarr?token=mysecrettoken \
     -H "Content-Type: application/json" \
     -d @example_payload.json
```

---

## 📡 Accessing the Feed

Atom feeds are available at:

```
GET /<feed_id>.atom
```

Example:

```
https://feeds.example.com/radarr.atom
```

---

## 📁 Folder Structure

```
/app
  ├── webhook2rss.py       # Main Flask app
  └── entrypoint.sh        # Docker entrypoint
/data
  ├── feeds.yaml           # User-defined feeds
  ├── events.db           # sqlite database
  └── parsers.py           # User-defined parser functions
```

---

## ✨ Environment Variables

| Variable                | Description                             | Default                  |
|-------------------------|-----------------------------------------|--------------------------|
| `WEBHOOK2RSS_PORT`      | Port to serve the app                   | `8855`                   |
| `WEBHOOK2RSS_BASE_URL`  | Base URL used in Atom feed `<id>`       | `http://localhost:8855`  |
| `WEBHOOK2RSS_FEEDS`     | Path to `feeds.yaml`                    | `/data/feeds.yaml`       |
| `WEBHOOK2RSS_PARSERS`   | Path to `parsers.py`                    | `/data/parsers.py`       |

---
---

## 🩺 Diagnostic Endpoints

The app provides several built-in endpoints to help with debugging, health monitoring, and inspecting stored feed data.

---

### 📘 `/feeds`

Returns metadata for all defined feeds from `feeds.yaml`.

---

### 📗 `/feeds/<feed_id>`

Returns all stored events for the specified feed.

---

### 📙 `/diagnostics`

Returns system-level debug information

---

### ✅ `/healthz`

A simple health check endpoint for Docker, Kubernetes, or uptime monitoring tools.

---

