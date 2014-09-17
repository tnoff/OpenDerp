Shrink Images
--------------

Install
-------

.. code::

    git clone https://github.com/tylernorth/OpenDerp.git
    cd OpenDerp/image_scripts/
    pip install shrink_image/

Command Line
-------------

.. code::

    $ shrink-image --help
    usage: shrink-image [-h] [--username USERNAME] [--password PASSWORD]
                        [--tenant-name TENANT_NAME] [--auth-url AUTH_URL]
                        [--name NAME] [--all]
                        [image_id]

    Manage Boot From Volume Instances

    positional arguments:
      image_id              Image_id

    optional arguments:
      -h, --help            show this help message and exit
      --username USERNAME   OpenStack Auth username
      --password PASSWORD   OpenStack Auth password
      --tenant-name TENANT_NAME
                            OpenStack Auth tenant name
      --auth-url AUTH_URL   OpenStack Auth keystone url
      --name NAME           Image name
      --all                 Convert all images

Python Scripting
-----------------

.. code::

    >>> from shrink_image.client import ShrinkImage
    >>> help(ShrinkImage)
