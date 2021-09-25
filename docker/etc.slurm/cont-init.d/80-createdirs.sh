#!/usr/bin/with-contenv bash

# munge
mkdir /var/run/munge
chown munge:munge /var/run/munge

# mysql
mkdir /var/run/mysqld
chown mysql:mysql /var/run/mysqld