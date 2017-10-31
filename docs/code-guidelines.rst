Code guidelines
===============

.. note::
    This is highly WIP.

These are recommendations, not rules.

You should probably follow them, but if they don't improve things, `break them <https://en.wikipedia.org/wiki/Wikipedia:Ignore_all_rules>_`.

Testing
-------

We don't test everything, since that takes too much effort,
instead we focus on testing the critical parts of the code.

Use your best judgement when evaluating if code is critical,
but as an example: :code:`aw-core` is used in almost every other module and we
therefore aim for >90% code coverage with our unittests there.
We also do some integration testing and typechecking.
This makes it the most extensively tested part of ActivityWatch.

Some of our testing methods:

- Unittests (with code coverage analysis)
- Integration tests
- Typechecking (with mypy)

Deprecation
-----------

Sometimes, old code gets replaced by better, backwards-incompatible, code.

Whenever you write something better than the old code, you can get tempted
to immediately remove the old code. **But don't!**

Instead, mark the code as deprecated. Preferably, you should do this using the
:code:`@deprecated` decorator in aw-core, but you could also just leave a comment
or add a warning message when it is run.

There is one exception to this rule:
If there are no other packages where the function/class you are replacing is called,
then you may go ahead and delete the old stuff immediately since there is no risk of
you breaking anything.

This guideline was initially conceived in `this PR <https://github.com/ActivityWatch/aw-server/pull/35#issuecomment-340752237>_`.
