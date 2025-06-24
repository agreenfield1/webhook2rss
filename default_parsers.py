"""
How to Add a New Parser Function
-------------------------------

Each parser function converts incoming JSON data into a list of RSS feed items
that have the structure:
    {"title": str, "description": str, "link": str}

To create a new parser:
1. Define a function named `parse_<feed_id>(data: dict, feed_id)`
   - The function name must match the expected `feed_id` from the webhook route.
2. Extract the relevant fields from `data` and construct:
   - `title`     → A short headline summarizing the event.
   - `description` → A longer summary or message (can be optional or defaulted).
   - `link`      → A URL relevant to the item (can be static or dynamic).
3. Return a list of one or more dictionaries in the format above.

Example Template:

def parse_example(data: dict, feed_id):
    title = f"{data['field1']} - {data['field2']}"
    description = data.get("message", "No description.")
    link = "http://example.com/view"
    return [{"title": title, "description": description, "link": link}]

Notes:
- Use `data.get(..., default)` to handle missing fields gracefully.
- If the input contains a list of items, iterate and build multiple entries.
- Feed logic (e.g., filtering, formatting) belongs inside the parser.

"""

# def parse_sonarr(data: dict, feed_id):

    # series_title = data.get("series", {}).get("title", "N/A")
    # episode = data.get("episodes", [{}])[0]
    # season_num = episode.get("seasonNumber", "N/A")
    # episode_num = episode.get("episodeNumber", "N/A")

    # title = f"{series_title} - S{season_num:02}E{episode_num:02}"
    # description = episode.get("overview", "No overview provided")
    # link = f"http://docker.ajghs.com:8972/series/{data['series']['titleSlug']}"  #

    # return [{"title": title, "description": description, "link": link}]

