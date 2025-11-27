# Trassir RTSP proxy
## Basic usage

```
docker buildx build -t trssr-rtsp-proxy https://github.com/Silencer2K/trssr-rtsp-proxy.git
docker run \
    -p 8554:8554 \
    -e API_HOST=https://<trassir_host>:8080 \
    -e RTSP_HOST=rtsp://<trassir_host>:555 \
    -e LOGIN=<login> \
    -e PASSWORD=<password> \
    -e PATHS=* \
    trssr-rtsp-proxy
```
