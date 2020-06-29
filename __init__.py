from mycroft import intent_file_handler, intent_handler, MycroftSkill
from mycroft.skills.core import resting_screen_handler
from requests_cache import CachedSession
from datetime import timedelta, datetime
from mtranslate import translate
from mycroft.util import create_daemon
from mycroft.util.log import LOG
from adapt.intent import IntentBuilder
from lingua_franca.parse import extract_datetime
from lingua_franca.format import nice_date
import random
import feedparser
from time import mktime
import bs4


class SpaceNewsSkill(MycroftSkill):

    def __init__(self):
        super(SpaceNewsSkill, self).__init__(name="SpaceNewsSkill")
        if "hubblesite_esa_news" not in self.settings:
            # http://hubblesite.org/api/v3/external_feed/esa_feed?page=all
            self.settings["hubblesite_esa_news"] = True
        if "hubblesite_jwst_news" not in self.settings:
            # http://hubblesite.org/api/v3/external_feed/jwst_feed?page=all
            self.settings["hubblesite_jwst_news"] = True
        if "sf_news" not in self.settings:
            # https://spaceflightnewsapi.net/about
            self.settings["sf_news"] = True
        if "jpl_news" not in self.settings:
            # http://www.jpl.nasa.gov/multimedia/rss/news.xml
            self.settings["jpl_news"] = True
        if "nasa_breaking_news" not in self.settings:
            # https://www.nasa.gov/rss/dyn/breaking_news.rss
            self.settings["nasa_breaking_news"] = True
        if "nasa_education_news" not in self.settings:
            # https://www.nasa.gov/rss/dyn/educationnews.rss
            self.settings["nasa_education_news"] = True
        if "nasa_iss_news" not in self.settings:
            # https://www.nasa.gov/rss/dyn/shuttle_station.rss
            self.settings["nasa_iss_news"] = True
        if "nasa_solar_system_news" not in self.settings:
            # https://www.nasa.gov/rss/dyn/solar_system.rss
            self.settings["nasa_solar_system_news"] = True
        if "nasa_earth_news" not in self.settings:
            # https://www.nasa.gov/rss/dyn/earth.rss
            self.settings["nasa_earth_news"] = True
        if "nasa_aeronautics_news" not in self.settings:
            # https://www.nasa.gov/rss/dyn/aeronautics.rss
            self.settings["nasa_aeronautics_news"] = True
        if "nasa_ames" not in self.settings:
            # Ames Research Center News and Features
            # https://www.nasa.gov/rss/dyn/ames_news.rss
            self.settings["nasa_ames"] = True
        if "nasa_armstrong" not in self.settings:
            # Armstrong Flight Research Center News and Features
            # https://www.nasa.gov/rss/dyn/armstrong_news.rss
            self.settings["nasa_armstrong"] = True
        if "nasa_glenn" not in self.settings:
            # Glenn Research Center News and Features
            # https://www.nasa.gov/rss/dyn/glenn_features.rss
            self.settings["nasa_glenn"] = True
        if "nasa_goddard" not in self.settings:
            # Goddard Spaceflight Center News and Features
            # https://www.nasa.gov/rss/dyn/goddard-NewsFeature.rss
            self.settings["nasa_goddard"] = True
        if "nasa_johnson" not in self.settings:
            # Johnson Space Center
            # http://www.nasa.gov/rss/dyn/johnson_news.rss
            self.settings["nasa_johnson"] = True
        if "nasa_marshall" not in self.settings:
            # Marshall Spaceflight Center News and Features
            # https://www.nasa.gov/rss/dyn/msfc_news.rss
            self.settings["nasa_marshall"] = True
        if "nasa_stennis" not in self.settings:
            # Stennis Space Center News and Features
            # https://www.nasa.gov/rss/dyn/centers/stennis/news/latest_news.rss
            self.settings["nasa_stennis"] = True
        if "nasa_sti" not in self.settings:
            # NASA STI
            # http://www.sti.nasa.gov/scan/rss99-01.xml
            self.settings["nasa_sti"] = True
        if "nasa_reports" not in self.settings:
            # NASA STI Report Series
            # http://www.sti.nasa.gov/scan/rss99-02.xml
            self.settings["nasa_reports"] = True
        if "esa_news" not in self.settings:
            # ESA news
            # http://www.esa.int/rssfeed/Our_Activities/Space_News
            self.settings["esa_news"] = True
        if "esa_earth" not in self.settings:
            # ESA earth
            # http://www.esa.int/rssfeed/Our_Activities/Observing_the_Earth
            self.settings["esa_earth"] = True
        if "esa_flight" not in self.settings:
            # ESA Spaceflight
            # http://www.esa.int/rssfeed/Our_Activities/Human_Spaceflight
            self.settings["esa_flight"] = True
        if "esa_launchers" not in self.settings:
            # ESA Launchers
            # http://www.esa.int/rssfeed/Our_Activities/Launchers
            self.settings["esa_launchers"] = True
        if "esa_navigation" not in self.settings:
            # ESA Navigation
            # http://www.esa.int/rssfeed/Our_Activities/Navigation
            self.settings["esa_navigation"] = True
        if "esa_science" not in self.settings:
            # ESA Science
            # http://www.esa.int/rssfeed/Our_Activities/Space_Science
            self.settings["esa_science"] = True
        if "esa_tech" not in self.settings:
            # ESA space tech
            # http://www.esa.int/rssfeed/Our_Activities/Space_Engineering_Technology
            self.settings["esa_tech"] = True
        if "esa_operations" not in self.settings:
            # ESA operations
            # http://www.esa.int/rssfeed/Our_Activities/Operations
            self.settings["esa_operations"] = True
        if "esa_comms" not in self.settings:
            # ESA comms
            # http://www.esa.int/rssfeed/Our_Activities/Telecommunications_Integrated_Applications
            self.settings["esa_comms"] = True
        if "esa_education" not in self.settings:
            # ESA education
            # http://www.esa.int/rssfeed/Education
            self.settings["esa_education"] = True

        if "filter" not in self.settings:
            # ignore entries without picture
            self.settings["filter"] = True

        self.session = CachedSession(backend='memory',
                                     expire_after=timedelta(hours=1))
        self.translate_cache = {}
        self.current_news = 0
        self.total_news = 0
        self.already_said = []
        self.rss_cache = []

    def initialize(self):
        create_daemon(self.get_news)  # bootstrap cache
        self.update_rss_feeds()  # start periodic RSS parsing

    @staticmethod
    def parse_feed(url, author=""):
        news = []
        LOG.debug("Parsing feed: " + url)
        data = feedparser.parse(url)
        for new in data["entries"]:
            try:
                author = new["source"]["title"]
            except:
                pass
            caption = new["summary"]
            dt = datetime.fromtimestamp(mktime(new["published_parsed"]))
            d = {"title": new["title"],
                 "source": author,
                 "url": new["link"],
                 "caption": caption,
                 "date_str": dt.strftime("%Y-%m-%d"),
                 "datetime": dt}
            if new.get("tags"):
                d["tags"] = [t["term"] for t in new["tags"]]
            img = None
            for l in new["links"]:
                if l["type"] in ["image/jpeg"]:
                    img = l["href"]
            if img is None:
                html = new["summary"]
                soup = bs4.BeautifulSoup(html, "html.parser")
                img = soup.find("img")
                if img:
                    caption = soup.text.strip()
                    d["caption"] = caption
                    img = img["src"]
            if img:
                d["imgLink"] = img
            d["utterance"] = d["caption"] or d["title"] or "News from " + \
                             author
            news.append(d)
        return news

    def update_rss_feeds(self, event=None):
        now = datetime.now()
        next_update = now + timedelta(hours=1)
        news = []
        if self.settings["jpl_news"]:
            author = "NASA Jet Propulsion Laboratory"
            url = "http://www.jpl.nasa.gov/multimedia/rss/news.xml"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)

        if self.settings["nasa_breaking_news"]:
            author = "NASA Breaking News"
            url = "https://www.nasa.gov/rss/dyn/breaking_news.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)

        if self.settings["nasa_education_news"]:
            author = "NASA Education"
            url = "https://www.nasa.gov/rss/dyn/educationnews.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_iss_news"]:
            author = "NASA Space Station News"
            url = "https://www.nasa.gov/rss/dyn/shuttle_station.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_solar_system_news"]:
            author = "NASA Solar System News"
            url = "https://www.nasa.gov/rss/dyn/solar_system.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_earth_news"]:
            author = "NASA Earth News"
            url = "https://www.nasa.gov/rss/dyn/earth.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_aeronautics_news"]:
            author = "NASA Aeronautics News"
            url = "https://www.nasa.gov/rss/dyn/aeronautics.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_ames"]:
            author = "Ames Research Center News and Features"
            url = "https://www.nasa.gov/rss/dyn/ames_news.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_armstrong"]:
            author = "Armstrong Flight Research Center News and Features"
            url = "https://www.nasa.gov/rss/dyn/armstrong_news.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_glenn"]:
            author = "Glenn Research Center News and Features"
            url = "https://www.nasa.gov/rss/dyn/glenn_features.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_goddard"]:
            author = "Goddard Spaceflight Center News and Features"
            url = "https://www.nasa.gov/rss/dyn/goddard-NewsFeature.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_johnson"]:
            author = "Johnson Space Center"
            url = "http://www.nasa.gov/rss/dyn/johnson_news.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_marshall"]:
            author = "NASA Marshall Spaceflight Center News and Features"
            url = "https://www.nasa.gov/rss/dyn/msfc_news.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_stennis"]:
            author = "NASA Stennis Space Center News and Features"
            url = "https://www.nasa.gov/rss/dyn/centers/stennis/news/latest_news.rss"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_sti"]:
            author = "NASA STI"
            url = "http://www.sti.nasa.gov/scan/rss99-01.xml"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["nasa_reports"]:
            author = "NASA STI Reports"
            url = "http://www.sti.nasa.gov/scan/rss99-02.xml"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_news"]:
            author = "ESA Space News"
            url = "http://www.esa.int/rssfeed/Our_Activities/Space_News"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_earth"]:
            author = "ESA Observing the Earth"
            url = "http://www.esa.int/rssfeed/Our_Activities/Observing_the_Earth"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_flight"]:
            author = "ESA Human Spaceflight"
            url = "http://www.esa.int/rssfeed/Our_Activities/Human_Spaceflight"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_launchers"]:
            author = "ESA Launchers"
            url = "http://www.esa.int/rssfeed/Our_Activities/Launchers"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_navigation"]:
            author = "ESA Navigation"
            url = "http://www.esa.int/rssfeed/Our_Activities/Navigation"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_science"]:
            author = "ESA Space Science"
            url = "http://www.esa.int/rssfeed/Our_Activities/Space_Science"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_tech"]:
            author = "ESA Space Engineering Technology"
            url = "http://www.esa.int/rssfeed/Our_Activities/Space_Engineering_Technology"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_operations"]:
            author = "ESA Operations"
            url = "http://www.esa.int/rssfeed/Our_Activities/Operations"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_comms"]:
            author = "ESA Telecommunications Integrated Applications"
            url = "http://www.esa.int/rssfeed/Our_Activities/Telecommunications_Integrated_Applications"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)
        if self.settings["esa_education"]:
            author = "ESA Education"
            url = "http://www.esa.int/rssfeed/Education"
            for new in self.parse_feed(url, author):
                if new not in news:
                    news.append(new)

        # remove duplicates (by title)
        titles = []
        for idx, n in enumerate(news):
            if n["title"] in titles:
                news[idx] = None
            else:
                titles.append(n["title"])
        self.rss_cache = [r for r in news if r]
        # sort
        self.rss_cache.sort(key=lambda r: r["datetime"], reverse=True)
        # update data in 1 hour
        self.schedule_event(self.update_rss_feeds, next_update)

    def get_news(self):
        news = list(self.rss_cache)
        if self.settings["hubblesite_esa_news"]:
            url = "http://hubblesite.org/api/v3/external_feed/esa_feed?page=all"
            data = self.session.get(url).json()
            for new in data:
                d = {"title": new["title"],
                     "source": "James Webb Telescope",
                     "caption": new["description"],
                     "utterance": new.get("description") or new["title"],
                     "date_str": new["pub_date"].split("T")[0],
                     "datetime": datetime.strptime(
                         new["pub_date"].split("T")[0], "%Y-%m-%d")}
                if new.get("image"):
                    d["thumbnail"] = "http:" + new["thumbnail"]
                    d["imgLink"] = "http:" + new["image"]
                news.append(d)

        if self.settings["hubblesite_jwst_news"]:
            url = "http://hubblesite.org/api/v3/external_feed/jwst_feed?page=all"
            data = self.session.get(url).json()
            for new in data:
                d = {"title": new["title"],
                     "source": "James Webb Telescope",
                     "caption": new["description"],
                     "utterance": new.get("description") or new["title"],
                     "date_str": new["pub_date"].split("T")[0],
                     "datetime": datetime.strptime(
                         new["pub_date"].split("T")[0], "%Y-%m-%d")}
                if new.get("image"):
                    d["thumbnail"] = "http:" + new["thumbnail"]
                    d["imgLink"] = "http:" + new["image"]
                news.append(d)

        if self.settings["sf_news"]:
            for url in ["https://spaceflightnewsapi.net/api/v1/reports",
                        "https://spaceflightnewsapi.net/api/v1/articles"]:
                data = self.session.get(url).json()["docs"]
                for new in data:
                    d = {"title": new["title"],
                         "source": new["news_site"],
                         "url": new["url"],
                         "caption": new.get("summary"),
                         "utterance": new.get("summary") or new["title"],
                         "date_str": new["published_date"].split("T")[0],
                         "datetime": datetime.strptime(
                             new["published_date"].split("T")[0], "%Y-%m-%d")}
                    if new.get("featured_image"):
                        d["imgLink"] = new["featured_image"]
                    news.append(d)

        if self.settings["filter"]:
            news = [n for n in news if n.get("imgLink")]
            #for idx, n in enumerate(news):
            #    status = self.session.get(n["imgLink"]).status_code
            #    print(status)
            #    if status != 200:
            #        news[idx] = None
            #news = [n for n in news if n]

        news.sort(key=lambda r: r["datetime"], reverse=True)

        self.total_news = len(news)
        return news

    def _tx_keys(self, bucket):
        tx = ["title", "caption"]
        for k in bucket:
            try:
                if not self.lang.startswith("en") and k in tx:
                    if isinstance(bucket[k], dict):
                        bucket[k] = self._tx_keys(bucket[k])
                    elif isinstance(bucket[k], list):
                        for idx, d in enumerate(bucket[k]):
                            bucket[k][idx] = self._tx_keys(d)
                    elif bucket[k] not in self.translate_cache:
                        translated = translate(str(bucket[k]), self.lang)
                        self.translate_cache[bucket[k]] = translated
                        bucket[k] = translated
                    else:
                        bucket[k] = self.translate_cache[bucket[k]]
            except:
                continue  # rate limit from google translate
        return bucket

    def _display_and_speak(self, news_idx=None, date=None):
        data = self.update_picture(news_idx, date)
        self.already_said.append(news_idx)
        self.speak_dialog("news", {"date": data["human_date"]})
        self.gui.show_image(data["imgLink"],
                            override_idle=True,
                            title=data["title"],
                            fill='PreserveAspectFit',
                            caption=data["caption"])
        self.speak(data["utterance"], wait=True)

    # idle screen
    def update_picture(self, idx=None, date=None):
        data = self.get_news()
        if idx is not None:
            data = data[idx]
            self.current_news = idx
        elif date is not None:
            if isinstance(date, datetime):
                date = date.date()

            def nearest(items, pivot):
                return min(items, key=lambda x: abs(x - pivot))

            dates = [d["datetime"].date() for d in data]
            date = nearest(dates, date)

            for d in data:
                if d["date_str"] == str(date):
                    data = d
                    break
            else:
                data = data[0]
                self.current_news = 0
                # TODO error dialog
        else:
            data = data[0]
            self.current_news = 0

        data = dict(self._tx_keys(data))
        date = data.pop("datetime")

        for k in data:
            self.gui[k] = data[k]
        self.set_context("space")
        self.set_context("url", data["url"])

        self.settings["raw"] = data
        data["human_date"] = nice_date(date, lang=self.lang)
        return data

    @resting_screen_handler("SpaceNews")
    def idle(self, message):
        idx = random.randint(0, 20)
        self.update_picture(idx)
        self.gui.clear()
        self.gui.show_image(self.gui["imgLink"],
                            override_idle=True,
                            fill='PreserveAspectFit',
                            caption=self.gui["caption"])

    # intents
    @intent_file_handler("recent.intent")
    def handle_recent_news_intent(self, message):
        news_idx = random.randint(0, 5)
        self._display_and_speak(news_idx)

    @intent_handler(IntentBuilder("SpaceNewsIntent")
                    .require("space").require("news"))
    def handle_news(self, message):
        date = extract_datetime(message.data["utterance"], lang="en")
        if date:
            self._display_and_speak(date=date[0])
        else:
            # avoid repeating news
            news_idx = len(self.already_said)
            if news_idx >= self.total_news - 1:
                news_idx = random.randint(0, self.total_news - 1)
            self._display_and_speak(news_idx)

    @intent_handler(IntentBuilder("SpaceNewsWebsiteIntent")
                    .optionally("space").optionally("news").require("website")
                    .require("open").require("url"))
    def handle_website(self, message):
        url = message.data["url"]
        self.gui.show_url(url, True)

    @intent_handler(IntentBuilder("PrevSpaceNewsIntent")
                    .require("previous").require("news").optionally("space"))
    @intent_handler(IntentBuilder("PrevSpaceNewsPictureIntent")
                    .require("previous").require("picture"))
    def handle_prev(self, message):
        news_idx = max(self.current_news - 1, 0)
        # TODO error dialog if out of range
        self._display_and_speak(news_idx)

    @intent_handler(IntentBuilder("NextSpaceNewsIntent")
                    .require("next").require("news").optionally("space"))
    @intent_handler(IntentBuilder("NextSpaceNewsPictureIntent")
                    .require("next").require("picture"))
    def handle_next(self, message):
        news_idx = min(self.current_news + 1, self.total_news - 1)
        # TODO error dialog if out of range
        self._display_and_speak(news_idx)


def create_skill():
    return SpaceNewsSkill()
