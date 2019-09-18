`st`: The SuperTunnel
---------------------

|GithubActions|_ |PyPi|_

.. |GithubActions| image:: https://github.com/alexrudy/supertunnel/workflows/Supertunnel%20CI/badge.svg
.. _GithubActions: https://github.com/alexrudy/supertunnel/actions

.. |PyPi| image:: https://badge.fury.io/py/supertunnel.svg
.. _PyPi: https://badge.fury.io/py/supertunnel

`st` is a supercharged SSH tunnel manager, useful for managing SSH
connections that you want to be long lived.

To forward port 8888 from ``host.example.com``::

    $ st forward -p 8888 host.example.com
    Forwarding ports:
    1) local:8888 -> remote:8888
    ^C to exit
    [connected] 0:00:00 |

The tunnel will be kept alive, both by ssh and by supertunnel. If you lose your
network connection for a while, or if you suddenly get cut off, supertunnel
works with ssh to notice the connection failure, and seamlessly restarts the
tunneling process.

That just scratches the surface of what supertunnel can do though.

Why supertunnel?
****************

I wrote this script when I used to ride a train through a tunnel every day, and
it would interrupt my connection to a Jupyter notebook on a remote server, but
it is useful for a lot more – think about any time your SSH connection drops,
and you have to go find that terminal window and start it up again. Now think
about never doing that again. That's what ``st`` provides.

``st`` is designed to be fairly flexible (my needs have evolved over time) but
still simple enough that someone who doesn't want to understand the intricacies
of SSH tunneling could use it.

It is written in Python 3, and relies on the command line tool library click_,
but just running ``pip install supertunnel`` should get you the ``st`` command.

Why not just use ssh?
*********************

This tool restarts your SSH connection when it goes away. But really, you could
probably do this all some other way, and thats fine! Go for it! If your way is
really awesome, open an issue_ and let me know about it.

.. _click: https://click.palletsprojects.com/
.. _issue: https://github.com/alexrudy/supertunnel/issues

