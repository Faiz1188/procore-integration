<<<<<<< HEAD
CREATE TABLE projects (
=======
CREATE TABLE IF NOT EXISTS projects (
>>>>>>> 9f691a5c8baca5cb5c80126cb7141c08d41602cc
    id BIGINT PRIMARY KEY,
    name TEXT,
    status TEXT,
    created_at TIMESTAMP,
    synced_at TIMESTAMP DEFAULT NOW()
);

<<<<<<< HEAD
CREATE TABLE submittals (
    id BIGINT PRIMARY KEY,
    project_id BIGINT,
=======
CREATE TABLE IF NOT EXISTS submittals (
    id BIGINT PRIMARY KEY,
    project_id BIGINT REFERENCES projects(id),
>>>>>>> 9f691a5c8baca5cb5c80126cb7141c08d41602cc
    title TEXT,
    status TEXT,
    responsible_contractor TEXT,
    received_date DATE,
    returned_date DATE,
    on_site_date DATE,
    revision_count INT DEFAULT 0,
    synced_at TIMESTAMP DEFAULT NOW()
);
