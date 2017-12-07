import re
from pprint import pprint
import sys
from datetime import datetime, timezone

import requests


def downloads(verbose=False):
    r = requests.get("https://api.github.com/repos/ActivityWatch/activitywatch/releases")
    d = r.json()

    downloads = 0
    for release in d:
        if verbose:
            print("Release: ", release["tag_name"])
        for asset in release["assets"]:
            platform = re.findall("(macos|darwin|linux|windows)", asset["name"])[0]
            count = asset["download_count"]
            if verbose:
                print(" - {}: {}".format(platform, count))

            downloads += asset["download_count"]
    return downloads


def stars():
    r = requests.get("https://api.github.com/repos/ActivityWatch/activitywatch")
    d = r.json()
    return d["stargazers_count"]


def clones():
    # TODO: Needs push access to the repository
    r = requests.get("https://api.github.com/repos/ActivityWatch/activitywatch/traffic/clones?per=day")
    d = r.json()
    pprint(d)


def twitter():
    # TODO: Needs API key
    r = requests.get("https://api.twitter.com/1.1/users/show.json?screen_name=ActivityWatchIt")
    d = r.json()
    pprint(d)
    followers = d["followers_count"]
    print("Followers: ", followers)


if __name__ == "__main__":
    s = stars()
    d = downloads()

    if "--csv" in sys.argv:
        print("{},{},{}".format(datetime.now(tz=timezone.utc).isoformat(), d, s))
    else:
        print("Downloads: ", d)
        print("Stars:     ", s)