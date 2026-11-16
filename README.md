# News Tracker

An installable web app of headlines from **Fox News**, **Fox Business**, the **Associated Press**, **Reuters**, **NewsNation**, **Tousi TV** and the **PBD Podcast**. Headlines, summaries and times are shown as the source published them. The app does not add commentary or invent stories.

Live: https://phillipalvaranga-arch.github.io/news-tracker/

## Sources

- Fox News RSS: `https://moxie.foxnews.com/google-publisher/{latest,us,world,politics,health,tech,sports}.xml`
- Fox Business RSS: `https://moxie.foxbusiness.com/google-publisher/{latest,markets,economy,technology,personal-finance,real-estate}.xml`
- Associated Press: official Flipboard magazines, with links to apnews.com (AP no longer offers a working public RSS feed on apnews.com)
- Reuters: Google News RSS limited to `site:reuters.com` (Reuters ended public RSS feeds in 2020)
- NewsNation official RSS: `https://www.newsnationnow.com/feed/` and section feeds
- Tousi TV YouTube channel ID `UCjJec0wv1EUomjrBNt1xCTA` (`@tousitv`)
- PBD Podcast YouTube channel ID `UCGX7nGXpz-CmO_Arg-cgJ7A` (`@pbdpodcast`)

This app does not use CNN, MSN or MSNBC. Fox News does not publish a Texas or DFW RSS feed at that host, so that section is not included.

AllSides, checked on Nov 15, 2026, rates Reuters and NewsNation as Center and the Associated Press as Lean Left (online news coverage).

A GitHub Action runs every 15 minutes, fetches the feeds, and writes `data/news.json`. The last about 400 items are kept, with a minimum from each source. Browsers cannot read the feeds directly because of CORS.

Saved stories stay on your device only.
