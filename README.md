ActivityWatch
=============


[![Build Status](https://travis-ci.org/ActivityWatch/activitywatch.svg?branch=master)](https://travis-ci.org/ActivityWatch/activitywatch)
[![Documentation](https://readthedocs.org/projects/activitywatch/badge/?version=latest)](http://activitywatch.readthedocs.io)

## About ActivityWatch

ActivityWatch is about recording what you do, so you can become aware of what you do, and choose to do better. All in a way where you control the data.

**Note:** ActivityWatch is under development. There is still work to be done so we provide it with no guarantees with the hope that others may wish to help and give their feedback!

You can read more on our [website](https://activitywatch.github.io/about/).

#### Server
The *aw-server* project is the official implementation of the core service which the other activitywatch services interact with. It provides a datastore and serves the web interface developed in the *aw-webapp* project (which provides the frontend part of the webapp).

The webapp includes basic data visualization (WIP), data browsing and export, and has a lot planned for it.

***TODO:*** Add screenshots of the webapp.

#### Watchers

 - *aw-watcher-afk* - can be used to log the presence/absence of user activity from keyboard and mouse input
 - *aw-watcher-window* - can be used to log the currently active application and it's window title
 - *aw-core* - core library, provides no runnable modules


## About this repository

This repo is a bundle of the core components and official modules of ActivityWatch. it Is also where releases of the full suite are published (see [releases](https://github.com/ActivityWatch/activitywatch/releases)).

It's primary use is as a meta-package providing all the components in one repo; enabling easier packaging and installation.

This is also the repo where issues about ActivityWatch *in general* should go, such as requests and discussion regarding new features.

