FROM python:3.11-alpine
EXPOSE 8855
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY webhook2rss.py .
COPY default_parsers.py .
COPY default_feeds.yaml .
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh
ENV PYTHONUNBUFFERED=1
ENV WEBHOOK2RSS_BASE_URL=http://localhost
ENV WEBHOOK2RSS_FEED_DEFINITIONS='/data/feeds.yaml'
ENV WEBHOOK2RSS_DATABASE='/data/events.db'
ENV WEBHOOK2RSS_PARSERS='/data/parsers.py'
ENV WEBHOOK2RSS_PORT=8855
ENTRYPOINT ["/entrypoint.sh"]
