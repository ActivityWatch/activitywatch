[![en](https://img.shields.io/badge/lang-en-red.svg)](/CONTRIBUTING.md) | [![zh](https://img.shields.io/badge/lang-zh--CN-yellow.svg)](/CONTRIBUTING.zh.md)

如何贡献
============

<!-- 本指南可根据 https://mozillascience.github.io/working-open-workshop/contributing/ 的建议进行改进 -->

**目录**

- [开始](#开始)
- [你可以如何帮助](#你可以如何帮助)
- [提交 Issue](#提交-issue)
- [行为准则](#行为准则)
- [提交消息规范](#提交消息规范)
- [获得报酬](#获得报酬)
- [领取 GitPOAP](#领取-gitpoap)
- [问题？](#问题)

## 开始

要开发 ActivityWatch，你首先需要从源代码安装。请按照[文档中的指南](https://activitywatch.readthedocs.io/en/latest/installing-from-source.html)进行操作。

你可能还想了解[架构](https://activitywatch.readthedocs.io/en/latest/architecture.html)和[数据模型](https://activitywatch.readthedocs.io/en/latest/buckets-and-events.html)。

如果你想要一些如何编写监控器或其他类型客户端的代码示例，请参阅[编写监控器的文档](https://docs.activitywatch.net/en/latest/examples/writing-watchers.html)。

## 你可以如何帮助

有很多方式可以为 ActivityWatch 做出贡献：

- 处理标记为 [`good first issue`][good first issue] 或 [`help wanted`][help wanted] 的问题，这些特别适合新贡献者
- 修复 [`bug`][bugs]
- 实现新功能
  - 在论坛上查看[请求的功能][requested features]
  - 在 issue 中或通过[我们的 Discord 服务器][discord]与我们交流，获取如何进行的帮助
- 编写[文档](https://github.com/ActivityWatch/docs)
- 构建生态系统
  - 例如：新的监控器、数据分析工具、从其他源导入数据的工具等

如果你对我们下一步的计划感兴趣，请查看我们的[路线图][roadmap]和[里程碑][milestones]。

以上大部分工作都能让你登上我们的[贡献者统计页面][contributors]作为感谢！

[good first issue]: https://github.com/ActivityWatch/activitywatch/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22
[help wanted]: https://github.com/ActivityWatch/activitywatch/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22
[bugs]: https://github.com/ActivityWatch/activitywatch/issues?q=is%3Aissue+is%3Aopen+label%3A%22type%3A+bug%22
[milestones]: https://github.com/ActivityWatch/activitywatch/milestones
[roadmap]: https://github.com/orgs/ActivityWatch/projects/2
[requested features]: https://forum.activitywatch.net/c/features
[contributors]: http://activitywatch.net/contributors/

## 提交 Issue

感谢你希望通过提交 Issue 来帮助我们修复 bug 等。

提交 Issue 时，请务必使用[Issue 模板](https://github.com/ActivityWatch/activitywatch/issues/new/choose)。这确保我们拥有理解问题所需的信息，避免需要大量的后续问题，从而更快地解决问题！

## 行为准则

我们有一个行为准则，希望所有贡献者遵守，你可以在 [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) 中找到。

## 提交消息规范

编写提交消息时，请尽量遵循[约定式提交](https://www.conventionalcommits.org/)。这不是硬性要求（为了降低新贡献者的负担），但鼓励遵守。

格式如下：

```
<类型>[可选范围]: <描述>

[可选正文]

[可选页脚]
```

其中 `类型` 可以是以下之一：`feat, fix, chore, ci, docs, style, refactor, perf, test`

示例：

```
- feat: added ability to sort by duration
- fix: fixes incorrect week number (#407)
- docs: improved query documentation
```

此规范在 [issue #391](https://github.com/ActivityWatch/activitywatch/issues/391) 中采纳。

## 获得报酬

我们正在尝试通过捐赠和资助获得的资金向贡献者支付报酬。

基本思路是：你用 ActivityWatch 记录你的工作（并确保正确分类），然后修改 [working_hours.py](https://github.com/ActivityWatch/aw-client/blob/master/examples/working_hours.py) 脚本以使用你的分类规则，生成每日工作时间报告及匹配的事件。

如果你为 ActivityWatch 做出了贡献（至少 10 小时）并希望为你的时间获得报酬，请联系我们！

你可以在[论坛](https://forum.activitywatch.net/t/getting-paid-with-activitywatch/986)和[issues](https://github.com/ActivityWatch/activitywatch/issues/458)中了解更多关于这个实验的信息。

## 领取 GitPOAP

如果你为 ActivityWatch 贡献了提交，你就有资格在以太坊上领取 GitPOAP。你可以在这里了解更多信息：https://twitter.com/ActivityWatchIt/status/1584454595467612160

2022 年的 GitPOAP 如下：

<a href="https://www.gitpoap.io/gh/ActivityWatch/activitywatch">
  <img src="https://assets.poap.xyz/gitpoap-2022-activitywatch-contributor-2022-logo-1663695908409.png" width="256px">
</a>

## 问题？

如果你有任何问题，你可以：

- 在[我们的 Discord 服务器][discord]上与我们交流
- 在[论坛][forum]或 [GitHub Discussions][github discussions] 上发帖
- （作为最后手段/如果需要）发送邮件给维护者： [erik@bjareho.lt](mailto:erik@bjareho.lt)

[forum]: https://forum.activitywatch.net
[github discussions]: https://github.com/ActivityWatch/activitywatch/discussions
[discord]: https://discord.gg/vDskV9q
