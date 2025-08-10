import sys, os, json, base64, threading, time, random
from datetime import datetime, timezone, timedelta
import requests
from colorama import Fore, init as colorama_init
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, Slot, Signal, QUrl
from PySide6.QtWebEngineCore import QWebEngineSettings

colorama_init(autoreset=True)
CONFIG_FILE = "config.json"
#---Speed---
SLEEP_TIME = 0

CHALLENGE_TYPES = [
 "assist","characterIntro","characterMatch","characterPuzzle","characterSelect",
 "characterTrace","characterWrite","completeReverseTranslation","definition","dialogue",
 "extendedMatch","extendedListenMatch","form","freeResponse","gapFill","judge","listen",
 "listenComplete","listenMatch","match","name","listenComprehension","listenIsolation",
 "listenSpeak","listenTap","orderTapComplete","partialListen","partialReverseTranslate",
 "patternTapComplete","radioBinary","radioImageSelect","radioListenMatch",
 "radioListenRecognize","radioSelect","readComprehension","reverseAssist","sameDifferent",
 "select","selectPronunciation","selectTranscription","svgPuzzle","syllableTap",
 "syllableListenTap","speak","tapCloze","tapClozeTable","tapComplete","tapCompleteTable",
 "tapDescribe","translate","transliterate","transliterationAssist","typeCloze",
 "typeClozeTable","typeComplete","typeCompleteTable","writeComprehension"
]

gem_rewards = ["SKILL_COMPLETION_BALANCED-…-2-GEMS"] * 100

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            return json.load(open(CONFIG_FILE, "r"))
        except json.JSONDecodeError as e:
            print(Fore.RED + f"Error parsing {CONFIG_FILE}: {e}")
            sys.exit(1)
    jwt = input("Enter your JWT: ").strip()
    try:
        payload = jwt.split(".")[1]
        padded = payload + "=" * (-len(payload) % 4)
        sub = json.loads(base64.urlsafe_b64decode(padded))["sub"]
    except Exception as e:
        print(Fore.RED + f"Failed to decode JWT: {e}")
        sys.exit(1)
    headers = {
        "authorization": f"Bearer {jwt}",
        "cookie": f"jwt_token={jwt}",
        "connection": "Keep-Alive",
        "content-type": "application/json",
        "user-agent": "Duolingo-Storm/1.0",
        "device-platform": "web",
        "x-duolingo-device-platform": "web",
        "x-duolingo-app-version": "1.0.0",
        "x-duolingo-application": "chrome",
        "x-duolingo-client-version": "web",
        "accept": "application/json"
    }
    r = requests.get(f"https://www.duolingo.com/2017-06-30/users/{sub}", headers=headers, timeout=15)
    if r.status_code != 200:
        print(Fore.RED + f"Failed to fetch profile: {r.status_code}")
        print(r.text)
        sys.exit(1)
    d = r.json()
    cfg = {"JWT": jwt,"UID": sub,"FROM": d.get("fromLanguage", "en"),"TO": d.get("learningLanguage", "fr")}
    json.dump(cfg, open(CONFIG_FILE, "w"))
    return cfg

cfg = load_config()
JWT, UID, FROM_LANG, TO_LANG = cfg["JWT"], cfg["UID"], cfg["FROM"], cfg["TO"]
STORY_SLUG = cfg.get("STORY_SLUG", "fr-en-le-passeport")
SLEEP_TIME = cfg.get("SLEEP_TIME", SLEEP_TIME)

HEADERS = {
    "authorization": f"Bearer {JWT}",
    "cookie": f"jwt_token={JWT}",
    "connection": "Keep-Alive",
    "content-type": "application/json",
    "user-agent": "Duolingo-Storm/1.0",
    "device-platform": "web",
    "x-duolingo-device-platform":"web",
    "x-duolingo-app-version": "1.0.0",
    "x-duolingo-application": "chrome",
    "x-duolingo-client-version": "web",
    "accept": "application/json"
}

BASE_URL = "https://www.duolingo.com/2017-06-30"
PROFILE_URL = f"{BASE_URL}/users/{UID}"
SESSIONS_URL = f"{BASE_URL}/sessions"
STORIES_URL = "https://stories.duolingo.com/api2/stories"

class Backend(QObject):
    updateProgress = Signal(int, int, float)
    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._stop_flag = threading.Event()
    @Slot(str, int)
    def start(self, mode, count):
        self._stop_flag.clear()
        threading.Thread(target=self.runFarm, args=(mode, count), daemon=True).start()
    @Slot()
    def stop(self):
        self._stop_flag.set()
    def runFarm(self, mode, count):
        if mode == "xp": self.farm_xp(count)
        elif mode == "gem": self.farm_gems(count)
        elif mode == "streak": self.farm_streak(count)
    def farm_xp(self, count):
        start_time = time.time()
        for i in range(count):
            if self._stop_flag.is_set(): break
            now_ts = int(datetime.now(timezone.utc).timestamp())
            payload = {"awardXp": True,"completedBonusChallenge": True,"fromLanguage": FROM_LANG,
                       "learningLanguage": TO_LANG,"hasXpBoost": False,"illustrationFormat": "svg",
                       "isFeaturedStoryInPracticeHub": True,"isLegendaryMode": True,"isV2Redo": False,
                       "isV2Story": False,"masterVersion": True,"maxScore": 0,"score": 0,
                       "happyHourBonusXp": 469,"startTime": now_ts,"endTime": now_ts}
            try:
                r = self.session.post(f"{STORIES_URL}/{STORY_SLUG}/complete", json=payload, timeout=20)
                if r.status_code != 200:
                    self.updateProgress.emit(i + 1, count, 0.0)
                    break
            except Exception:
                self.updateProgress.emit(i + 1, count, 0.0)
                break
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0.0
            self.updateProgress.emit(i + 1, count, rate)
            time.sleep(SLEEP_TIME)
    def farm_gems(self, count):
        start_time = time.time()
        for i in range(count):
            if self._stop_flag.is_set(): break
            random.shuffle(gem_rewards)
            for reward in gem_rewards:
                url = f"{BASE_URL}/users/{UID}/rewards/{reward}"
                payload = {"consumed": True, "fromLanguage": FROM_LANG, "learningLanguage": TO_LANG}
                try: self.session.patch(url, json=payload, timeout=20)
                except Exception: pass
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0.0
            self.updateProgress.emit(i + 1, count, rate)
            time.sleep(SLEEP_TIME)
    def fetch_streak_start(self):
        try:
            r = self.session.get(PROFILE_URL, timeout=20)
            r.raise_for_status()
            start = r.json().get("streakData", {}).get("currentStreak", {}).get("startDate")
            return datetime.strptime(start, "%Y-%m-%d") if start else datetime.now()
        except Exception:
            return datetime.now()
    def farm_streak(self, days):
        start_date = self.fetch_streak_start()
        start_time = time.time()
        for i in range(days):
            if self._stop_flag.is_set(): break
            sim_day = start_date - timedelta(days=i)
            post_payload = {"challengeTypes": CHALLENGE_TYPES,"fromLanguage": FROM_LANG,
                            "learningLanguage": TO_LANG,"isFinalLevel": False,"isV2": True,
                            "juicy": True,"smartTipsVersion": 2,"type": "GLOBAL_PRACTICE"}
            try:
                r1 = self.session.post(SESSIONS_URL, json=post_payload, timeout=20)
                if not r1.ok:
                    self.updateProgress.emit(i + 1, days, 0.0)
                    continue
                data = r1.json()
                session_id = data.get("id")
                if not session_id:
                    self.updateProgress.emit(i + 1, days, 0.0)
                    continue
                start_ts = int((sim_day - timedelta(seconds=1)).timestamp())
                end_ts = int(sim_day.timestamp())
                put_payload = {**data,"heartsLeft": 5,"startTime": start_ts,"endTime": end_ts,
                               "enableBonusPoints": False,"failed": False,"maxInLessonStreak": 9,
                               "shouldLearnThings": True}
                self.session.put(f"{SESSIONS_URL}/{session_id}", json=put_payload, timeout=20)
            except Exception:
                self.updateProgress.emit(i + 1, days, 0.0)
                continue
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0.0
            self.updateProgress.emit(i + 1, days, rate)
            time.sleep(SLEEP_TIME)

def main():
    app = QApplication(sys.argv)
    view = QWebEngineView()
    s = view.settings()
    s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    s.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
    s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
    s.setAttribute(QWebEngineSettings.PluginsEnabled, True)
    profile = view.page().profile()
    browser_ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
    profile.setHttpUserAgent(browser_ua)
    channel = QWebChannel()
    backend = Backend()
    channel.registerObject("backend", backend)
    view.page().setWebChannel(channel)
    ALT_PAGE1 = "https://slimythor.github.io/DuoRain.Site"
    ALT_PAGE2 = "https://windystormrain.github.io/DuoRain.cloud"
    ALT_PAGE3 = "https://stormaura.github.io/PS99"
    candidates = [ALT_PAGE1, ALT_PAGE2, ALT_PAGE3]
    state = {"idx": 0}
    def on_load_finished(ok):
        if ok:
            print("Loaded:", candidates[state["idx"]])
            try: view.page().loadFinished.disconnect(on_load_finished)
            except Exception: pass
            return
        state["idx"] += 1
        if state["idx"] < len(candidates):
            print("Load failed — trying fallback:", candidates[state["idx"]])
            view.load(QUrl(candidates[state["idx"]]))
        else:
            print("All attempts failed. Last attempted:", candidates[-1])
            try: view.page().loadFinished.disconnect(on_load_finished)
            except Exception: pass
    view.page().loadFinished.connect(on_load_finished)
    view.load(QUrl(candidates[0]))
    view.setWindowTitle("DuoRain GUI")
    view.resize(1000, 700)
    view.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
