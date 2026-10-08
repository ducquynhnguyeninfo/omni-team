-- Suppliers can define their own custom roles. Role names only need to be unique
-- within a scope ('global' or 'supplier:<id>').
ALTER TABLE roles DROP CONSTRAINT roles_name_key;
CREATE UNIQUE INDEX roles_scope_name_key ON roles (scope, name);
