CREATE TABLE projects (
    id BIGINT PRIMARY KEY,
    name TEXT,
    status TEXT,
    created_at TIMESTAMP,
    synced_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE submittals (
    id BIGINT PRIMARY KEY,
    project_id BIGINT,
    title TEXT,
    status TEXT,
    responsible_contractor TEXT,
    received_date DATE,
    returned_date DATE,
    on_site_date DATE,
    revision_count INT DEFAULT 0,
    synced_at TIMESTAMP DEFAULT NOW()
);
