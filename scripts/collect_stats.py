import re

import requests


def downloads():
    r = requests.get("https://api.github.com/repos/ActivityWatch/activitywatch/releases")
    d = r.json()

    downloads = 0
    for release in d:
        print("Release: ", release["tag_name"])
        for asset in release["assets"]:
            platform = re.findall("(macos|darwin|linux|windows)", asset["name"])[0]
            count = asset["download_count"]
            print(" - {}: {}".format(platform, count))

            downloads += asset["download_count"]

    print("Total: ", downloads)


def stars():
    r = requests.get("https://api.github.com/repos/ActivityWatch/activitywatch")
    d = r.json()

    print("Stars: ", d["stargazers_count"])

stars()
downloads()
