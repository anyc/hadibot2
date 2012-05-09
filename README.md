HaDiBot2
========

During my free time, I created an IRC bot that helps managing our local 
network infrastructure in the HaDiKo ( http://www.hadiko.de ). Its main 
purpose is to notify about various events and it even does some monitoring 
on its own. It is written in Python and the focus lies on simplicity and 
modularity. Although it is mainly used for monitoring, it has a modular 
design and can be applied in other areas.

Current features:

    Controllable over IRC or an interactive shell
    Plugin infrastructure (allows reload during runtime)
    User authentication
    LDAP plugin for "group auto-op" and object monitoring
    cat2irc plugin allows simple messaging from scripts (see 
	Syslogfilter http://home.hadiko.de/~anyc/syslogfilter.html )

