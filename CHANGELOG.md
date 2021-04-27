# 0.4.22
- Added fallback support for special contacts in Slack (such as `_deployer`).
# 0.4.20
- Fixed crash when deleting subscriptions.
# 0.4.19
- Minor bug fixed: comparison of triggers with saturations that have parameters now works correctly.
# 0.4.18
- Saturation support was added.
# 0.4.17
- Added retrai requests to Moira.
# 0.4.16
- Bug fix with failed subscriptions
# 0.4.15
- Now you can configure inheritance for all triggers with the MONAD tag at once.
# 0.4.14
- Supported deletion of all triggers / subscriptions of one file
# 0.4.13
- Subscriptions already saved in other tags are no longer deleted.
# 0.4.12
- Created subscriptions are now also saved in Redis, like triggers.
- Added a link to the assembly in Teamcity in the user agent, in which alert-autoconf is running.
- Improved logs.
# 0.4.11
- {cluster} supported in targets and parents.tags fields
# 0.4.10
- Fixed validate.py
# 0.4.9
- Triggers now roll in two passes to avoid inheritance issues.
# 0.4.7
- Trigger inheritance supported
- Fixed a bug with updating targets, in which duplicate triggers were created instead of updating them.
# 0.4.6
- Schedules in subscriptions
# 0.4.5
- Warn_value and error_value fields must be filled together
# 0.4.4
- User Agent now contains the name and version of the utility
- Corrected documentation
# 0.4.3
- We exclude system tags when selecting triggers for comparison if there is no service token in Redis
# 0.4.2
- Fixed a bug in the comparison of triggers
# 0.4.1
- warning_value renamed to warn_value according to the trigger model in Moira
# 0.4.0
- In docker images, python version has been updated to 3.7
- Used for data validation pydantic
- alerting section made optional
# 0.3.12
- Processing changes in the fields day_disable, time_start, time_end
# 0.3.11
- Updated moira-client version to 2.4.2
# 0.3.10
- Contacts containing "{" are added to exceptions
# 0.3.9
- Fixed bug in validator: section `triggers` is now considered optional
# 0.3.8
- Added MONAD tag to exceptions
# 0.3.7
- Added alert.yaml validation script
# 0.3.6
- Added timeouts for moir client
# 0.3.5
- Fixed problem with prefixes
# 0.3.4
- Fixed problem with prefixes
# 0.3.3
- Fixed processing of dashboards links
# 0.3.2
- Changed the logic of processing triggers, in which changes are not recorded, we no longer update them, making a full scan in radishes!
# 0.3.1
- correct removal of triggers from Radish, when removing them in Moira by hand.
# 0.3.0
- Registration of incoming alert.yaml in Redis (argument "-s" with value "redis: // $ host: $ port / $ db_num").
  Exapmle: "-s redis: // monitoring01: 6379/5"
- Reconciliation of triggers from aletr.yaml with those in Redis (sset) (argument "-t" with value "$ teamCity_project_name").
  Exapmle: "-t service-saga"
- If alert.yaml is absent in the list of registered alert.yaml`s in Redis,
  triggers will be requested according to their tags.
# 0.2.8
- When managing subscriptions, added to exceptions, processing of system tags ERROR, OK, ...
# 0.2.7
- bugfix
# 0.2.6
- removed the addition of prefixes for system tags ERROR, WARN, OK, NODATA
# 0.2.5
- added parameter pending_interval
# 0.2.4
- added check for remote triggers and dashboards
# 0.2.3
- added a check for the presence of contacts when creating a subscription
# 0.2.2
- added escalations in subscriptions
- updated description of alert expressions
# 0.2.1
- Fixed url in entrypoint at http://moira.yourdomain.ru/api/
# 0.2.0
- New version of the config (version: "1.1") with support for `prefix` - an analogue of namespace for trigger names and tags.
# 0.1.5
- Fixed a bug update triggers (Work has been done to optimize the search and identify changed / deleted
  triggers)
# 0.1.4
- The algorithm for updating the subscription to the event has been changed
  When updating the list - those subscriptions that were installed in Moira and which do not change the configuration file in any way,
  I do not delete. Comparison is based on the list of contacts and subscription tags.
- The algorithm for updating triggers has been changed
  As well as in the subscription renewal algorithm - two lists of triggers are formed for comparison. First list
  generated from Moira's data, where triggers from the configuration file are mentioned. Second list for the most
  configuration file. Nothing is done on triggers that fall into the intersection of lists. With the rest
  triggers:
    - if they are from Moira's list, they are removed
    - if they are from the file list, they are added
- Added Dockerfile

# 0.1.3
- The triggers section in the configuration file is optional

# 0.1.2
- Fixed a bug with setting the logging level
- Fixed bug with installing jsonschema from package

# 0.1.1
- Fixed the algorithm for updating the subscription.
  Now, when updating the list of tagged subscriptions, the previous data will be completely replaced by the new ones.

# 0.1
- Implemented basic functionality
