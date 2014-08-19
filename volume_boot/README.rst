Volume Boot
============

One line command to boot from volume

Installation
-------------

.. code::

    git clone https://github.com/tylernorth/OpenDerp.git
    cd OpenDerp/compute_scripts/
    pip install volume_boot/

Command Line
--------------

.. code::

    $ volume-boot --help
    usage: volume-boot [-h] [--username USERNAME] [--password PASSWORD]
                       [--tenant-name TENANT_NAME] [--auth-url AUTH_URL]
                       {boot,snapshot} ...

    Manage Boot From Volume Instances

    positional arguments:
      {boot,snapshot}       Sub-command
        boot                Create instance from bootable volume
        snapshot            Snapshot instance

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

    >>> from volume_boot import VolumeBoot
    >>> help(VolumeBoot)
