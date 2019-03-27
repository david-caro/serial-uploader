# Serial Uploader


Simple script to upload switch configurations though a serial connection.


Just have the configuration that you want to upload in a file, and run::

    sudo serial_uploader \
        --config-file my_switch_config.txt -
        --serial-device-path /dev/ttyUSB0



If you need user and password, you can pass the username, and the password
will be prompted for::

    sudo serial_uploader \
        --config-file my_switch_config.txt \
        --serial-device-path /dev/ttyUSB0 \
        --user myuser
