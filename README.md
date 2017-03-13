ActivityWatch
=============


[![Build Status](https://travis-ci.org/ActivityWatch/activitywatch.svg?branch=master)](https://travis-ci.org/ActivityWatch/activitywatch)
[![Documentation](https://readthedocs.org/projects/activitywatch/badge/?version=latest)](http://activitywatch.readthedocs.io)

[Releases](https://github.com/ActivityWatch/activitywatch/releases)
| [Documentation](http://activitywatch.readthedocs.io)
| [Issue tracker](https://github.com/ActivityWatch/activitywatch-user-issues/issues)
| [Website](http://activitywatch.net/)
| [GitHub](https://github.com/ActivityWatch/activitywatch/)
| [Twitter](https://twitter.com/ActivityWatchIt)

ActivityWatch ***records what you do*** so that you can ***become aware of what you do*** and choose to do better. All in a secure way where ***you control the data***.


# About

The goal of ActivityWatch is simple: *Enable the collection of as much valuable lifedata as possible without compromising user privacy.*

We've worked towards this goal by creating a application for safe storage of the data on the users local machine and created a set of watchers which watch for data to record such as keyboard and mouse activity, window titles, open tab URLs. It is up to you as user to collect as much as you want, or as little as you want.

**Note:** ActivityWatch is under development. There is still work to be done so we provide it with no guarantees with the hope that others may wish to help and give their feedback!

You can read more on our [website](https://activitywatch.github.io/about/).

## Screenshots

<img src="http://activitywatch.net/screenshot.png" width="22%">
<!--
  <img src="http://activitywatch.net/screenshot.png" width="22%">
  <img src="http://activitywatch.net/screenshot.png" width="22%">
  <img src="http://activitywatch.net/screenshot.png" width="22%">
-->

# About this repository

This repo is a bundle of the core components and official modules of ActivityWatch (managed with `git submodule`). It's primary use is as a meta-package providing all the components in one repo; enabling easier packaging and installation. It is also where releases of the full suite are published (see [releases](https://github.com/ActivityWatch/activitywatch/releases)).

## Server

`aw-server` is the official implementation of the core service which the other activitywatch services interact with. It provides a datastore and serves the web interface developed in the *aw-webui* project (which provides the frontend part of the webapp).

The webapp includes basic data visualization (WIP), data browsing and export, and has a lot more planned for it.

## Watchers

 - `aw-watcher-afk` - can be used to log the presence/absence of user activity from keyboard and mouse input
 - `aw-watcher-window` - can be used to log the currently active application and it's window title
 - `aw-watcher-web` - (WIP) can be used to increase the logging detail when browsing the web by collecting the URLs and titles of tabs (your web history with superpowers)

## Libraries

 - `aw-core` - core library, provides no runnable modules
 - `aw-client` - client library, useful when writing watchers

# Contributing

We currently don't have much of a good contributors guide (we're working on it), feel free to browse the documentation (also in a early state). You should also send me an email at: [erik@bjareho.lt](mailto:erik@bjareho.lt).
