ARG BASE_CONTAINER=imaxt/owl-server:0.8.3
FROM ${BASE_CONTAINER}

RUN DEBIAN_FRONTEND=noninteractive

USER root

# Install all base dependencies
RUN apt-get update && \
    apt install -yq  --no-install-recommends \
    gcc make ruby ruby-dev python3 \
    libpam0g-dev libmariadb-client-lgpl-dev libmysqlclient-dev \
    libmunge-dev libmunge2 munge \
    libhdf5-serial-dev hdf5-tools \
    mariadb-server \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# install gem needed for dpkg
RUN gem install fpm

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
RUN git clone https://github.com/mknoxnv/ubuntu-slurm.git && \
    cp ubuntu-slurm/slurmd.init /etc/init.d/slurmd && \
    cp ubuntu-slurm/slurm.default /etc/default/slurm && \
    chmod 755 /etc/init.d/slurmd && \
    cp ubuntu-slurm/slurmdbd.init /etc/init.d/slurmdbd && \
    chmod 755 /etc/init.d/slurmdbd && \
    cp ubuntu-slurm/slurmdbd.service /etc/systemd/system/ && \
    cp ubuntu-slurm/slurmdbd.conf /etc/slurm/

RUN chown slurm /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm /var/run/slurm

RUN rm -rf slurm-20.02.7.tar.bz2
RUN rm -rf slurm-20.02.7_1.0_amd64.deb

COPY docker/initialize-mariadb.sql initialize-mariadb.sql
COPY docker/slurm.conf /etc/slurm/slurm.conf
RUN chmod a+rw /etc/slurm/slurm.conf
ADD docker/etc.slurm /etc
RUN chmod -R +x /etc/cont-init.d && chmod -R +x /etc/cont-finish.d

RUN echo "Cmnd_Alias MUNGE = /usr/sbin/service munge start, /usr/sbin/service munge stop\nuser    ALL=(ALL) NOPASSWD: MUNGE" > /etc/sudoers.d/munge && \
    echo "Cmnd_Alias MYSQL = /usr/sbin/service mysql start, /usr/sbin/service mysql stop, /usr/bin/mysql\nuser    ALL=(ALL) NOPASSWD: MYSQL" > /etc/sudoers.d/mysql && \
    echo "Cmnd_Alias SLURM = /usr/sbin/service slurmdbd start, /usr/sbin/service slurmdbd stop, /usr/sbin/slurmctld, /usr/sbin/slurmd\nuser    ALL=(ALL) NOPASSWD: SLURM" > /etc/sudoers.d/slurm && \
    chmod o-r /etc/sudoers.d/*

WORKDIR /home/user
USER 1000

ENTRYPOINT ["/init", "/usr/local/bin/start.sh"]
