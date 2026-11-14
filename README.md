# News Tracker

An installable web app of headlines from **Fox News**, **Fox Business**, **Tousi TV** and the **PBD Podcast**. Headlines, summaries and times are shown as the source published them. The app does not add commentary or invent stories.

Live: https://phillipalvaranga-arch.github.io/news-tracker/

## Sources

- Fox News RSS: `https://moxie.foxnews.com/google-publisher/{latest,us,world,politics,health,tech,sports}.xml`
- Fox Business RSS: `https://moxie.foxbusiness.com/google-publisher/{latest,markets,economy,technology,personal-finance,real-estate}.xml`
- Tousi TV YouTube channel ID `UCjJec0wv1EUomjrBNt1xCTA` (`@tousitv`)
- PBD Podcast YouTube channel ID `UCGX7nGXpz-CmO_Arg-cgJ7A` (`@pbdpodcast`)

Fox News does not publish a Texas or DFW RSS feed at that host, so that section is not included.

A GitHub Action runs every 15 minutes, fetches the feeds, and writes `data/news.json`. The last about 300 items are kept. Browsers cannot read the feeds directly because of CORS.

Saved stories stay on your device only.
