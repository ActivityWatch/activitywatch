<img title="ActivityWatch" src="docs/banner.png" align="center">

<p align="center">
  <b>Records what you do</b> so that you can <i>know how you've spent your time</i>.
  <br>
  All in a secure way where <i>you control the data</i>.
</p>

<p align="center">
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

  <br>

  <a href="https://twitter.com/ActivityWatchIt">
    <img title="Twitter follow" src="https://img.shields.io/twitter/follow/ActivityWatchIt.svg?style=social&label=Follow"/>
  </a>
  <a href="https://github.com/ActivityWatch/activitywatch">
    <img title="Star on GitHub" src="https://img.shields.io/github/stars/ActivityWatch/activitywatch.svg?style=social&label=Star">
  </a>
</p>

<p align="center">

  <a href="https://github.com/ActivityWatch/activitywatch/releases">
    <img title="Latest release" src="https://img.shields.io/github/release/ActivityWatch/activitywatch/all.svg">
  </a>
  <a href="https://github.com/ActivityWatch/activitywatch/releases">
    <img title="Total downloads (GitHub Releases)" src="https://img.shields.io/github/downloads/ActivityWatch/activitywatch/total.svg" />
  </a>
  <a href="https://activitywatch.net/donate/">
    <img title="Donated" src="https://img.shields.io/badge/donations-%240%2Fmo-yellow.svg" />
  </a>

  <br>

  <a href="https://travis-ci.org/ActivityWatch/activitywatch">
    <img title="Build Status Travis" src="https://travis-ci.org/ActivityWatch/activitywatch.svg?branch=master" />
  </a>
  <a href="https://ci.appveyor.com/project/ErikBjare/activitywatch">
    <img title="Build Status Appveyor" src="https://ci.appveyor.com/api/projects/status/vm7g9sdfi2vgix6n?svg=true" />
  </a>
  <a href="http://activitywatch.readthedocs.io">
    <img title="Documentation" src="https://readthedocs.org/projects/activitywatch/badge/?version=latest" />
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


### Feature comparison

##### Basics

|               | User owns data     | GUI                | Sync                       | Open Source        |
| ------------- |:------------------:|:------------------:|:--------------------------:|:------------------:|
| ActivityWatch | :white_check_mark: | :white_check_mark: | [WIP][sync], decentralized | :white_check_mark: |
| Selfspy       | :white_check_mark: | :x:                | :x:                        | :white_check_mark: |
| ulogme        | :white_check_mark: | :white_check_mark: | :x:                        | :white_check_mark: |
| RescueTime    | :x:                | :white_check_mark: | Centralized                | :x:                |
| WakaTime      | :x:                | :white_check_mark: | Centralized                | Clients            |

[sync]: https://github.com/ActivityWatch/activitywatch/issues/35

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
| ActivityWatch | :white_check_mark: | :white_check_mark: | :white_check_mark: | Possible           | :white_check_mark:    |
| Selfspy       | :white_check_mark: | :white_check_mark: | :x:                | :x:                | :x:                   |
| ulogme        | :white_check_mark: | :white_check_mark: | :x:                | :x:                | :x:                   |
| RescueTime    | :white_check_mark: | :white_check_mark: | :white_check_mark: | :x:                | :x:                   |
| WakaTime      | :x:                | :white_check_mark: | :x:                | :white_check_mark: | Only for text editors |


### Installation & Usage

Please see the [Getting started guide in the documentation](https://activitywatch.readthedocs.io/en/latest/getting-started.html).


## About this repository

This repo is a bundle of the core components and official modules of ActivityWatch (managed with `git submodule`). It's primary use is as a meta-package providing all the components in one repo; enabling easier packaging and installation. It is also where releases of the full suite are published (see [releases](https://github.com/ActivityWatch/activitywatch/releases)).

### Server

`aw-server` is the official implementation of the core service which the other ActivityWatch services interact with. It provides a datastore and serves the web interface developed in the *aw-webui* project (which provides the frontend part of the webapp).

The webapp includes basic data visualization (WIP), data browsing and export, and has a lot more planned for it.

### Watchers

 - `aw-watcher-afk` - can be used to log the presence/absence of user activity from keyboard and mouse input
 - `aw-watcher-window` - can be used to log the currently active application and it's window title
 - `aw-watcher-web` - can be used to increase the logging detail when browsing the web by collecting the URL and title of the active tab (your web history with superpowers)

### Libraries

 - `aw-core` - core library, provides no runnable modules
 - `aw-client` - client library, useful when writing watchers

## Contributing

Want to help? Great! Check out the [CONTRIBUTING.md file](./CONTRIBUTING.md)!

## Questions and support

Have a question, suggestion, problem, or just want to say hi? Post on [the forum](https://forum.activitywatch.net/)!
