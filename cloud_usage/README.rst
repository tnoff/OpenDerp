Cloud Usage
============

Get a summary of used resources on an OpenStack Cluster

Install
--------

.. code::

    git clone https://github.com/tylernorth/OpenDerp.git
    cd OpenDerp/
    pip install cloud_usage/

Command Line
-------------

.. code::

    $ cloud-usage --help
    usage: cloud-usage [-h] [--username USERNAME] [--password PASSWORD]
                       [--tenant-name TENANT_NAME] [--auth-url AUTH_URL]

    Create & Setup OpenStack Accounts

    optional arguments:
      -h, --help            show this help message and exit
      --username USERNAME   OpenStack Auth username
      --password PASSWORD   OpenStack Auth password
      --tenant-name TENANT_NAME
                            OpenStack Auth tenant name
      --auth-url AUTH_URL   OpenStack Auth keystone url

Python Script
--------------

.. code::

    from cloud_usage import CloudUsage
    help(CloudUsage)
