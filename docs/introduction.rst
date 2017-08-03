Introduction
============

.. TODO This could need some more user-friendly language and less details about architecture.

ActivityWatch is a bundle of software that tracks your computer activity.
You are, by default, the sole owner of your data.

It also offers an ecosystem of software to work around it, including ways to collect more data and do different kinds of analysis,

What ActivityWatch is
---------------------

 - A set of watchers that record relevant information about what you do and what happens on your computer (such as if you are AFK or not, or which window is currently active).
 - A way of storing data collected by the watchers.
 - A dataformat accomodating most logging needs due to its flexibility.
 - An ecosystem of tools to help users extend the software to fit their needs.

Reason for existence
--------------------

.. TODO We should add more of the reasons that we write about in the README

There are plenty of companies offering services which do collection of Quantified Self data with goals
ranging from increasing personal producivity to understanding the people that managers manage (organizational
productivity). However, all known services suffer from a significant disadvantage, the users data is in
the hands of the service providers which leads to the problem of trust. Every customer of these
companies have their data in hands they are forced to trust if they want to use their service.

This is a significant problem, but the true reason that we decided to do something about it was that
existing solutions were inadequate. They focused on short-term insight, a goal worthy in itself, but we also
want long-term understanding. We made it completely free and open source so anyone can
use, improve and extend it.


Data philosophy
---------------

Data in it's raw form is always the most valuable.

Quantified self data doesn't take much space by todays standards, but for services such as RescueTime which have over
than thousand of customers, every megabyte per user counts.

For the users however, every megabyte of data is worth it. It is therefore of importance that we collect and
store data in the highest reasonable resolution such that we later don't have to "fill the gaps" in lower resolution
data with lossy heuristics.

Many services doing collection and analysis of QS data today don't actually store the raw data but instead
store only summaries (such as only storing how long you used an applicatin during a given hour, instead of
storing the individual uses). This is a problem with existing services: they store summarized data instead of the raw data.

This is indicative of that they actually lack a long-term plan. They want to provide a certain type of analysis *today* but
we expect to want to do some unknown analysis in the future, and for that we might need the raw data.

*Simply put: It is of importance that we start collecting raw data now, because if we don't it will be forever lost.*

