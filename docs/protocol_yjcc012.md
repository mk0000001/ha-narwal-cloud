# Narwal YJCC012 cloud protocol notes

These notes contain only redacted protocol structure. Tokens, account IDs,
device IDs, private MQTT captures, and map geometry are intentionally excluded.

## Transport

- Regional REST base: `https://kr-app.narwaltech.com`
- MQTT broker is discovered through
  `/iot-broker-discover/app/v1/broker/discover?country=KR`.
- MQTT uses TLS and protocol level 5.
- The access token is the MQTT password. The 32-character account UUID is the
  MQTT username and appears in request header fields 1 and 2.
- Commands use a response topic and request UUID in header field 5.
- The official app subscribes to `<command topic>/response` before publishing.
- Payload framing is:
  `0x01 + varint(header_length) + header_protobuf + command_body_protobuf`.

## Confirmed commands

### Pause

- Topic: `/<product>/<device>/task/pause`
- Command body: empty

### Resume

- Topic: `/<product>/<device>/task/resume`
- Command body: empty

### Start whole-house Freo Mind cleaning

- Topic: `/<product>/<device>/clean/easy_clean/start`
- Body fields:
  - field 1: `1`
  - field 2: `1`
  - repeated field 3: one room plan per room
    - room field 1: room ID
    - room field 2: `3`
    - room field 6:
      - field 1: `2`
      - field 2: `1`
      - field 3: `2`
      - field 4: `1`
- The current test map exposes room IDs 1 through 7. This is a temporary
  device-specific fallback until map-response decoding supplies them
  dynamically.

### End task

- Topic: `/<product>/<device>/task/force_end`
- Command body: `12 02 01 02`
- Home Assistant mapping: `VacuumEntityFeature.STOP` / `async_stop()`

## State

- REST endpoint: `/device-task/work-status/get`
- Required parameter: `source=0`
- Confirmed state transitions:
  - idle to cleaning after `clean/easy_clean/start`
  - cleaning to idle after `task/force_end`
  - returning is exposed by `recall=true`

## Pending captures and implementation

- Add a map camera and HA room segments using the decoded map.
- Expose mode, suction, humidity, and cycle selectors.
- Add dock wash-and-dry and finish buttons.
- Capture a dedicated dock recall command if it differs from ending a task.
- Separate authentication from the API client and add an interactive login
  flow while retaining manual tokens as an advanced fallback.

## Deployment policy

Do not deploy intermediate builds to Home Assistant. Bundle STOP, map/room
support, cleaning modes, and mop station actions into one tested release, then
apply that release once.

## Map and room discovery

- Request: `/map/get_map`, body `08 00 10 00`
- Response: `/map/get_map/response`
- Response body field 1 is success (`1`); field 2 is the map message.
- Map fields: revision `2`, resolution `3`, width `4`, height `5`,
  repeated room metadata `12`, zlib-compressed grid `17`.
- Room fields: ID `1`, type `2`, UTF-8 custom name `3`, category `4`,
  duplicate instance index `8`.
- Verified YJCC012 map revision 28: 197 x 206, seven rooms.

## Cleaning modes and options

`/clean/plan/get/response` returns the official defaults. Plan field 3 is
the mode number and repeated field 9 contains per-room templates.

The `/clean/easy_clean/start` body has:

- field 1: mode
- field 2: constant `1`
- repeated field 3: room configuration

Verified mode values:

- `1`: Freo Mind
- `2`: Vacuum
- `3`: Mop
- `4`: Vacuum and mop
- `5`: Vacuum then mop

Per-room configuration starts with room ID field 1 and constant field 2 = 1.

- Vacuum: field 4 message; suction field 1 (`1` quiet, `2` standard,
  `3` strong), cycle field 2 (`1`-`3`).
- Mop: field 5 message; constant field 1 = 1, cycle field 2 (`1`-`3`),
  humidity field 3 (`1` slightly dry, `2` standard, `3` slightly wet).
- Vacuum and mop: field 6; suction field 1, vacuum cycle field 2,
  humidity field 3, mop cycle field 4.
- Vacuum then mop: field 7 containing vacuum settings as field 1 and mop
  settings as field 2.
- Freo Mind uses the captured automatic per-room settings and does not
  accept manual option selects.

## Dock mop washing

- Start washing followed by automatic drying:
  `/supply/wash_and_dry_mop`, empty body.
- Finish washing or drying:
  `/task/force_end`, empty body in the current official app. The previously
  captured `12 02 01 02` body is also accepted for ending an active task.
  YJCC012 applies this command without returning a response, so successful
  transmission is treated as success instead of surfacing a false timeout.

## Live map and robot pose

- `/map/get_map`, body `08 00 10 00`.
- Static map payload field 7: `origin` (`PoseData`).
- Static map payload field 8: `station` (`PoseData`).
- Static map payload field 24: `robot_pose` (`PoseData`).
- Static map payload field 36: `robot_pose_update_time`.
- The camera is rendered from the current compressed grid and pose fields; no
  screenshot is retained.

## Battery status

- Request topic: `/status/get_device_base_status`.
- Asynchronous broadcast: `/status/robot_base_status`.
- YJCC012 battery percentage is protobuf fixed32 float field `2`.
- Verified against a live value of `100.0` from firmware `v01.05.01.02`.

## Consumables

- `POST /consumables-management-app-server/v3/consumables/list`
- JSON body fields: `deviceId`, `productId`.
- Timed rows expose `total_duration` and `usage_duration` in seconds.
- Remaining hours are
  `ceil((total_duration - usage_duration) / 3600)`.
