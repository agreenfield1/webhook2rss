#!/bin/sh

PARSERS_FILE=$WEBHOOK2RSS_PARSERS
FEEDS_FILE=$WEBHOOK2RSS_FEED_DEFINITIONS

if [ ! -f "$PARSERS_FILE" ]; then
  echo "No parsers.py found"
  cp /app/default_parsers.py "$PARSERS_FILE"
fi

if [ ! -f "$FEEDS_FILE" ]; then
  echo "No feeds.yaml found"
  cp /app/default_feeds.yaml "$FEEDS_FILE"
fi

if [ "$DEV_MODE" = "1" ]; then
  export FLASK_ENV=development
  export FLASK_DEBUG=1
  echo "Starting Flask in development mode..."
  exec flask --app webhook2rss.py run --host=0.0.0.0 --port=$WEBHOOK2RSS_PORT
else
  export FLASK_ENV=production
  export FLASK_DEBUG=0
  echo "Starting Gunicorn in production mode..."
  exec gunicorn -b 0.0.0.0:$WEBHOOK2RSS_PORT webhook2rss:app
fi
