FROM python:3.7-buster

COPY . $PROJECT_ROOT

RUN pip3 install .

WORKDIR /conf

ENTRYPOINT ["alert.py", "--url", "http://moira.yourdomain.ru/api/", "--user", "alert-autoconf", "--config", "./alert.yaml"]
