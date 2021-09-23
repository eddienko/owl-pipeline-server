FROM imaxt/owl-server:0.8.3

RUN DEBIAN_FRONTEND=noninteractive

CMD ["/bin/bash"]

USER root

# Install all base dependencies
RUN apt-get update && apt install sudo git gcc make ruby ruby-dev python3 \
    libpam0g-dev libmariadb-client-lgpl-dev libmysqlclient-dev wget vim -y

# install gem needed for dpkg
RUN gem install fpm

# Install munge
RUN apt-get install libmunge-dev libmunge2 munge -y

# Install hdf5
RUN apt-get install libhdf5-serial-dev hdf5-tools -y


# Install MariaDB for slurm accounting (as the instructions state, change the password)
RUN apt-get install mariadb-server -y

# RUN service mysql start
# RUN service munge start

RUN mkdir /slurm

WORKDIR /slurm
RUN wget https://download.schedmd.com/slurm/slurm-20.02.7.tar.bz2
RUN tar xvf slurm-20.02.7.tar.bz2
WORKDIR /slurm/slurm-20.02.7
RUN ./configure --prefix=/slurm/slurm-build --sysconfdir=/etc/slurm --enable-pam \
    --with-pam_dir=/lib/x86_64-linux-gnu/security/ --without-shared-libslurm
RUN make
RUN make contrib
RUN make install

WORKDIR /slurm
RUN fpm -s dir -t deb -v 1.0 -n slurm-20.02.7 --prefix=/usr -C /slurm/slurm-build .
RUN dpkg -i slurm-20.02.7_1.0_amd64.deb

# Add the slurm user
RUN useradd -m -u 1004 slurm

# Make runtime and conf directories
RUN mkdir -p /etc/slurm /etc/slurm/prolog.d /etc/slurm/epilog.d /var/spool/slurm/ctld \
    /var/spool/slurm/d /var/log/slurm /var/run/slurm

# Get example files and copy to corresponding directories
RUN git clone https://github.com/mknoxnv/ubuntu-slurm.git
RUN cp ubuntu-slurm/slurmd.init /etc/init.d/slurmd
RUN cp ubuntu-slurm/slurm.default /etc/default/slurm
RUN chmod 755 /etc/init.d/slurmd
RUN cp ubuntu-slurm/slurmdbd.init /etc/init.d/slurmdbd
RUN chmod 755 /etc/init.d/slurmdbd
RUN cp ubuntu-slurm/slurmdbd.service /etc/systemd/system/
RUN cp ubuntu-slurm/slurmdbd.conf /etc/slurm/

RUN chown slurm /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm /var/run/slurm

RUN rm -rf slurm-20.02.7.tar.bz2
RUN rm -rf slurm-20.02.7_1.0_amd64.deb

COPY docker/initialize-mariadb.sql initialize-mariadb.sql
COPY docker/start-slurm-cluster.sh start-slurm-cluster.sh
COPY docker/slurm.conf /etc/slurm/slurm.conf
RUN chmod +x start-slurm-cluster.sh
RUN chmod a+rw /etc/slurm/slurm.conf
ENV CMD_INIT=/slurm/start-slurm-cluster.sh

RUN echo "Cmnd_Alias MUNGE = /usr/sbin/service munge start\nuser    ALL=(ALL) NOPASSWD: MUNGE" > /etc/sudoers.d/munge
RUN echo "Cmnd_Alias MYSQL = /usr/sbin/service mysql start, /usr/bin/mysql\nuser    ALL=(ALL) NOPASSWD: MYSQL" > /etc/sudoers.d/mysql
RUN echo "Cmnd_Alias SLURM = /usr/sbin/service slurmdbd start, /usr/sbin/slurmctld, /usr/sbin/slurmd\nuser    ALL=(ALL) NOPASSWD: SLURM" > /etc/sudoers.d/slurm


WORKDIR /home/user

USER 1000

