# Alert-autoconf
## Alerting auto confuration

This Utility uses a configuration file (alert.yaml), and automatically creates triggers and alerts.

### Docker run: Triggers/Notifications create/edit/del

You need to be in the directory with the configuration file "./alerts.yaml"

```shell
docker pull registry.yourdomain.ru/alerting/alert:latest && docker run -v `pwd`:/conf registry.yourdomain.ru/alerting/alert:latest \
    --user $LOGIN --password $PASSWORD \
    --redis_token_storage "redis://$REDIS:6379/1"" \
    --token "hands::$SERVICE::$ENV" \
    --log-level DEBUG
    --cluster $CLUSTER
```
$SERVICE - the name of the service for which triggers and notifications will be created
$ENV - prod/staging/dev
$LOGIN - it is best to use system account
$PASSWORD - password
$REDIS - redis host for internal metadata
$CLUSTER (optional) - we use this optional parameters to deploy the same triggers to different k8s clusters

### Validation config file (alert.yaml):
```shell
docker run -v `pwd`:/conf registry.yourdomain.ru/alerting/alert-validator:latest \
    --log-level DEBUG
```
```shell
docker pull registry.yourdomain.ru/alerting/alert-validator:latest; \
find . -type f -iname 'alert.yaml' -print0 | \
xargs --null --max-args=1 --max-procs=1 --no-run-if-empty -I{} \
docker run -v `pwd`:/conf  registry.yourdomain.ru/alerting/alert-validator:latest\
    --log-level DEBUG \
    --config "{}"
```

### Tests run 

```shell
docker run -ti --entrypoint=make registry.yourdomain.ru/alerting/alert:latest test
```

### Config file describe
The configuration file consists of two required sections:

  "triggers:" - configuring triggers
  "alerting:" - setting of contacts for notification

```
---
version: "1"                  # version package "1" or "1.1"
prefix: "any-string-"         # a prefix is added for the names of triggers and tags
                              # (only for version: "1.1")

# Блок триггеров
triggers:s
  - name: Trigger_1           # Trigger name
    targets:                  # Targets list
      - apps.services.my_service.api.query_rec_POST.request_time.200.count
      - apps.services.my_service.api.query_rec_POST.request_time.5*.count
    desc: Test description 1  
    dashboard: "http://grafana.yourdomain.ru/grafana/d/000000596/graphite-clickhouse?panelId=17&fullscreen"
                              # Link to a specific dashboard panel in Grafana
    is_pull_type: true        # Fetch data in Graphite without using Moira's internal storage. Flase by default.
    pending_interval:0        # The number of seconds that the trigger must spend in the new state 
                              # before Moira sends a notification on it
    warn_value: 15            # Execute mailing with the status' WARN
    error_value: 10           # Execute mailing with the status' ERROR 

                              # (If the value of the error_value field is greater than or equal to warn_value,
                              #  then the notification algorithm will be as follows: 
                              #  Execute 'Warning' or 'Error' - if the metric value is greater than the specified
                              # )

    ttl: 600                  # The number of seconds after which you need to make a mailing with the status from the 'ttl_state' field
    tags:                     # Subset of triggers
      - service-1
      - "cluster-{cluster}"   # Dynamic cluster name substitution (Optional!)
                              # (Strings that use {cluster} are recommended to be wrapped in quotes 
                              #  so that the yaml parser does not swear)
    ttl_state: OK             # OK | WARN | ERROR | NODATA | DEL
                              # All states are described here - http://moira.readthedocs.io/en/latest/user_guide/efficient.html

    parents:                  # List of parent triggers (optional)
      - name: "DC shutdown"   # The link to the parent is his name and a set of tags
        tags:
        - datacenters
        - global
      - name: "autoconf maintenance"
        tags:
        - autoconf

    expression: "t1 > 10 ? ERROR : (t2 > 4 ? WARN : OK)"
                              # Expression input.
                              # Supports govaluate and graphite syntax. (t1, t2, tN - in the order specified in targets)
                              # Described - http://moira.readthedocs.io/en/latest/user_guide/advanced.html

    time_start: "12:30"       # Start time of this trigger
    time_end: "23:59"         # End time of this trigger
    day_disable:              # Days in which triggers don't work (list)
      - Tue                   # Mon | Tue | Wed | Thu | Fri | Sat | Sun

  - name: Trigger_2
    targets:
      - movingAverage(apps.services.{cluster}.monitoring.modules.worker.*.handleMessage.time.count, 2)
    dashboard: grafana.yourdomain.ru/grafana/d/000000596/graphite-clickhouse?panelId=17&fullscreen
    is_pull_type: true
    ttl: 60
    ttl_state: ERROR
    expression: "t1 <= 0.3 ? ERROR : OK"
    tags:
      - sms
      - mail
      - slack


# Alerting section
alerting:
  # Simple notifications
  - tags:                            # List of tags used in trigger descriptions
      - service 1                    # It is enough to match one tag with a trigger tag
    time_start: "12:30"              # Application start time
    time_end: "23:50"                # Application end time
    day_disable:                     # Days in which this setting is ignored
      - Tue
    contacts:                        # List of available contacts
      - type: mail                   # type of notification. It is possible to specify the following values:
                                     # mail, send-sms, slack, jira
        value: qwe@qwe.qwe           # Contact value. The text in the field must be enclosed in quotation marks,
                                     # if special symbols #, @, +, etc. are used.

  # Notify with escalations
  - tags:
      - service_1
      - ERROR
    contacts:
      - type: slack
        value: #channel_service_1                 # Send a notification to the Slack channel of the service owners
      - type: send-sms
        value: +7123456789                        # Duty person service-1
    escalations:                                  # Escalation section. 
                                                  #  If it is described in the subscription, then all messages sent to Slack will have an "Acknoweledge" button
      - contacts:                                 # Escalation will be interrupted if the "Acknoweledge" button was pressed, 
          - type: jira                            #  or the trigger itself returned to the "OK" state during this time.
            value: monitoring_team_24x7
          - type: slack                           # Send a notification to the Slack team 24x7
            value: #channel_monitoring_team_24x7  
        offset_in_minutes: 5                      # Notification will be sent 5 minutes after the start

      - contacts:                     
          - type: send-sms             
            value: '+7123456789'                  # Team lead responsible for the service       
        offset_in_minutes: 10                     # Notifications will be sent 10 minutes after the start
```

---
Example configuration file:
 ./tests/valid_config.yaml
 ./tests/valid_config_blank.yaml
 
