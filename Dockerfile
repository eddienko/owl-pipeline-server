ARG BASE_CONTAINER=ubuntu:18.04
FROM continuumio/miniconda3:4.10.3 as miniconda
FROM ${BASE_CONTAINER}

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND noninteractive
ENV PATH /opt/conda/bin:$PATH

RUN apt-get update \
    && apt-get install -yq --no-install-recommends \
    sudo \
    bzip2 \
    wget \
    ca-certificates \
    locales \
    gcc \
    git \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    mercurial \
    openssh-client \
    procps \
    subversion \
    libc6-dev \
    vim \
    curl \
    make \
    zlib1g-dev libbz2-dev liblzma-dev libssl-dev libcurl4-openssl-dev\
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

COPY --from=miniconda /opt/conda /opt/conda

RUN conda install -y -c conda-forge \
    cython numpy numcodecs blosc lz4 nomkl cytoolz python-blosc pandas \
    psycopg2 ipython tini bokeh ipykernel jupyter_client  && \
    conda clean --all -f -y

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Apply the s6-overlay
ADD https://github.com/just-containers/s6-overlay/releases/download/v2.2.0.3/s6-overlay-amd64-installer /tmp/
RUN chmod +x /tmp/s6-overlay-amd64-installer && /tmp/s6-overlay-amd64-installer / && rm /tmp/s6-overlay-amd64-installer
RUN sed -s s/s6-nuke/sudo\ s6-nuke/ -i /etc/s6/init/init-stage3

ENV S6_KILL_FINISH_MAXTIME=10000
ENV S6_READ_ONLY_ROOT=1
##############################################################################

ADD docker/etc /etc
RUN chmod -R +x /etc/cont-init.d

RUN addgroup --gid 1000 user && \
    adduser --home /home/user --uid 1000 --gid 1000 --disabled-password --gecos None user

RUN chown -R user:user /opt/conda

RUN echo "Cmnd_Alias APT = /usr/bin/apt\nuser    ALL=(ALL) NOPASSWD: APT" > /etc/sudoers.d/apt && \
    echo "Cmnd_Alias S6 = /bin/s6-nuke\nuser    ALL=(ALL) NOPASSWD: S6" > /etc/sudoers.d/s6 && \
    chmod o-r /etc/sudoers.d/*

COPY ./docker/start.sh /usr/local/bin/start.sh
RUN chmod a+rx /usr/local/bin/start.sh

ENV PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user
USER 1000

ENTRYPOINT ["/init", "/usr/local/bin/start.sh"]


