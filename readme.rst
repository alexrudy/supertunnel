``st``: The SuperTunnel
-----------------------

``st`` is a supercharged SSH tunnel manager, useful for managing SSH 
connections that you want to be long lived.

I wrote this script when I used to ride a train through a tunnel every day, and
it would interrupt my connection to a Jupyter notebook on a remote server, but
it is useful for a lot more – think about any time your SSH connection drops,
and you have to go find that terminal window and start it up again. Now think
about never doing that again. That's what ``st`` provides.

``st`` is designed to be fairly flexible (my needs have evolved over time) but still
simple enough that someone who doesn't want to understand the intricacies of SSH
tunneling could use it.

It is written in Python 3, and relies on the command line tool library `click`_,
but just running ``pip install supertunnel`` should get you the ``st`` command.


.. click_: https://click.palletsprojects.com/

