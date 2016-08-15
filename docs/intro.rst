Introduction
============

ActivityWatch is a bundle of software that provides storage for life-logging data such as what you do on your
computer.

What the system does is handle collection and retrieval of all kinds of logging data (relating to your life,
your computer or any type of record of an event). aw-server provides a safe repository where you store your data,
it is not a place for modification (providing data integrity), once a record is created, it is intended to
be immutable.

What ActivityWatch is
---------------------

* A set of watchers (i.e. afk-watcher, window-watchers) that record relevant information about what you do and what happens on your computer
* A way of storing data collected from a wide variety of sources in an immutable manner: Events added are persistent and the stored data cannot be changed unless it's first copied.
* Provides a common dataformat accomodating most needs in a flexible yet simple manner

What ActivityWatch isn't
------------------------

* A tool for doing advanced data analysis
* A full-fledged data visualization tool

Reason for existence
--------------------

There are plenty of companies offering services which do collection of Quantified Self data with goals
ranging from increasing personal producivity to understanding the people that managers manage (organizational
productivity). However, all known services suffer from a significant disadvantage, the users data is in
the hands of the service providers which leads to the problem of trust. Every customer of these
companies have their data in hands they are forced to trust if they want to use their service.

This is a significant problem, but the true reason that we decided to do something about it was that
existing solutions were inadequate. They focused on short-term insight, a goal worthy in itself, but we also
want long-term understanding. Making the software completely free and open source so anyone can
{use, audit, improve, extend} it seemed like the only reasonable alternative.


Data philosophy
---------------

Raw data is always the most valuable data.

QS data doesn't take much space by todays standards, but when you are a service having thousand of
customers, every megabyte per user counts.

For the users however, every megabyte of data is worth it. It is therefore of importance that
we collect and store data in the highest reasonable resolution such that we later don't have to "fill the gaps"
in incomplete or aggregated data with heuristics and trickery.

Many services doing collection and analysis of QS data today don't actually store the raw data but instead
store only summaries or low-resolution data (such as summarizing all time within an interval, instead of
storing the individual intervals). This is a problem today with existing services: they store summarized data instead of the raw data.

This is indicative of that they actually lack a long-term plan. They want to provide a certain type of analysis *today*, which is fine,
but we expect to want to do some unknown analysis in the future, and for that we might need the raw data.
And we suspect that we would rather choose how detailed our analysis should be then rather than saving a bit of space by reducing the data resolution and detail before storing it.

*Simply put: it is of importance that we start collecting the raw data now, before it disappears into the aether.*


Security
--------

One of the reasons this project was started was due to the fact that we were missing security in how
our Quantified Self data was stored. Data needs to be collected on many devices, and be stored at a
central and secure location or distributed for redundancy.

Since we want to be able to provide a safe storage service for initial users who do not have the
time to run a server of their own, we will provide a feature such that we will only have the users
encrypted data, without information of the contents (with exception for some relatively unimportant
metadata such as allocated storage space, sessions, clients, and number of entries).

**NOTE:** Security features discussed here are all considered work in progress and this software is
not yet fit for exposure to the internet. Only allow connections from localhost!

