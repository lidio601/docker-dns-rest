FROM alpine:3.1
MAINTAINER "André Martins <aanm90@gmail.com>"
COPY . /data
RUN /data/bootstrap
EXPOSE 80
ENTRYPOINT ["/data/docker_dnsrest"]

