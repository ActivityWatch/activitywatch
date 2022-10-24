How to Contribute
=================

<!-- This guide could be improved by following the advice at https://mozillascience.github.io/working-open-workshop/contributing/ -->

**Table of Contents**

 - [Getting started](#getting-started)
 - [How you can help](#how-you-can-help)
 - [Filing an issue](#filing-an-issue)
 - [Code of Conduct](#code-of-conduct)
 - [Commit message guidelines](#commit-message-guidelines)
 - [Getting paid](#getting-paid)
 - [Claiming GitPOAP](#claiming-gitpoap)
 - [Questions?](#questions)


## Getting started

To develop on ActivityWatch you'll first want to install from source. To do so, follow [the guide in the documentation](https://activitywatch.readthedocs.io/en/latest/installing-from-source.html).

You might then want to read about the [architecture](https://activitywatch.readthedocs.io/en/latest/architecture.html) and the [data model](https://activitywatch.readthedocs.io/en/latest/buckets-and-events.html).

If you want some code examples for how to write watchers or other types of clients, see the [documentation for writing watchers](https://docs.activitywatch.net/en/latest/examples/writing-watchers.html).


## How you can help

There are many ways to contribute to ActivityWatch:

 - Work on issues labeled [`good first issue`][good first issue] or [`help wanted`][help wanted], these are especially suited for new contributors.
 - Fix [`bugs`][bugs].
 - Implement new features.
   - Look among the [requested features][requested features] on the forum.
   - Talk to us in the issues or on [our Discord server][discord] to get help on how to proceed.
 - Write documentation.
 - Build the ecosystem.
   - Examples: New watchers, tools to analyze data, tools to import data from other sources, etc.

If you're interested in what's next for ActivityWatch, have a look at our [roadmap][roadmap] and [milestones][milestones].

Most of the above will get you up on our [contributor stats page][contributors] as thanks!

[good first issue]: https://github.com/ActivityWatch/activitywatch/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22
[help wanted]: https://github.com/ActivityWatch/activitywatch/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22
[bugs]: https://github.com/ActivityWatch/activitywatch/issues?q=is%3Aissue+is%3Aopen+label%3A%22type%3A+bug%22
[milestones]: https://github.com/ActivityWatch/activitywatch/milestones
[roadmap]: https://github.com/orgs/ActivityWatch/projects/2
[requested features]: https://forum.activitywatch.net/c/features
[contributors]: http://activitywatch.net/contributors/


## Filing an issue

Thanks for wanting to help out with squashing bugs and more by filing an issue.

When filing an issue, it's important to use an [issue template](https://github.com/ActivityWatch/activitywatch/issues/new/choose). This ensures that we have the information we need to understand the issue, so we don't have to ask for tons of follow-up questions, so we can fix the issue faster!


## Code of Conduct

We have a Code of Conduct that we expect all contributors to follow, you can find it in [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).


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


## Getting paid

We're experimenting with paying our contributors using funds we've raised from donations and grants. 

The idea is you track your work with ActivityWatch (and ensure it gets categorized correctly), then you modify the [working_hours.py](https://github.com/ActivityWatch/aw-client/blob/master/examples/working_hours.py) script to use your category rule and generate a report of time worked per day and the matching events.

If you've contributed to ActivityWatch (for a minimum of 10h) and want to get paid for your time, contact us!

You can read more about this experiment on [the forum](https://forum.activitywatch.net/t/getting-paid-with-activitywatch/986) and in [the issues](https://github.com/ActivityWatch/activitywatch/issues/458).


## Claiming GitPOAP

If you've contributed a commit to ActivityWatch, you are eligible to claim a GitPOAP on Ethereum. You can read about it here: https://twitter.com/ActivityWatchIt/status/1584454595467612160

The one for 2022 looks like this:

<a href="https://www.gitpoap.io/gh/ActivityWatch/activitywatch">
  <img src="https://assets.poap.xyz/gitpoap-2022-activitywatch-contributor-2022-logo-1663695908409.png" width="256px">
</a>


## Questions?

If you have any questions, you can:

 - Talk to us on our [Discord server][discord]
 - Post on [the forum][forum] or [GitHub Discussions][github discussions].
 - (as a last resort/if needed) Email one of the maintainers at: [erik@bjareho.lt](mailto:erik@bjareho.lt)

[forum]: https://forum.activitywatch.net
[github discussions]: https://github.com/ActivityWatch/activitywatch/discussions
[discord]: https://discord.gg/vDskV9q
