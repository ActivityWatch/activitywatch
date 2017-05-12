# Based on https://hvelarde.blogspot.se/2014/01/how-to-get-statistics-about-your.html
# Requires github3.py, get it with "pip install github3.py"

import operator
from getpass import getpass
from pprint import pprint

from github3 import login

two_factor_code = ''


def prompt_two_factor():
    global two_factor_code
    while not two_factor_code:
        # The user could accidentally press Enter before being ready,
        # let's protect them from doing that.
        two_factor_code = input('Enter 2FA code: ')
    return two_factor_code


def main():
    username = input("Username: ")
    password = getpass("Password for {}: ".format(username))
    cs = Contribstats(username, password)
    cs.gather()
    cs.print()


def sum_weeks(weeks: list):
    sum_week = {"additions": 0, "deletions": 0, "commits": 0}
    for week in weeks:
        sum_week["additions"] += week["additions"]
        sum_week["deletions"] += week["deletions"]
        sum_week["commits"] += week["commits"]
    return sum_week


class Contribstats:
    def __init__(self, username, password):
        self.username = username
        self.g = login(username, password=password, two_factor_callback=prompt_two_factor)
        self.o = self.g.organization('ActivityWatch')
        self.print_ratelimit()

    def print_ratelimit(self):
        print("Remaining ratelimit:", self.g.ratelimit_remaining)

    def gather(self):
        self.repos = {}
        for r in self.o.iter_repos():
            if r.fork:
                print("Skipping {}, was a fork".format(r.name))
                continue

            print("Collecting from {}".format(r.name))
            self.repos[r.name] = {}
            for c in r.iter_contributor_statistics():
                self.repos[r.name][c.author.login] = sum_weeks(c.alt_weeks)

        self.print_ratelimit()

    def print(self):
        pprint(self.repos)


if __name__ == "__main__":
    main()
