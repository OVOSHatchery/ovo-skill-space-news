from mycroft import intent_file_handler, intent_handler, MycroftSkill
from mycroft.skills.core import resting_screen_handler
from requests_cache import CachedSession
from datetime import timedelta, datetime
from mtranslate import translate
from mycroft.util import create_daemon
from adapt.intent import IntentBuilder
import random


class SpaceNewsSkill(MycroftSkill):

    def __init__(self):
        super(SpaceNewsSkill, self).__init__(name="SpaceNewsSkill")
        if "esa_news" not in self.settings:
            # http://hubblesite.org/api/v3/external_feed/esa_feed?page=all
            self.settings["esa_news"] = True
        if "jwst_news" not in self.settings:
            # http://hubblesite.org/api/v3/external_feed/jwst_feed?page=all
            self.settings["jwst_news"] = True
        if "sf_news" not in self.settings:
            # https://spaceflightnewsapi.net/about
            self.settings["sf_news"] = True
        if "filter" not in self.settings:
            # ignore entries without picture
            self.settings["filter"] = True
        self.session = CachedSession(backend='memory',
                                     expire_after=timedelta(hours=1))
        self.translate_cache = {}
        self.current_news = 0
        self.total_news = 0
        self.already_said = []
        create_daemon(self.get_news)  # bootstrap cache

    def get_news(self):
        news = []
        # date_str datetime
        if self.settings["esa_news"]:
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

        if self.settings["jwst_news"]:
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
        news.sort(key=lambda r: r["datetime"], reverse=True)
        for idx in range(len(news)):
            news[idx].pop("datetime")
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

    def _display_and_speak(self, news_idx):
        data = self.update_picture(news_idx)
        self.already_said.append(news_idx)
        self.gui.show_image(data["imgLink"],
                            override_idle=True,
                            title=data["title"],
                            fill='PreserveAspectFit',
                            caption=data["caption"])
        self.speak(data["utterance"], wait=True)

    # idle screen
    def update_picture(self, idx=None, date=None):
        data = self.get_news()
        self.settings["raw"] = data
        if idx is not None:
            data = data[idx]
            self.current_news = idx
        elif date is not None:
            if isinstance(date, datetime):
                date = date.date()
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

        data = self._tx_keys(data)
        for k in data:
            self.gui[k] = data[k]
        self.set_context("space")

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
        # avoid repeating news
        news_idx = len(self.already_said)
        if news_idx >= self.total_news - 1:
            news_idx = random.randint(0, self.total_news - 1)
        self._display_and_speak(news_idx)

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
