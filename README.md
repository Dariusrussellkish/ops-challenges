## Advanced Backend - Sensor Monitoring Microservices

#### To run locally with Docker:
```shell
# Using Traefik to proxy and load balance between the two service instances
docker build -t sensor-service sensor_service
docker compose up
```
which will put the api on `http://sensor_service.localhost:8080/docs`

#### To run locally with k8s:
```shell
minikube start
eval $(minikube docker-env)
docker build -t sensor-service sensor_service
kubectl create -f sensor_service.yaml
# it can take a few seconds for the redis service to come online and the api to become available
kubectl port-forward service/sensor-api-svc 8080
kubectl delete -f sensor_service.yaml
```

which will expose `http://localhost:8080/docs`

#### Load testing

There's some incredibly rudimentary load testing using `locust`, see the `locustfile.py`. It could be expanded
to test bad/nonsensical inputs as well using the response checking in `locust`. It also serves as rudimentary 
validation of the API for well-defined inputs. 

To run
```shell
pip install locust
locust
```
And navigate to the server linked in stdout and input the # users and spawn rate. 