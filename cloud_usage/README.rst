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

Sample Run
-----------

.. code::

    $ cloud-usage
    Moudle:cinder
    +--------+-----------+---------+
    | tenant | gigabytes | volumes |
    +--------+-----------+---------+
    | total  |     0     |    0    |
    +--------+-----------+---------+
    Moudle:keystone
    +--------+-------+----------+
    | tenant | users | projects |
    +--------+-------+----------+
    | total  |   5   |    3     |
    +--------+-------+----------+
    Moudle:nova
    +--------+-----+-----------+-----------+-------+------+------+
    | tenant | ram | ephemeral | instances | vcpus | swap | disk |
    +--------+-----+-----------+-----------+-------+------+------+
    | total  |  0  |     0     |     0     |   0   |  0   |  0   |
    +--------+-----+-----------+-----------+-------+------+------+
    Moudle:swift
    +--------+-------+------------+
    | tenant | bytes | containers |
    +--------+-------+------------+
    | total  |   0   |     0      |
    +--------+-------+------------+
    Moudle:glance
    +----------------------------------+--------+-------------+
    |              tenant              | images |    bytes    |
    +----------------------------------+--------+-------------+
    |              total               |   4    | 22808822272 |
    | b67d3ad8bdfc4f07b17281d4c26715d7 |   1    |   18350080  |
    | 724a9104d7aa46b6aaf101895c63b385 |   3    | 22790472192 |
    +----------------------------------+--------+-------------+

Python Script
--------------

.. code::

    >>> from cloud_usage.client import CloudUsage
    >>> help(CloudUsage)
