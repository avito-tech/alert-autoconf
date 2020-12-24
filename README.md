# Alert auto config

Утилита, которая по файлу конфигурации позволяет автоматически создать триггеры и установить оповещения.

## Запуск в докере

В текущей директории должен быть файл ./alert.yaml с конфигурацией.

### Для валидации файла:
```shell
docker run -v `pwd`:/conf registry.yourdomain.ru/alerting/alert-validator:latest \
    --log-level DEBUG
```

### Для создания триггеров:
```shell
docker pull registry.yourdomain.ru/alerting/alert:latest && docker run -v `pwd`:/conf registry.yourdomain.ru/alerting/alert:latest \
    --user $LOGIN --password $PASSWORD \
    --redis_token_storage "redis://monitoring01:6379/5"" \
    --token "hands::$serviceName::$env" \
    --log-level DEBUG
    --cluster omicron
```
*!!! $serviceName::$env - нужно заменить на реальные названия сервиса и окружения*
где PASSWORD, это Ваш пароль от LDAP (Jira,Cf,etc...). С случае с выкаткой через тимсити используется системный пользователь alert-autoconf.
`--cluster omicron` — это строка, на которую будет заменяться `{cluster}` в тэгах в alert.yaml. Если в yaml не используется `{cluster}`, то можно не указывать `--cluster`. Если указан `--cluster`, то можно не указывать `--token`, он сгенерится автоматически (но можно и указать).

### Для валидации alert.yaml (запускать в директории с alert.yaml):
```shell
docker pull registry.yourdomain.ru/alerting/alert-validator:latest; \
find . -type f -iname 'alert.yaml' -print0 | \
xargs --null --max-args=1 --max-procs=1 --no-run-if-empty -I{} \
docker run -v `pwd`:/conf  registry.yourdomain.ru/alerting/alert-validator:latest\
    --log-level DEBUG \
    --config "{}"
```

## Запуск приложения

### Для валидации файла:
```shell
validate.py --url hostname --config config_file --log-level DEBUG
```

### Для создания триггеров:
```shell
alert.py --url hostname --config config_file --user username --password password --log-level DEBUG
```

## Запуск тестов

```shell
docker run -ti --entrypoint=make alert-autoconf test
```


Файл конфигурации состоит из двух блоков:
 - Настроика триггеров (triggers)
 - Настройка контактов для оповещения (alerting)

В файле конфигурации обязятельно должен присутствовать блок контактов.

Блок триггеров состоит из следующих полей:
```
---
version: "1"                  # Версия пакета "1" или "1.1"
prefix: "any-string-"         # Аналог namespace для имён триггеров и тегов в moira,
                              # дополняет triggers[].name, triggers[].tags[] и alerting[].tags
                              # (только для version: "1.1")

# Блок триггеров
triggers:s
  - name: Trigger_1           # Имя триггера
    targets:                  # Список метрик
      - stats.timers.service.rec-collab.service.dev.api.rec_rec_POST.request_time.404.mean
      - stats.timers.service.rec-collab.service.dev.api.rec_rec_POST.request_time.404.mean
    desc: Test description 1  # Описание триггера
    dashboard: "http://mntr.yourdomain.ru/grafana/d/000000596/graphite-clickhouse?panelId=17&fullscreen"
                              # Ссылка на конкретную панель дашборда в Grafana (http://mntr.yourdomain.ru/grafana)
    is_pull_type: true        # Ходить за данными в Graphite, не используя внутреннее хранилище Moira. По умолчанию Flase.
    pending_interval:0        # Сколько времени должен триггер находится в новом состоянии, перед тем как Мойра отправит по нему нотификацию
    warn_value: 15            # Выполнить рассылку со статусом 'Warning', если значение графика будет меньше указанного
    error_value: 10           # Выполнить рассылку со статусом 'Error', если значение графика будет меньше указанного

                              # (Если значение поля error_value больше или равно warn_value, то алгоритм оповещения
                              #  будет следующий:
                              #  Выполнить 'Warning' или 'Error' - если значение метрики больше указанного
                              # )

    ttl: 600                  # Количество секунд, через которе нужно сделать рассылку со статусом из поля 'ttl_state'
    tags:                     # Группа для оповещения
      - service 1
      - "cluster-{cluster}"   # Динамическая подстановка имени кластера
                              # (строки, в которых используется {cluster}, рекомендуется оборачивать в кавычки, чтобы парсер yaml не ругался)
    ttl_state: OK             # OK | WARN | ERROR | NODATA | DEL
                              # все состояния здесь - http://moira.readthedocs.io/en/latest/user_guide/efficient.html

    parents:                  # Список родительских триггеров (необязательно)
      - name: "DC shutdown"   # Ссылка на родителя — это его имя и набор тэгов
        tags:
        - datacenters
        - global
      - name: "autoconf maintenance"
        tags:
        - autoconf

    expression: "(t1 > 10) ? ERROR : ((t2 > 4) ? WARN : OK)"
                              # Ввод выражения.
                              # Поддерживает синтаксис govaluate и graphite. (t1, t2, tN - в порядке, указанном в targets)
                              # Подробнее - http://moira.readthedocs.io/en/latest/user_guide/advanced.html

                              # (По приоритету выше, чем warn_value && error_value )
    time_start: "12:30"       # Время начала применения данного триггера
    time_end: "23:59"         # Время окончания применения данного триггера
    day_disable:              # Дни, в которых данная настройка игнорируется (list)
      - Tue                   # Возможные значения:
                              #   Mon, Tue, Wed, Thu, Fri, Sat, Sun

  - name: Trigger_2
    targets:
      - movingAverage(apps.services.{cluster}.monitoring.modules.worker.*.handleMessage.time.count, 2)
    dashboard: mntr.yourdomain.ru/grafana/d/000000596/graphite-clickhouse?panelId=17&fullscreen
    is_pull_type: true
    ttl: 60
    ttl_state: ERROR
    expression: "t1 <= 0.3 || t1 > 5 ? ERROR : OK"
    tags:
      - sms
      - mail
      - slack


# Блок оповещения
alerting:
  - tags:                            # Список тегов, задействованных в описании триггеров
      - service 1                    # Достаточно совпадения одного тега с тегом триггер
    time_start: "12:30"              # Время начала применения
    time_end: "23:50"                # Время окончания применения
    day_disable:                     # Дни, в которых данная настройка игнорируется
      - Tue
    contacts:                        # Список доступных контактов
      - type: mail                   # тип оповещения. Возможно указать следующие значения:
                                     # mail, send-sms, slack, twilio sms, twilio voice
        value: qwe@qwe.qwe           # значение контакта. Текст в оле нужно заключтиь в кавычики,
                                     # если используются спец-символы #,@,+ и т.д.

  - tags:
      - service_1
      - ERROR
    contacts:
      - type: slack
        value: #channel_service_1      # Уведомление улетает в канал владельцев сервиса
      - type: slack
        value: '#spb_monitoring'       # Уведомление улетает в канал команды мониторинга 24х7
      - type: jira
        value: 'group_spb_monitoring'  # По данному инциденту создается тикет в Jira. (По нему будут оценивать работу во "вне рабочее время")
    escalations:                       # Секция эскалаций. Если она описана в подписке, то у всех сообщений отправляемых в Slack появится кнопка Acknoweledge.
      - contacts:                      # Эскалация прервется в случае если была нажата кнопка Acknoweledge, либо триггер за это время самостоятельно не вернулся в состояние "ОК".
        - type: send-sms                # Уведомление улетает по SMS
          value: '<phone-number>'       # на <phone-number>
        offset_in_minutes: 5            # через 5 минут после отправки первого уведомления.

  - tags:
      - service 1
      - service 2
      - service 3
    contacts:                    # Список допустимых типов контакта
      - type: mail
        value: qwe@qwe.qwe
      - type: send-sms
        value: '+71234567891'
      - type: mail
        value: qwe@qwe.qwe
      - type: pushover
        value: test
      - type: slack
        value: '#chat-name'
      - type: twilio sms
        value: tw_sms
      - type: twilio voice
        value: tw_vioce
```

## Запуск тестов
```shell
make test
```
---
Пример конфигурационного файла можно найти тут:
./tests/valid_config.yaml
./tests/valid_config_blank.yaml

## Свойства триггеров по умолчанию
Триггерам можно задавать свойства по умолчанию в зависимости от тэгов. Например:
```yaml
defaults:
  - condition:      # условие
      tags:         # сейчас поддерживается только `tags`: список тэгов
        - "MONAD"
        - hardware  # все триггеры с тэгами MONAD и hardware (одновременно)
    values:         # значения по умолчанию
      parents:      # сейчас поддерживается только `parents`
        - tags:     # всем триггерам, подходящим под условие, добавляется этот родитель (если его ещё нет)
          - global
          name: 'global parent'
```

Команда для сохранения default'ов в Редис (вручную запускать обычно не надо, запускается в teamcity):
```shell
setdefaults.py -s redis://localhost:6379/0 -c default.yaml
```
