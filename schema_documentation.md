# Database Schema Documentation

**Database:** events_db

**Generated:** sam 01 nov 2025 16:02:46 EDT

---

## Tables

- [corrective_measure](#corrective_measure)
- [event](#event)
- [event_corrective_measure](#event_corrective_measure)
- [event_employee](#event_employee)
- [event_risk](#event_risk)
- [organizational_unit](#organizational_unit)
- [person](#person)
- [risk](#risk)

---

## corrective_measure

| Column | Type | Nullable | Key | Description |
|--------|------|----------|-----|-------------|
| measure_id | integer | ✗ | PK |  |
| name | character varying(255) | ✗ |  |  |
| description | text | ✓ |  |  |
| owner_id | integer | ✗ |  |  |
| implementation_date | date | ✓ |  |  |
| cost | numeric | ✓ |  |  |
| organizational_unit_id | integer | ✗ |  |  |


## event

| Column | Type | Nullable | Key | Description |
|--------|------|----------|-----|-------------|
| event_id | integer | ✗ | PK |  |
| declared_by_id | integer | ✗ |  |  |
| description | text | ✗ |  |  |
| start_datetime | timestamp without time zone | ✗ |  |  |
| end_datetime | timestamp without time zone | ✓ |  |  |
| organizational_unit_id | integer | ✗ |  |  |
| type | character varying(50) | ✗ |  |  |
| classification | character varying(50) | ✗ |  |  |


## event_corrective_measure

| Column | Type | Nullable | Key | Description |
|--------|------|----------|-----|-------------|
| event_id | integer | ✗ | PK |  |
| measure_id | integer | ✗ | PK |  |


## event_employee

| Column | Type | Nullable | Key | Description |
|--------|------|----------|-----|-------------|
| event_id | integer | ✗ | PK |  |
| person_id | integer | ✗ | PK |  |
| involvement_type | character varying(255) | ✓ |  |  |


## event_risk

| Column | Type | Nullable | Key | Description |
|--------|------|----------|-----|-------------|
| event_id | integer | ✗ | PK |  |
| risk_id | integer | ✗ | PK |  |


## organizational_unit

| Column | Type | Nullable | Key | Description |
|--------|------|----------|-----|-------------|
| unit_id | integer | ✗ | PK |  |
| identifier | character varying(255) | ✗ |  |  |
| name | character varying(255) | ✗ |  |  |
| location | character varying(255) | ✗ |  |  |


## person

| Column | Type | Nullable | Key | Description |
|--------|------|----------|-----|-------------|
| person_id | integer | ✗ | PK |  |
| matricule | character varying(255) | ✗ |  |  |
| name | character varying(255) | ✗ |  |  |
| family_name | character varying(255) | ✗ |  |  |
| role | character varying(255) | ✗ |  |  |


## risk

| Column | Type | Nullable | Key | Description |
|--------|------|----------|-----|-------------|
| risk_id | integer | ✗ | PK |  |
| name | character varying(200) | ✗ |  |  |
| gravity | character varying(20) | ✗ |  |  |
| probability | character varying(20) | ✗ |  |  |


## Foreign Key Relationships

| From Table | From Column | To Table | To Column |
|------------|-------------|----------|-----------|
| corrective_measure | organizational_unit_id | organizational_unit | unit_id |
| corrective_measure | owner_id | person | person_id |
| event | declared_by_id | person | person_id |
| event | organizational_unit_id | organizational_unit | unit_id |
| event_corrective_measure | event_id | event | event_id |
| event_corrective_measure | measure_id | corrective_measure | measure_id |
| event_employee | event_id | event | event_id |
| event_employee | person_id | person | person_id |
| event_risk | event_id | event | event_id |
| event_risk | risk_id | risk | risk_id |