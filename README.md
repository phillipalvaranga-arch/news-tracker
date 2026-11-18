# News Tracker

An installable web app of headlines from **Fox News**, **Fox Business**, **Reuters**, **NewsNation**, **Tousi TV** and the **PBD Podcast**. Headlines, summaries and times are shown as the source published them. The app does not add commentary or invent stories.

Live: https://phillipalvaranga-arch.github.io/news-tracker/

## Sources

- Fox News RSS: `https://moxie.foxnews.com/google-publisher/{latest,us,world,politics,health,tech,sports}.xml`
- Fox Business RSS: `https://moxie.foxbusiness.com/google-publisher/{latest,markets,economy,technology,personal-finance,real-estate}.xml`
- Reuters: Google News RSS limited to `site:reuters.com` (Reuters ended public RSS feeds in 2020). Only items whose Google News source is reuters.com are kept.
- NewsNation official RSS: `https://www.newsnationnow.com/feed/` and section feeds
- Tousi TV YouTube channel ID `UCjJec0wv1EUomjrBNt1xCTA` (`@tousitv`)
- PBD Podcast YouTube channel ID `UCGX7nGXpz-CmO_Arg-cgJ7A` (`@pbdpodcast`)

This app does not use CNN, MSN, MSNBC, the Associated Press, The New York Times, The Washington Post, NPR, ABC, CBS or NBC, and it does not pull those outlets in through Google News or Flipboard. Fox News does not publish a Texas or DFW RSS feed at that host, so that section is not included.

AllSides ratings, checked on Nov 17, 2026 (online news coverage):

- Fox News Digital: Right — https://www.allsides.com/news-source/fox-news-media-bias
- Fox Business: Lean Right — https://www.allsides.com/news-source/fox-business-media-bias
- Reuters: Center — https://www.allsides.com/news-source/reuters-media-bias
- NewsNation: Center — https://www.allsides.com/news-source/newsnation-media-bias
- Tousi TV and the PBD Podcast: not rated by AllSides (kept because they were chosen for this app)

Sources AllSides rates Left or Lean Left, including the Associated Press, are not included.

A GitHub Action runs every 15 minutes, fetches the feeds, and writes `data/news.json`. The last about 400 items are kept, with a minimum from each source. Browsers cannot read the feeds directly because of CORS.

Saved stories stay on your device only.
