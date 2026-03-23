-- ============================================================
--  Taxscio — client_database setup + seed
--  Run with: psql -U postgres -f seed_client_database.sql
-- ============================================================

-- 1. Create the database (run as superuser)
CREATE DATABASE client_database;

-- 2. Connect to the new database
\c client_database;

-- 3. Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TABLE: enum_master
-- ============================================================
CREATE TABLE IF NOT EXISTS enum_master (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    enum_type   VARCHAR(100) NOT NULL,
    code        VARCHAR(100) NOT NULL,
    label       VARCHAR(255) NOT NULL,
    description TEXT,
    sort_order  INTEGER      NOT NULL DEFAULT 0,
    color       VARCHAR(50),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    is_system   BOOLEAN      NOT NULL DEFAULT FALSE,
    tenant_id   UUID,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_enum_master_enum_type        ON enum_master(enum_type);
CREATE UNIQUE INDEX IF NOT EXISTS ix_enum_master_type_code ON enum_master(enum_type, code) WHERE tenant_id IS NULL;

-- ============================================================
-- TABLE: clients
-- ============================================================
CREATE TABLE IF NOT EXISTS clients (
    id                    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entity Info
    entity_type           VARCHAR(20)  NOT NULL,
    first_name            VARCHAR(100),
    last_name             VARCHAR(100),
    business_name         VARCHAR(255),
    trust_name            VARCHAR(255),
    date_of_birth         DATE,
    date_of_incorporation DATE,

    -- Contact
    email                 VARCHAR(150),
    phone                 VARCHAR(20),

    -- Tax Info
    tax_id                VARCHAR(50),
    country               VARCHAR(100),
    residency_status      VARCHAR(50),

    -- Address
    address_line1         TEXT,
    address_line2         TEXT,
    city                  VARCHAR(100),
    state                 VARCHAR(100),
    zip_code              VARCHAR(20),

    -- Classification
    lifecycle_stage       VARCHAR(50),
    risk_profile          VARCHAR(50),
    source                VARCHAR(100),

    -- Additional
    notes                 TEXT,
    tags                  JSONB DEFAULT '[]'::JSONB,

    -- Audit
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_clients_email           ON clients(email);
CREATE INDEX IF NOT EXISTS ix_clients_entity_type     ON clients(entity_type);
CREATE INDEX IF NOT EXISTS ix_clients_lifecycle_stage ON clients(lifecycle_stage);

-- Auto-update updated_at on row changes
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_clients_updated_at ON clients;
CREATE TRIGGER trg_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trg_enum_master_updated_at ON enum_master;
CREATE TRIGGER trg_enum_master_updated_at
    BEFORE UPDATE ON enum_master
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- SEED: enum_master
-- ============================================================

-- entity_type
INSERT INTO enum_master (enum_type, code, label, description, sort_order, color, is_active, is_system)
VALUES
  ('entity_type', 'INDIVIDUAL', 'Individual', 'Natural person',                      1,  '#6366f1', TRUE, TRUE),
  ('entity_type', 'BUSINESS',   'Business',   'Corporation, LLC, Partnership, etc.',  2,  '#0ea5e9', TRUE, TRUE),
  ('entity_type', 'TRUST',      'Trust',      'Trust or estate entity',               3,  '#8b5cf6', TRUE, TRUE)
ON CONFLICT DO NOTHING;

-- country (comprehensive list — ISO 3166-1 alpha-2 names)
INSERT INTO enum_master (enum_type, code, label, sort_order, is_active, is_system) VALUES
  ('country','US','United States',1,TRUE,TRUE),
  ('country','AF','Afghanistan',2,TRUE,FALSE),
  ('country','AL','Albania',3,TRUE,FALSE),
  ('country','DZ','Algeria',4,TRUE,FALSE),
  ('country','AD','Andorra',5,TRUE,FALSE),
  ('country','AO','Angola',6,TRUE,FALSE),
  ('country','AG','Antigua and Barbuda',7,TRUE,FALSE),
  ('country','AR','Argentina',8,TRUE,FALSE),
  ('country','AM','Armenia',9,TRUE,FALSE),
  ('country','AU','Australia',10,TRUE,FALSE),
  ('country','AT','Austria',11,TRUE,FALSE),
  ('country','AZ','Azerbaijan',12,TRUE,FALSE),
  ('country','BS','Bahamas',13,TRUE,FALSE),
  ('country','BH','Bahrain',14,TRUE,FALSE),
  ('country','BD','Bangladesh',15,TRUE,FALSE),
  ('country','BB','Barbados',16,TRUE,FALSE),
  ('country','BY','Belarus',17,TRUE,FALSE),
  ('country','BE','Belgium',18,TRUE,FALSE),
  ('country','BZ','Belize',19,TRUE,FALSE),
  ('country','BJ','Benin',20,TRUE,FALSE),
  ('country','BT','Bhutan',21,TRUE,FALSE),
  ('country','BO','Bolivia',22,TRUE,FALSE),
  ('country','BA','Bosnia and Herzegovina',23,TRUE,FALSE),
  ('country','BW','Botswana',24,TRUE,FALSE),
  ('country','BR','Brazil',25,TRUE,FALSE),
  ('country','BN','Brunei',26,TRUE,FALSE),
  ('country','BG','Bulgaria',27,TRUE,FALSE),
  ('country','BF','Burkina Faso',28,TRUE,FALSE),
  ('country','BI','Burundi',29,TRUE,FALSE),
  ('country','CV','Cabo Verde',30,TRUE,FALSE),
  ('country','KH','Cambodia',31,TRUE,FALSE),
  ('country','CM','Cameroon',32,TRUE,FALSE),
  ('country','CA','Canada',33,TRUE,FALSE),
  ('country','CF','Central African Republic',34,TRUE,FALSE),
  ('country','TD','Chad',35,TRUE,FALSE),
  ('country','CL','Chile',36,TRUE,FALSE),
  ('country','CN','China',37,TRUE,FALSE),
  ('country','CO','Colombia',38,TRUE,FALSE),
  ('country','KM','Comoros',39,TRUE,FALSE),
  ('country','CG','Congo',40,TRUE,FALSE),
  ('country','CR','Costa Rica',41,TRUE,FALSE),
  ('country','HR','Croatia',42,TRUE,FALSE),
  ('country','CU','Cuba',43,TRUE,FALSE),
  ('country','CY','Cyprus',44,TRUE,FALSE),
  ('country','CZ','Czech Republic',45,TRUE,FALSE),
  ('country','DK','Denmark',46,TRUE,FALSE),
  ('country','DJ','Djibouti',47,TRUE,FALSE),
  ('country','DM','Dominica',48,TRUE,FALSE),
  ('country','DO','Dominican Republic',49,TRUE,FALSE),
  ('country','EC','Ecuador',50,TRUE,FALSE),
  ('country','EG','Egypt',51,TRUE,FALSE),
  ('country','SV','El Salvador',52,TRUE,FALSE),
  ('country','GQ','Equatorial Guinea',53,TRUE,FALSE),
  ('country','ER','Eritrea',54,TRUE,FALSE),
  ('country','EE','Estonia',55,TRUE,FALSE),
  ('country','SZ','Eswatini',56,TRUE,FALSE),
  ('country','ET','Ethiopia',57,TRUE,FALSE),
  ('country','FJ','Fiji',58,TRUE,FALSE),
  ('country','FI','Finland',59,TRUE,FALSE),
  ('country','FR','France',60,TRUE,FALSE),
  ('country','GA','Gabon',61,TRUE,FALSE),
  ('country','GM','Gambia',62,TRUE,FALSE),
  ('country','GE','Georgia',63,TRUE,FALSE),
  ('country','DE','Germany',64,TRUE,FALSE),
  ('country','GH','Ghana',65,TRUE,FALSE),
  ('country','GR','Greece',66,TRUE,FALSE),
  ('country','GD','Grenada',67,TRUE,FALSE),
  ('country','GT','Guatemala',68,TRUE,FALSE),
  ('country','GN','Guinea',69,TRUE,FALSE),
  ('country','GW','Guinea-Bissau',70,TRUE,FALSE),
  ('country','GY','Guyana',71,TRUE,FALSE),
  ('country','HT','Haiti',72,TRUE,FALSE),
  ('country','HN','Honduras',73,TRUE,FALSE),
  ('country','HU','Hungary',74,TRUE,FALSE),
  ('country','IS','Iceland',75,TRUE,FALSE),
  ('country','IN','India',76,TRUE,FALSE),
  ('country','ID','Indonesia',77,TRUE,FALSE),
  ('country','IR','Iran',78,TRUE,FALSE),
  ('country','IQ','Iraq',79,TRUE,FALSE),
  ('country','IE','Ireland',80,TRUE,FALSE),
  ('country','IL','Israel',81,TRUE,FALSE),
  ('country','IT','Italy',82,TRUE,FALSE),
  ('country','JM','Jamaica',83,TRUE,FALSE),
  ('country','JP','Japan',84,TRUE,FALSE),
  ('country','JO','Jordan',85,TRUE,FALSE),
  ('country','KZ','Kazakhstan',86,TRUE,FALSE),
  ('country','KE','Kenya',87,TRUE,FALSE),
  ('country','KI','Kiribati',88,TRUE,FALSE),
  ('country','KW','Kuwait',89,TRUE,FALSE),
  ('country','KG','Kyrgyzstan',90,TRUE,FALSE),
  ('country','LA','Laos',91,TRUE,FALSE),
  ('country','LV','Latvia',92,TRUE,FALSE),
  ('country','LB','Lebanon',93,TRUE,FALSE),
  ('country','LS','Lesotho',94,TRUE,FALSE),
  ('country','LR','Liberia',95,TRUE,FALSE),
  ('country','LY','Libya',96,TRUE,FALSE),
  ('country','LI','Liechtenstein',97,TRUE,FALSE),
  ('country','LT','Lithuania',98,TRUE,FALSE),
  ('country','LU','Luxembourg',99,TRUE,FALSE),
  ('country','MG','Madagascar',100,TRUE,FALSE),
  ('country','MW','Malawi',101,TRUE,FALSE),
  ('country','MY','Malaysia',102,TRUE,FALSE),
  ('country','MV','Maldives',103,TRUE,FALSE),
  ('country','ML','Mali',104,TRUE,FALSE),
  ('country','MT','Malta',105,TRUE,FALSE),
  ('country','MH','Marshall Islands',106,TRUE,FALSE),
  ('country','MR','Mauritania',107,TRUE,FALSE),
  ('country','MU','Mauritius',108,TRUE,FALSE),
  ('country','MX','Mexico',109,TRUE,FALSE),
  ('country','FM','Micronesia',110,TRUE,FALSE),
  ('country','MD','Moldova',111,TRUE,FALSE),
  ('country','MC','Monaco',112,TRUE,FALSE),
  ('country','MN','Mongolia',113,TRUE,FALSE),
  ('country','ME','Montenegro',114,TRUE,FALSE),
  ('country','MA','Morocco',115,TRUE,FALSE),
  ('country','MZ','Mozambique',116,TRUE,FALSE),
  ('country','MM','Myanmar',117,TRUE,FALSE),
  ('country','NA','Namibia',118,TRUE,FALSE),
  ('country','NR','Nauru',119,TRUE,FALSE),
  ('country','NP','Nepal',120,TRUE,FALSE),
  ('country','NL','Netherlands',121,TRUE,FALSE),
  ('country','NZ','New Zealand',122,TRUE,FALSE),
  ('country','NI','Nicaragua',123,TRUE,FALSE),
  ('country','NE','Niger',124,TRUE,FALSE),
  ('country','NG','Nigeria',125,TRUE,FALSE),
  ('country','NO','Norway',126,TRUE,FALSE),
  ('country','OM','Oman',127,TRUE,FALSE),
  ('country','PK','Pakistan',128,TRUE,FALSE),
  ('country','PW','Palau',129,TRUE,FALSE),
  ('country','PA','Panama',130,TRUE,FALSE),
  ('country','PG','Papua New Guinea',131,TRUE,FALSE),
  ('country','PY','Paraguay',132,TRUE,FALSE),
  ('country','PE','Peru',133,TRUE,FALSE),
  ('country','PH','Philippines',134,TRUE,FALSE),
  ('country','PL','Poland',135,TRUE,FALSE),
  ('country','PT','Portugal',136,TRUE,FALSE),
  ('country','QA','Qatar',137,TRUE,FALSE),
  ('country','RO','Romania',138,TRUE,FALSE),
  ('country','RU','Russia',139,TRUE,FALSE),
  ('country','RW','Rwanda',140,TRUE,FALSE),
  ('country','KN','Saint Kitts and Nevis',141,TRUE,FALSE),
  ('country','LC','Saint Lucia',142,TRUE,FALSE),
  ('country','VC','Saint Vincent and the Grenadines',143,TRUE,FALSE),
  ('country','WS','Samoa',144,TRUE,FALSE),
  ('country','SM','San Marino',145,TRUE,FALSE),
  ('country','ST','Sao Tome and Principe',146,TRUE,FALSE),
  ('country','SA','Saudi Arabia',147,TRUE,FALSE),
  ('country','SN','Senegal',148,TRUE,FALSE),
  ('country','RS','Serbia',149,TRUE,FALSE),
  ('country','SC','Seychelles',150,TRUE,FALSE),
  ('country','SL','Sierra Leone',151,TRUE,FALSE),
  ('country','SG','Singapore',152,TRUE,FALSE),
  ('country','SK','Slovakia',153,TRUE,FALSE),
  ('country','SI','Slovenia',154,TRUE,FALSE),
  ('country','SB','Solomon Islands',155,TRUE,FALSE),
  ('country','SO','Somalia',156,TRUE,FALSE),
  ('country','ZA','South Africa',157,TRUE,FALSE),
  ('country','SS','South Sudan',158,TRUE,FALSE),
  ('country','ES','Spain',159,TRUE,FALSE),
  ('country','LK','Sri Lanka',160,TRUE,FALSE),
  ('country','SD','Sudan',161,TRUE,FALSE),
  ('country','SR','Suriname',162,TRUE,FALSE),
  ('country','SE','Sweden',163,TRUE,FALSE),
  ('country','CH','Switzerland',164,TRUE,FALSE),
  ('country','SY','Syria',165,TRUE,FALSE),
  ('country','TW','Taiwan',166,TRUE,FALSE),
  ('country','TJ','Tajikistan',167,TRUE,FALSE),
  ('country','TZ','Tanzania',168,TRUE,FALSE),
  ('country','TH','Thailand',169,TRUE,FALSE),
  ('country','TL','Timor-Leste',170,TRUE,FALSE),
  ('country','TG','Togo',171,TRUE,FALSE),
  ('country','TO','Tonga',172,TRUE,FALSE),
  ('country','TT','Trinidad and Tobago',173,TRUE,FALSE),
  ('country','TN','Tunisia',174,TRUE,FALSE),
  ('country','TR','Turkey',175,TRUE,FALSE),
  ('country','TM','Turkmenistan',176,TRUE,FALSE),
  ('country','TV','Tuvalu',177,TRUE,FALSE),
  ('country','UG','Uganda',178,TRUE,FALSE),
  ('country','UA','Ukraine',179,TRUE,FALSE),
  ('country','AE','United Arab Emirates',180,TRUE,FALSE),
  ('country','GB','United Kingdom',181,TRUE,FALSE),
  ('country','UY','Uruguay',182,TRUE,FALSE),
  ('country','UZ','Uzbekistan',183,TRUE,FALSE),
  ('country','VU','Vanuatu',184,TRUE,FALSE),
  ('country','VE','Venezuela',185,TRUE,FALSE),
  ('country','VN','Vietnam',186,TRUE,FALSE),
  ('country','YE','Yemen',187,TRUE,FALSE),
  ('country','ZM','Zambia',188,TRUE,FALSE),
  ('country','ZW','Zimbabwe',189,TRUE,FALSE)
ON CONFLICT DO NOTHING;

-- residency_status
INSERT INTO enum_master (enum_type, code, label, sort_order, color, is_active, is_system) VALUES
  ('residency_status', 'RESIDENT',   'Resident',   1, '#16a34a', TRUE, TRUE),
  ('residency_status', 'FOREIGNER',  'Foreigner',  2, '#d97706', TRUE, TRUE)
ON CONFLICT DO NOTHING;

-- state (US only)
INSERT INTO enum_master (enum_type, code, label, sort_order, is_active, is_system) VALUES
  ('state','AL','Alabama',1,TRUE,TRUE),
  ('state','AK','Alaska',2,TRUE,TRUE),
  ('state','AZ','Arizona',3,TRUE,TRUE),
  ('state','AR','Arkansas',4,TRUE,TRUE),
  ('state','CA','California',5,TRUE,TRUE),
  ('state','CO','Colorado',6,TRUE,TRUE),
  ('state','CT','Connecticut',7,TRUE,TRUE),
  ('state','DE','Delaware',8,TRUE,TRUE),
  ('state','FL','Florida',9,TRUE,TRUE),
  ('state','GA','Georgia',10,TRUE,TRUE),
  ('state','HI','Hawaii',11,TRUE,TRUE),
  ('state','ID','Idaho',12,TRUE,TRUE),
  ('state','IL','Illinois',13,TRUE,TRUE),
  ('state','IN','Indiana',14,TRUE,TRUE),
  ('state','IA','Iowa',15,TRUE,TRUE),
  ('state','KS','Kansas',16,TRUE,TRUE),
  ('state','KY','Kentucky',17,TRUE,TRUE),
  ('state','LA','Louisiana',18,TRUE,TRUE),
  ('state','ME','Maine',19,TRUE,TRUE),
  ('state','MD','Maryland',20,TRUE,TRUE),
  ('state','MA','Massachusetts',21,TRUE,TRUE),
  ('state','MI','Michigan',22,TRUE,TRUE),
  ('state','MN','Minnesota',23,TRUE,TRUE),
  ('state','MS','Mississippi',24,TRUE,TRUE),
  ('state','MO','Missouri',25,TRUE,TRUE),
  ('state','MT','Montana',26,TRUE,TRUE),
  ('state','NE','Nebraska',27,TRUE,TRUE),
  ('state','NV','Nevada',28,TRUE,TRUE),
  ('state','NH','New Hampshire',29,TRUE,TRUE),
  ('state','NJ','New Jersey',30,TRUE,TRUE),
  ('state','NM','New Mexico',31,TRUE,TRUE),
  ('state','NY','New York',32,TRUE,TRUE),
  ('state','NC','North Carolina',33,TRUE,TRUE),
  ('state','ND','North Dakota',34,TRUE,TRUE),
  ('state','OH','Ohio',35,TRUE,TRUE),
  ('state','OK','Oklahoma',36,TRUE,TRUE),
  ('state','OR','Oregon',37,TRUE,TRUE),
  ('state','PA','Pennsylvania',38,TRUE,TRUE),
  ('state','RI','Rhode Island',39,TRUE,TRUE),
  ('state','SC','South Carolina',40,TRUE,TRUE),
  ('state','SD','South Dakota',41,TRUE,TRUE),
  ('state','TN','Tennessee',42,TRUE,TRUE),
  ('state','TX','Texas',43,TRUE,TRUE),
  ('state','UT','Utah',44,TRUE,TRUE),
  ('state','VT','Vermont',45,TRUE,TRUE),
  ('state','VA','Virginia',46,TRUE,TRUE),
  ('state','WA','Washington',47,TRUE,TRUE),
  ('state','WV','West Virginia',48,TRUE,TRUE),
  ('state','WI','Wisconsin',49,TRUE,TRUE),
  ('state','WY','Wyoming',50,TRUE,TRUE),
  ('state','DC','District of Columbia',51,TRUE,TRUE)
ON CONFLICT DO NOTHING;

-- lifecycle_stage
INSERT INTO enum_master (enum_type, code, label, sort_order, color, is_active, is_system) VALUES
  ('lifecycle_stage', 'PROSPECT', 'Prospect', 1, '#6366f1', TRUE, TRUE),
  ('lifecycle_stage', 'ACTIVE',   'Active',   2, '#16a34a', TRUE, TRUE),
  ('lifecycle_stage', 'DORMANT',  'Dormant',  3, '#d97706', TRUE, TRUE),
  ('lifecycle_stage', 'CLOSED',   'Closed',   4, '#ef4444', TRUE, TRUE)
ON CONFLICT DO NOTHING;

-- risk_profile
INSERT INTO enum_master (enum_type, code, label, sort_order, color, is_active, is_system) VALUES
  ('risk_profile', 'LOW',    'Low',    1, '#16a34a', TRUE, TRUE),
  ('risk_profile', 'MEDIUM', 'Medium', 2, '#d97706', TRUE, TRUE),
  ('risk_profile', 'HIGH',   'High',   3, '#ef4444', TRUE, TRUE)
ON CONFLICT DO NOTHING;

-- source
INSERT INTO enum_master (enum_type, code, label, sort_order, is_active, is_system) VALUES
  ('source', 'REFERRAL', 'Referral', 1, TRUE, TRUE),
  ('source', 'WEBSITE',  'Website',  2, TRUE, TRUE),
  ('source', 'PARTNER',  'Partner',  3, TRUE, TRUE)
ON CONFLICT DO NOTHING;

-- Done
SELECT 'client_database setup complete ✓' AS status;
