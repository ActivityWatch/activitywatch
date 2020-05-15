<img title="ActivityWatch" src="https://activitywatch.net/img/banner.png" align="center">

<p align="center">
  <b>Records what you do</b> so that you can <i>know how you've spent your time</i>.
  <br>
  All in a secure way where <i>you control the data</i>.
</p>

<p align="center">

  <a href="https://twitter.com/ActivityWatchIt">
    <img title="Twitter follow" src="https://img.shields.io/twitter/follow/ActivityWatchIt.svg?style=social&label=Follow"/>
  </a>
  <a href="https://github.com/ActivityWatch/activitywatch">
    <img title="Star on GitHub" src="https://img.shields.io/github/stars/ActivityWatch/activitywatch.svg?style=social&label=Star">
  </a>

  <br>

  <b>
    <a href="https://activitywatch.net/">Website</a>
    — <a href="https://forum.activitywatch.net/">Forum</a>
    — <a href="https://activitywatch.readthedocs.io">Documentation</a>
    — <a href="https://github.com/ActivityWatch/activitywatch/releases">Releases</a>
  </b>

  <br>

  <b>
    <a href="https://activitywatch.net/contributors/">Contributor stats</a>
    — <a href="https://activitywatch.net/ci/">CI overview</a>
  </b>
</p>

<p align="center">
  <a href="https://activitywatch.net/donate/">
    <img title="Donated" src="https://img.shields.io/badge/current%20budget-%2437%2Fmo%20from%2015%20supporters-red.svg" />
  </a>

  <br>

  <a href="https://github.com/ActivityWatch/activitywatch/actions?query=branch%3Amaster">
    <img title="Build Status GitHub" src="https://github.com/ActivityWatch/activitywatch/workflows/Build/badge.svg?branch=master" />
  </a>
  <a href="https://travis-ci.org/ActivityWatch/activitywatch">
    <img title="Build Status Travis" src="https://travis-ci.org/ActivityWatch/activitywatch.svg?branch=master" />
  </a>
  <a href="https://ci.appveyor.com/project/ErikBjare/activitywatch">
    <img title="Build Status Appveyor" src="https://ci.appveyor.com/api/projects/status/vm7g9sdfi2vgix6n?svg=true" />
  </a>
  <a href="http://activitywatch.readthedocs.io">
    <img title="Documentation" src="https://readthedocs.org/projects/activitywatch/badge/?version=latest" />
  </a>

  <br>

  <a href="https://github.com/ActivityWatch/activitywatch/releases">
    <img title="Latest release" src="https://img.shields.io/github/release-pre/ActivityWatch/activitywatch.svg">
  </a>
  <a href="https://github.com/ActivityWatch/activitywatch/releases">
    <img title="Total downloads (GitHub Releases)" src="https://img.shields.io/github/downloads/ActivityWatch/activitywatch/total.svg" />
  </a>
</p>

<!--
# TODO: Best practices badge that we should work towards, see issue #42.
[![CII Best Practices](https://bestpractices.coreinfrastructure.org/projects/873/badge)](https://bestpractices.coreinfrastructure.org/projects/873)
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bhttps%3A%2F%2Fgithub.com%2FActivityWatch%2Factivitywatch.svg?type=shield)](https://app.fossa.io/projects/git%2Bhttps%3A%2F%2Fgithub.com%2FActivityWatch%2Factivitywatch?ref=badge_shield)
-->


*Do you want to receive email updates on major announcements?*<br>
***[Signup for the newsletter](http://eepurl.com/cTU6QX)!***

<details>
 <summary>Table of Contents</summary>

 * [About](#about)
    * [Screenshots](#screenshots)
    * [Is this yet another time tracker?](#is-this-yet-another-time-tracker)
       * [Feature comparison](#feature-comparison)
    * [Installation &amp; Usage](#installation--usage)
 * [About this repository](#about-this-repository)
    * [Server](#server)
    * [Watchers](#watchers)
    * [Libraries](#libraries)
 * [Contributing](#contributing)
</details>

## About

The goal of ActivityWatch is simple: *Enable the collection of as much valuable lifedata as possible without compromising user privacy.*

We've worked towards this goal by creating a application for safe storage of the data on the users local machine and as well as a set of watchers which record data such as:

 - Currently active application and the title of its window
 - Currently active browser tab and it's title and URL
 - Keyboard and mouse activity, to detect if you are AFK ("away from keyboard") or not
</small>

It is up to you as user to collect as much as you want, or as little as you want (and we hope some of you will help write watchers so we can collect more).

### Screenshots

<span><img src="https://activitywatch.net/screenshot-v0.8.0b9-today.png"    width="35%"></span>
<span><img src="https://activitywatch.net/screenshot-v0.8.0b9-timeline.png" width="43%"></span>


## Installation & Usage

Downloads are available on our [releases page](https://github.com/ActivityWatch/activitywatch/releases).

For instructions on how to get started, please see [our guide in the documentation](https://activitywatch.readthedocs.io/en/latest/getting-started.html).

Interested in building from source? [There's a guide for that too](https://activitywatch.readthedocs.io/en/latest/installing-from-source.html).

## Is this yet another time tracker?

Yes, but we found that most time trackers lack in one or more important features.

**Common dealbreakers:**

 - Not open source
 - The user does not own the data (common with non-open source options)
 - Lack of synchronization (and when available: it's centralized and the sync server knows everything)
 - Difficult to setup/use (most open source options tend to target programmers)
 - Low data resolution (low level of detail, does not store raw data, long intervals between entries)
 - Hard or impossible to extend (collecting more data is not as simple as it could be)

**To sum it up:**

 - Closed source solutions suffer from privacy issues and limited features.
 - Open source solutions aren't developed with end-users in mind and are usually not written to be easily extended (they lack a proper API). They also lack synchronization.

We have a plan to address all of these and we're well on our way. See the table below for our progress.


### Feature comparison

##### Basics

|               | User owns data     | GUI                | Sync                       | Open Source        |
| ------------- |:------------------:|:------------------:|:--------------------------:|:------------------:|
| ActivityWatch | :white_check_mark: | :white_check_mark: | [WIP][sync], decentralized | :white_check_mark: |
| [Selfspy]       | :white_check_mark: | :x:                | :x:                        | :white_check_mark: |
| [ulogme]        | :white_check_mark: | :white_check_mark: | :x:                        | :white_check_mark: |
| [RescueTime]    | :x:                | :white_check_mark: | Centralized                | :x:                |
| [WakaTime]      | :x:                | :white_check_mark: | Centralized                | Clients            |

[sync]: https://github.com/ActivityWatch/activitywatch/issues/35
[Selfspy]: https://github.com/selfspy/selfspy
[ulogme]: https://github.com/karpathy/ulogme
[RescueTime]: https://www.rescuetime.com/
[WakaTime]: https://wakatime.com/

##### Platforms
<!-- TODO: Replace Platform names with icons  -->

|               | Windows            | macOS              | Linux              | Android            |
| ------------- |:------------------:|:------------------:|:------------------:|:------------------:|
| ActivityWatch | :white_check_mark: | :white_check_mark: | :white_check_mark: | [WIP][android]     |
| Selfspy       | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x:                | 
| ulogme        | :x:                | :white_check_mark: | :white_check_mark: | :x:                |
| RescueTime    | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | 

[android]: https://github.com/ActivityWatch/activitywatch/issues/6

##### Tracking

|               | App & Window Title | AFK                | Browser Extensions | Editor Plugins     | Extensible            |
| ------------- |:------------------:|:------------------:|:------------------:|:------------------:|:---------------------:|
| ActivityWatch | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark: | :white_check_mark:    |
| Selfspy       | :white_check_mark: | :white_check_mark: | :x:                | :x:                | :x:                   |
| ulogme        | :white_check_mark: | :white_check_mark: | :x:                | :x:                | :x:                   |
| RescueTime    | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x:                | :x:                   |
| WakaTime      | :x:                | :white_check_mark: | :white_check_mark: | :white_check_mark: | Only for text editors |

For a complete list of the things ActivityWatch can track, [see the page on *watchers* in the documentation](https://activitywatch.readthedocs.io/en/latest/watchers.html).


## About this repository

This repo is a bundle of the core components and official modules of ActivityWatch (managed with `git submodule`). It's primary use is as a meta-package providing all the components in one repo; enabling easier packaging and installation. It is also where releases of the full suite are published (see [releases](https://github.com/ActivityWatch/activitywatch/releases)).

### Server

`aw-server` is the official implementation of the core service which the other ActivityWatch services interact with. It provides a REST API to a datastore and query engine. It also serves the web interface developed in the `aw-webui` project (which provides the frontend part of the webapp).

The REST API includes:

 - Access to a datastore suitable for timeseries/timeperiod-data
 - A query engine and language for such data

The webapp includes:

 - Data visualization & browser
 - Query explorer
 - Export functionality 

### Watchers

ActivityWatch comes pre-installed with two watchers, `aw-watcher-afk` which logs the presence/absence of user activity from keyboard and mouse input and `aw-watcher-window` which logs the currently active application and it's window title.

There are lots of other watchers for ActivityWatch which can track more types of activity such as `aw-watcher-web` which tracks time spent on websites, multiple editor watchers which tracks spent time coding and many more! [A full list of watchers can be found in our documentation here](https://activitywatch.readthedocs.io/en/latest/watchers.html).

### Libraries

 - `aw-core` - core library, provides no runnable modules
 - `aw-client` - client library, useful when writing watchers

## Contributing

Want to help? Great! Check out the [CONTRIBUTING.md file](./CONTRIBUTING.md)!

## Questions and support

Have a question, suggestion, problem, or just want to say hi? Post on [the forum](https://forum.activitywatch.net/)!

