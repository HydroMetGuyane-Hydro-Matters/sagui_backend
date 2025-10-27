SHELL := /bin/bash
TAG=latest
IMAGE=pigeosolutions/sagui_backend
git_tag := $(shell git rev-parse --short HEAD)
date := $(shell date +%Y%m%d-%H%M)

all: docker-build docker-push

docker-build:
	docker build -f Dockerfile -t ${IMAGE}:latest . ;\
	echo built ${IMAGE}:latest ;\
	docker tag  ${IMAGE}:latest ${IMAGE}:$(date)-$(git_tag) ;\
	echo built ${IMAGE}:$(date)-$(git_tag)

docker-push:
	docker push ${IMAGE}:latest ;\
	echo pushed ${IMAGE}:latest ;\
	docker push ${IMAGE}:$(date)-$(git_tag) ;\
	echo pushed ${IMAGE}:$(date)-$(git_tag)
