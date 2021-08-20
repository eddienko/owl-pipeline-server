ARG BASE_CONTAINER=continuumio/miniconda3:4.10.3
FROM $BASE_CONTAINER

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update \
    && apt-get install -yq --no-install-recommends \
    wget \
    ca-certificates \
    locales \
    gcc \
    git \
    libc6-dev \
    vim \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

RUN conda install -y -c conda-forge \
    numpy numcodecs blosc lz4 nomkl cytoolz python-blosc pandas \
    psycopg2 ipython tini bokeh && \
    conda clean --all -f -y

COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

COPY ./docker/start.sh /usr/local/bin/start.sh
RUN chmod a+rx /usr/local/bin/start.sh

RUN addgroup --gid 1000 user && \
    adduser --home /user --uid 1000 --gid 1000 --disabled-password --gecos None user

ENV PATH=/user/.local/bin:$PATH


WORKDIR /user
USER 1000

ENTRYPOINT ["tini", "-g", "--", "/usr/local/bin/start.sh"]

