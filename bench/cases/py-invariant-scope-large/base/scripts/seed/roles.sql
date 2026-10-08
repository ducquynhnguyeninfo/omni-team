-- Built-in roles. Safe to re-run on every deploy.
INSERT INTO roles (name, scope) VALUES ('admin', 'global') ON CONFLICT (name) DO NOTHING;
INSERT INTO roles (name, scope) VALUES ('operator', 'global') ON CONFLICT (name) DO NOTHING;
INSERT INTO roles (name, scope) VALUES ('viewer', 'global') ON CONFLICT (name) DO NOTHING;
