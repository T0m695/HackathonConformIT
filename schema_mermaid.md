```mermaid
erDiagram

    CORRECTIVE_MEASURE 
        integer measure_id PK NOT NULL
        character varying(255) name NOT NULL
        text description
        integer owner_id NOT NULL
        date implementation_date
        numeric cost
        integer organizational_unit_id NOT NULL
    }

    EVENT 
        integer event_id PK NOT NULL
        integer declared_by_id NOT NULL
        text description NOT NULL
        timestamp without time zone start_datetime NOT NULL
        timestamp without time zone end_datetime
        integer organizational_unit_id NOT NULL
        character varying(50) type NOT NULL
        character varying(50) classification NOT NULL
    }

    EVENT_CORRECTIVE_MEASURE 
        integer event_id PK NOT NULL
        integer measure_id PK NOT NULL
    }

    EVENT_EMPLOYEE 
        integer event_id PK NOT NULL
        integer person_id PK NOT NULL
        character varying(255) involvement_type
    }

    EVENT_RISK 
        integer event_id PK NOT NULL
        integer risk_id PK NOT NULL
    }

    ORGANIZATIONAL_UNIT 
        integer unit_id PK NOT NULL
        character varying(255) identifier NOT NULL
        character varying(255) name NOT NULL
        character varying(255) location NOT NULL
    }

    PERSON 
        integer person_id PK NOT NULL
        character varying(255) matricule NOT NULL
        character varying(255) name NOT NULL
        character varying(255) family_name NOT NULL
        character varying(255) role NOT NULL
    }

    RISK 
        integer risk_id PK NOT NULL
        character varying(200) name NOT NULL
        character varying(20) gravity NOT NULL
        character varying(20) probability NOT NULL
    }

    CORRECTIVE_MEASURE ||--o{ ORGANIZATIONAL_UNIT : "organizational_unit_id"
    CORRECTIVE_MEASURE ||--o{ PERSON : "owner_id"
    EVENT ||--o{ PERSON : "declared_by_id"
    EVENT ||--o{ ORGANIZATIONAL_UNIT : "organizational_unit_id"
    EVENT_CORRECTIVE_MEASURE ||--o{ EVENT : "event_id"
    EVENT_CORRECTIVE_MEASURE ||--o{ CORRECTIVE_MEASURE : "measure_id"
    EVENT_EMPLOYEE ||--o{ EVENT : "event_id"
    EVENT_EMPLOYEE ||--o{ PERSON : "person_id"
    EVENT_RISK ||--o{ EVENT : "event_id"
    EVENT_RISK ||--o{ RISK : "risk_id"
```
