TAG=latest
IMAGE=sagui_backend

all: docker-build docker-push

docker-build:
	docker build -t pigeosolutions/${IMAGE}:${TAG} .

docker-push:
	docker push pigeosolutions/${IMAGE}:${TAG}
