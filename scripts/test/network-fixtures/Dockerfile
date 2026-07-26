FROM python:3.12-alpine

WORKDIR /srv
COPY fixture-server.py /srv/fixture-server.py
COPY public /srv/public
EXPOSE 8080
CMD ["python3", "/srv/fixture-server.py"]
