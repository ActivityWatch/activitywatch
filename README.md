<img title="ActivityWatch" src="docs/banner.png" align="center">

<p align="center">
  <b>
    <a href="https://github.com/ActivityWatch/activitywatch/releases">Releases</a>
    | <a href="http://activitywatch.readthedocs.io">Documentation</a>
    | <a href="http://activitywatch.net/">Website</a>
    | <a href="https://github.com/ActivityWatch/activitywatch/">GitHub</a>
    | <a href="https://twitter.com/ActivityWatchIt">Twitter</a>
  </b>

  <br>

  <a href="https://travis-ci.org/ActivityWatch/activitywatch">
    <img title="Build Status Travis" src="https://travis-ci.org/ActivityWatch/activitywatch.svg?branch=master" />
  </a>
  <a href="https://ci.appveyor.com/project/ErikBjare/activitywatch">
    <img title="Build Status Appveyor" src="https://ci.appveyor.com/api/projects/status/vm7g9sdfi2vgix6n?svg=true" />
  </a>
  <a href="https://github.com/ActivityWatch/activitywatch/releases">
    <img title="Total downloads (GitHub Releases)" src="https://img.shields.io/github/downloads/ActivityWatch/activitywatch/total.svg" />
  </a>
  <a href="http://activitywatch.readthedocs.io">
    <img title="Documentation" src="https://readthedocs.org/projects/activitywatch/badge/?version=latest" />
  </a>
</p>

<!--
# TODO: Best practices badge that we should work towards, see issue #42.
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/873/badge)](https://bestpractices.coreinfrastructure.org/projects/873)
-->

<p align="center">
  <b>Records what you do</b> so that you can <i>understand how you spend your time</i>. 
  <br>
  All in a secure way where <i>you control the data</i>.
</p>


## About

The goal of ActivityWatch is simple: *Enable the collection of as much valuable lifedata as possible without compromising user privacy.*

We've worked towards this goal by creating a application for safe storage of the data on the users local machine and as well as a set of watchers which record data such as:

 - Currently active application and the title of its window
 - Currently active browser tab and it's title and URL
 - Keyboard and mouse activity, to detect if you are afk or not
</small>
 
It is up to you as user to collect as much as you want, or as little as you want (and we hope some of you will help write watchers so we can collect more).

**Note:** ActivityWatch is under development. There is still work to be done so we provide it with no guarantees with the hope that others may wish to help and give their feedback!

You can read more on our [website](https://activitywatch.github.io/about/).

### Screenshots

<!-- TODO: We could probably stylize these (nice borders, scaled down) -->

<img src="http://activitywatch.net/screenshot.png" width="22%">
<!--
  <img src="http://activitywatch.net/screenshot.png" width="22%">
  <img src="http://activitywatch.net/screenshot.png" width="22%">
  <img src="http://activitywatch.net/screenshot.png" width="22%">
-->

### Is this yet another time tracker?

Yes, but we found that most time trackers lack in one or more important features. 

**Common dealbreakers:**

 - Not open source
 - The user does not own the data (common with non-open source options)
 - Lack of synchronization (and when available: it's centralized and the sync server knows everything)
 - Difficult to setup/use (most open source options tend to target programmers)
 - Low data resolution (low level of detail, does not store raw data, long intevals between entries)
 - Hard or impossible to extend (collecting more data is not as simple as it could be)

**To sum it up:**

 - Closed source solutions suffer from privacy issues and limited features.
 - Open source solutions aren't developed with end-users in mind and are usually not written to be easily extended (they lack a proper API). They also lack synchronization.

We have a plan to address all of these and we're well on our way. See the table below for our progress.

#### Feature comparison


<!-- TODO: Replace Platform names with icons  -->

|               | User owns data     | GUI                | Sync                     | Open Source        | Platforms                                 |
| ------------- |:------------------:|:------------------:|:------------------------:|:------------------:| ----------------------------------------- |
| ActivityWatch | :white_check_mark: | :white_check_mark: | ~~Decentralized~~ (WIP)  | :white_check_mark: | macOS, Linux, Windows, ~~Android~~ (WIP)  |
| Selfspy       | :white_check_mark: | :x:                | :x:                      | :white_check_mark: | macOS, Linux, Windows                     |
| ulogme        | :white_check_mark: | :white_check_mark: | :x:                      | :white_check_mark: | macOS, Linux                              |
| RescueTime    | :x:                | :white_check_mark: | Centralized              | :x:                | macOS, Linux, Windows, Android, iOS       |
| WakaTime      | :x:                | :white_check_mark: | Centralized              | Client             | Most popular text editors                 |

**Tracking**

|               | Application        | Window Title       | AFK                | Browser Extensions | Editor Plugins           |
| ------------- |:------------------:|:------------------:|:------------------:|:------------------:|:------------------------:|
| ActivityWatch | :white_check_mark: | :white_check_mark: | :white_check_mark: | In Beta            | Possible                 |
| Selfspy       | :white_check_mark: | :white_check_mark: | :white_check_mark:?| :x:                | :white_check_mark:?      |
| ulogme        | :white_check_mark: | :white_check_mark: | :white_check_mark:?| :x:                | :x:?                     |
| RescueTime    | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x:                      |
| WakaTime      | :x:                | :x:                | :white_check_mark: | :x:                | :white_check_mark:, many |


### Installation & Usage

**We're not there yet for end-users**, however if you are a developer you may try the following:

```sh
# Ensure you have Python 3.5 or later installed
python3 -V

# Now you probably want to set up a virtualenv so we don't install everything system-wide.
sudo pip3 install virtualenv  # Assuming you don't already have it, you might want to use your systems package manager instead.
python3 -m venv venv
# Now you need to activate the virtualenv
# For bash/zsh users: source ./venv/bin/activate
# For fish users:     source ./venv/bin/activate.fish

# Now we build and install everything into the virtualenv.
make build

# Now you should be able to start ActivityWatch
# Either use the trayicon manager:
aw-qt
# Or run each module seperately:
aw-server
aw-watcher-afk
aw-watcher-window

# Now everything should be running!
# You can see your data at http://localhost:5600/
```

If anything doesn't work, let us know!

## About this repository

This repo is a bundle of the core components and official modules of ActivityWatch (managed with `git submodule`). It's primary use is as a meta-package providing all the components in one repo; enabling easier packaging and installation. It is also where releases of the full suite are published (see [releases](https://github.com/ActivityWatch/activitywatch/releases)).

### Server

`aw-server` is the official implementation of the core service which the other activitywatch services interact with. It provides a datastore and serves the web interface developed in the *aw-webui* project (which provides the frontend part of the webapp).

The webapp includes basic data visualization (WIP), data browsing and export, and has a lot more planned for it.

### Watchers

 - `aw-watcher-afk` - can be used to log the presence/absence of user activity from keyboard and mouse input
 - `aw-watcher-window` - can be used to log the currently active application and it's window title
 - `aw-watcher-web` - (WIP) can be used to increase the logging detail when browsing the web by collecting the URLs and titles of tabs (your web history with superpowers)

### Libraries

 - `aw-core` - core library, provides no runnable modules
 - `aw-client` - client library, useful when writing watchers

## Contributing

We currently don't have much of a good contributors guide (we're working on it), feel free to browse the documentation (also in a early state). You should also send me an email at: [erik@bjareho.lt](mailto:erik@bjareho.lt).
