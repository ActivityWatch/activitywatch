How to Contribute
=================

**Did you come here to read what you should do before creating an issue?** Scroll down!

**Note:** This is a work in progress, there is a lot we could do better so file a PR if you think we've missed something!


## Getting started with development

To develop on ActivityWatch you'll first want to install from source. To do so, follow [the guide in the documentation](https://activitywatch.readthedocs.io/en/latest/installing-from-source.html).

You might then want to read about the [architecture](https://activitywatch.readthedocs.io/en/latest/architecture.html) and the [data model](https://activitywatch.readthedocs.io/en/latest/buckets-and-events.html).

If you want some code examples for how to write watchers or other types of clients, see the [documentation for writing watchers](https://activitywatch.readthedocs.io/en/latest/writing-watchers.html).


## How you can help

There are many ways to contribute to ActivityWatch:

 - Help with testing by being an early user and reporting bugs.
 - Help with one of the issues labeled [`help wanted`](https://github.com/ActivityWatch/activitywatch/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22), these are especially suited for new contributors.
 - Help write documentation.
 - Help build the ecosystem.
   - Examples: New watchers, tools to analyze data, tools to import data from other sources, etc.
 - Help fix bugs.
   - See the issues in this repo.
 - Help implement new features.
   - Want to start working on a new feature? Find the appropriate subrepo, if any, and see if there is anything that needs doing.

Most of the above will get you up on our [contributor stats page](http://activitywatch.net/contributors/) as thanks!


## Filing an issue

Thanks for wanting to help out with squashing bugs and more by filing an issue.

There are a few things you might consider when filing your issue:

 - Which version of ActivityWatch are you running? 
   - NOTE: There is currently no good way to find this out, sorry about that.
 - What made the issue/bug appear? (steps to reproduce)
 - Include a logfile
   - Log files can be found in different places, depending on platform:
     - macOS: `~/Library/Logs/activitywatch`
     - Linux: `~/.cache/activitywatch/log`
     - Windows: `C:\Users\<USERNAME>\AppData\Local\activitywatch\activitywatch\Logs`
     

## Commit message guidelines

When writing commit messages try to follow [Conventional Commits](https://www.conventionalcommits.org/). It is not a strict requirement (to minimize overhead for new contributors) but it is encouraged.

The format is: 

```
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

Where `type` can be one of: `feat, fix, chore, ci, docs, style, refactor, perf, test`

Examples:

```
 - feat: added ability to sort by duration
 - fix: fixes incorrect week number (#407)
 - docs: improved query documentation 
```

This guideline was adopted in [issue #391](https://github.com/ActivityWatch/activitywatch/issues/391).


## Questions?

If you have any questions, post on [the forum](https://forum.activitywatch.net/) or email one of the maintainers at: [erik@bjareho.lt](mailto:erik@bjareho.lt).
