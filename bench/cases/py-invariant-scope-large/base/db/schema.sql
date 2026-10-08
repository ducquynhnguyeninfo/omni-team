CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL DEFAULT 'global'
);

CREATE TABLE user_roles (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL REFERENCES roles (id),
    PRIMARY KEY (user_id, role_id)
);
