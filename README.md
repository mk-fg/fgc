fgc: misc tools to address py stdlib shortcomings
--------------------

It's mostly outdated assembly of the stuff I needed here and there...

IMO stuff like binding for posix acls and capabilities should be in python
stdlib, but there are probably nice enough modules for these available today.

I'll probably need to split this stuff up by-purpose, then either merge with
some already existing solution (if it's lacking something essential), release as
a standalone module if there's nothing similar, or just drop, if it's
redundant/unused stuff.
