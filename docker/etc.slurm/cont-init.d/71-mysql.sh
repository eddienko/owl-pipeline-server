#!/usr/bin/with-contenv bash

sudo service mysql start
sudo mysql -u root < /slurm/initialize-mariadb.sql

