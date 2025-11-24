FROM bluenviron/mediamtx:1.15.4 AS rtsp
FROM python:3.9-trixie

COPY --from=rtsp mediamtx .
COPY --from=rtsp mediamtx.yml .

RUN sed -r -i 's/^(api:\s*)no/\1yes/' mediamtx.yml

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY updater.py .
COPY cfg.yml .

RUN cat cfg.yml >> mediamtx.yml && rm cfg.yml

EXPOSE 8554

ENV API_HOST=https://<trassir_host>:8080
ENV RTSP_HOST=rtsp://<trassir_host>:555

ENV LOGIN=<login>
ENV PASSWORD=<password>

ENV PATHS=*

ENTRYPOINT [ "/mediamtx" ]
