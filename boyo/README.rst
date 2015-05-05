###############################
S3 Command Line Client, or Boyo
###############################
Connect to OpenStack using the s3 python boto module

=======
Install
=======

.. code::

    $ git clone https://github.com/tylernorth/OpenDerp.git
    $ cd OpenDerp
    $ pip install boyo/

============
Command Line
============
.. code::

    $ boyo --help
    # List all buckets/containers
    $ boyo list

=============
Python Script
=============
.. code::

    python
    >>> from boyo.client import BoyoClient
    >>> c = BoyoClient(username, password, tenant_name, auth_url)
    >>> c.boto
    S3Connection:192.168.2.9
