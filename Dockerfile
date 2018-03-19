FROM alpine:3.3
MAINTAINER "Patrick Hensley <spaceboy@indirect.com>"
COPY . /data
RUN /data/bootstrap
ENV PY=2.7.9-r0
RUN apk add --update python=$PY python-dev=$PY gcc libgcc libc-dev py-pip libev
COPY ./requirements.txt /data/requirements.txt
RUN pip install -r /data/requirements.txt
RUN apk del python-dev gcc libgcc libc-dev py-pip libev
RUN rm -rf /tmp/*
RUN rm -rf /var/cache/apk/*
EXPOSE 80
COPY . /data
ENTRYPOINT ["/data/docker_dnsrest"]