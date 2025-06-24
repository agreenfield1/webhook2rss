from flask import Flask, request, Response, g, jsonify
import json
import sqlite3
import os
import argparse
import logging
from feedgen.feed import FeedGenerator
import sys
# import parsers
import yaml
import hashlib
import inspect
import importlib.util
from datetime import datetime, timezone

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATABASE = os.environ.get("WEBHOOK2RSS_DATABASE", "./data/events.db")
MAX_ITEMS = int(os.environ.get("WEBHOOK2RSS_MAX_ITEMS", 50))
PORT = int(os.environ.get("WEBHOOK2RSS_PORT", 8855))
BASE_URL = os.environ.get("WEBHOOK2RSS_BASE_URL", "http://localhost")
VERSION = "3.0"
FEED_DEFINITIONS = os.environ.get("WEBHOOK2RSS_FEED_DEFINITIONS", "./data/feeds.yaml")
PARSERS=os.environ.get("WEBHOOK2RSS_PARSERS", "./data/parsers.py")

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feeds (
                feed_id TEXT PRIMARY KEY,
                feed_name TEXT,     
                feed_description TEXT,
                feed_icon_url TEXT,
                feed_created_at TEXT,
                feed_url TEXT,
                feed_token
            )
        """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id TEXT,
                event_title TEXT,
                event_description TEXT,
                event_link TEXT,
                event_guid TEXT,
                event_pub_date TEXT
                raw_msg TEXT
                msg_hash TEXT
            )
        """
        )
    logger.info(f"sqlite database at {DATABASE} initialized")


def add_feed(feed_id=None):
    db = get_db()
    with open(FEED_DEFINITIONS, "r") as f:
        FEEDS = yaml.safe_load(f)
    with db:

        def create_one(feed_id):
            feed = FEEDS.get(feed_id)
            if feed is None:
                logger.error("Unable to create feed, no structure match to feed definitions")
                return feed_id

            db.execute(
                """
                INSERT OR REPLACE INTO feeds 
                (feed_id, feed_name, feed_description, feed_icon_url, feed_url, feed_created_at, feed_token)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    feed_id,
                    feed["name"],
                    feed["description"],
                    feed["icon_url"],
                    feed["url"],
                    datetime.now(timezone.utc).isoformat(),
                    feed["token"],
                ),
            )
            logger.info(f"created new feed ({feed_id})")

        if feed_id is None:
            for fid in FEEDS:
                create_one(fid)
        else:
            create_one(feed_id)
    return feed_id


def add_event(feed_id, item, data):
    db = get_db()
    try:
        with db:
            cur = db.execute(
                """
                INSERT INTO events (feed_id, event_title, event_description, event_link, event_guid, event_pub_date, raw_msg, msg_hash, is_test)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feed_id,
                    item["title"],
                    item["description"],
                    item["link"],
                    item["guid"],
                    item["pub_date"],
                    item["raw_msg"],
                    item["msg_hash"],
                    item["is_test"],
                ),
            )

            db.execute(
                """
                DELETE FROM events
                WHERE event_id NOT IN (
                    SELECT event_id FROM events
                    WHERE feed_id = ?
                    ORDER BY event_pub_date DESC
                    LIMIT ?
                ) AND feed_id = ?
                """,
                (feed_id, MAX_ITEMS, feed_id),
            )

        event_id = cur.lastrowid
        logger.info(f"Added event ({item['title']}) to feed ({feed_id})")
        return event_id
    except sqlite3.Error as e:
        logger.error(f"Database error in add_event for feed '{feed_id}': {e}")
        raise


def get_feed(feed_id=None):
    db = get_db()
    db.row_factory = sqlite3.Row
    cur = db.execute(
        """
        SELECT feed_id, feed_name, feed_description, feed_icon_url, feed_created_at, feed_url 
        FROM feeds
        """,
    )
    db_feeds = {row["feed_id"]: dict(row) for row in cur.fetchall()}
    with open(FEED_DEFINITIONS, "r") as f:
        yaml_feeds = yaml.safe_load(f)
    missing_keys = list(set(yaml_feeds) - set(db_feeds))

    # logger.debug(f"db feeds: {db_feeds}")
    # logger.debug(f"yaml feeds: {yaml_feeds}")
    # logger.debug(f"feed_id: {feed_id}")
    # logger.debug(f"Missing from db: {missing_keys}")

    if missing_keys:
        for key in missing_keys:
            add_feed(key)
        cur = db.execute(
            """
        SELECT feed_id, feed_name, feed_description, feed_icon_url, feed_created_at, feed_url 
        FROM feeds
        """,
        )
        db_feeds = [dict(row) for row in cur.fetchall()]

    if feed_id:
        return db_feeds[feed_id]
    else:
        return db_feeds

    # if results == None:
    # logger.info("feed entry not present, creating")
    # if feed_id is not None and results:
    # return results[0]
    # elif feed_id is None and results:
    # return results


def get_events(feed_id):
    db = get_db()
    cur = db.execute(
        """
        SELECT event_id, event_title, event_description, event_link, event_guid, event_pub_date
        FROM events WHERE feed_id = ?
        ORDER BY event_pub_date DESC
        LIMIT ?
        """,
        (feed_id, MAX_ITEMS),
    )
    events = [dict(row) for row in cur.fetchall()]
    return events


def get_diagnostics():
    result = {
        "diagnostics": {
            "DATABASE": DATABASE,
            "MAX_ITEMS": MAX_ITEMS,
            "PORT": PORT,
            "DEV_MODE": os.environ.get("DEV_MODE"),
            "PYTHONUNBUFFERED": os.environ.get("PYTHONUNBUFFERED"),
            "version": VERSION,
            "FLASK_ENV": os.environ.get("FLASK_ENV"),
            "FLASK_DEBUG": os.environ.get("FLASK_DEBUG"),
            "BASE_URL": BASE_URL,
            "FEED_DEFINITIONS": FEED_DEFINITIONS,
            "PARSERS": PARSERS
        }
    }
    return result


def parse_handler(data, feed_id):
    def make_id(timestamp: str, source_name: str) -> str:
        raw = f"{timestamp}-{source_name}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
        
    def structure_only(obj):
        if isinstance(obj, dict):
            return {k: structure_only(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return ""  # lists become empty string
        else:
            return ""  # all other values become empty string

    def hash_structure(structure):
        structure_json = json.dumps(structure, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(structure_json.encode("utf-8")).hexdigest()[:24]

    def get_parser(feed_id):
        parser_name = f"parse_{feed_id}"
        return getattr(parsers, parser_name, None)

    parser_func = get_parser(feed_id)
    if parser_func is None:
        raise ValueError(f"No parser found for feed '{feed_id}'")

    items = parser_func(data, feed_id)
    structure = structure_only(data)
    hashed_structure = hash_structure(structure)
    # logger.debug(json.dumps(structure, indent=2))
    
    for item in items:
        item["pub_date"] = datetime.now(timezone.utc).isoformat()
        item["guid"] = make_id(item["pub_date"], item["title"])
        item["is_test"] = data.get("test", 0)
        item["raw_msg"] = json.dumps(data)
        item["msg_hash"] = hashed_structure
    return items


if DATABASE:
    init_db()
    
parser_path = PARSERS
spec = importlib.util.spec_from_file_location("parsers", parser_path)
parsers = importlib.util.module_from_spec(spec)
sys.modules["parsers"] = parsers
spec.loader.exec_module(parsers)
    
current_module = sys.modules["parsers"]
functions = inspect.getmembers(current_module, inspect.isfunction)
function_names = [name for name, _ in functions]
logger.info("Available parsers: %s", function_names)

@app.route("/webhook/<feed_id>", methods=["POST"])
def webhook(feed_id):
    # data = request.get_json(silent=True) or {}
    data = request.get_json()
    
    try:
        items = parse_handler(data, feed_id)
        for item in items:
            add_event(feed_id, item, data)
        return jsonify({"status": "ok","feed_id":feed_id,"title":[d.get('title') for d in items]}), 200

    except Exception as e:
        logger.error(f"Failed to parse or add event for feed '{feed_id}': {e}")
        logger.error(f"Data: {json.dumps(data)}")
        return jsonify({"error": "ParseError", "message": str(e)}), 400


@app.route("/<feed_id>.atom")
def atom_feed(feed_id):
    try:
        feed = get_feed(feed_id)
        if not feed:
            raise Exception("requested feed does not exist")
        events = get_events(feed_id)

        fg = FeedGenerator()
        fg.id(f"{BASE_URL}:{PORT}/{feed_id}.atom")
        fg.title(feed["feed_name"])
        fg.link(href=feed["feed_url"], rel="alternate")
        fg.icon(feed["feed_icon_url"])
        fg.subtitle(feed["feed_description"])
        if events:
            fg.updated(datetime.fromisoformat(events[0]["event_pub_date"]))
        else:
            fg.updated(datetime.now(timezone.utc))

        for event in events:
            fe = fg.add_entry()
            fe.id(str(event["event_guid"]))
            fe.title(event["event_title"])
            fe.link(href=event["event_link"])
            fe.updated(datetime.fromisoformat(event["event_pub_date"]))
            fe.summary(event["event_description"])

        atom_xml = fg.atom_str(pretty=True)
        return Response(atom_xml, mimetype="application/atom+xml")

    except Exception as e:
        error_message = f"Error generating atom feed: {e}\n" f"URL: {request.url}\n" f"feed: {feed}"
        logger.exception(error_message)
        return Response(error_message, status=500, mimetype="text/plain")


@app.route("/diagnostics")
def diagnostics():
    result = get_diagnostics()
    return jsonify(result)


@app.route("/feeds")
def feeds_route():
    feeds = get_feed()  # feeds is now a dict keyed by feed_id
    for feed in feeds.values():
        events = get_events(feed["feed_id"])
        feed["count"] = len(events)
    return jsonify(feeds)


@app.route("/feeds/<feed_id>")
def events(feed_id):
    events = get_events(feed_id)
    return jsonify(events)


@app.route("/healthz")
def healthz():
    try:
        db = get_db()
        db.execute("SELECT 1")
        return "OK", 200
    except Exception:
        return "DB Error", 500


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Feed utility")
    parser.add_argument("--update-all", action="store_true", help="Update all feed configurations")
    parser.add_argument(
        "--update-feed",
        metavar="FEED_ID",
        type=str,
        help="Update specific feed configuration",
    )
    parser.add_argument("--show-feeds", action="store_true", help="List feeds")
    parser.add_argument("--show-diagnostics", action="store_true", help="List env vars and paths")
    parser.add_argument("--show-events", metavar="FEED_ID", type=str, help="List events")
    parser.add_argument("--db-path", metavar="PATH", type=str, help="Set database path")
    parser.add_argument("--run", action="store_true", help="Run Flask server")
    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(0)
    if args.db_path:
        DATABASE = args.db_path
    init_db()

    with app.app_context():
        if args.update_all:
            logger.info("updating database entry for all feeds")
            add_feed()
        if args.update_feed:
            logger.info(f"updating feed {args.update_feed}")
            add_feed(args.update_feed)
        if args.show_feeds:
            feeds = get_feed()
            for feed in feeds:
                events = get_events(feed["feed_id"])
                feed["count"] = len(events)
            logger.info(f"Feeds:\n{json.dumps(feeds, indent=2)}")
        if args.show_events:
            events = get_events(args.show_events)
            logger.info(f"Events:\n{json.dumps(events, indent=2)}")
        if args.show_diagnostics:
            result = get_diagnostics()
            logger.info(f"Diagnostics:\n{json.dumps(result, indent=2)}")
        if args.run:
            app.run(host="0.0.0.0", port=PORT)
