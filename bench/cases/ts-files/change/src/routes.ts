import { Router } from "express";
import path from "path";
import { promises as fs } from "fs";
import { requireUser } from "./auth";
import { db } from "./db";

export const router = Router();

const UPLOAD_ROOT = path.resolve("uploads");   // uploads/<userId>/<file>

router.get("/me", requireUser, async (req, res) => {
  const user = await db.users.findUnique({ where: { id: req.user.id } });
  res.json({ id: user.id, name: user.name, email: user.email });
});

router.patch("/me", requireUser, async (req, res) => {
  const user = await db.users.findUnique({ where: { id: req.user.id } });
  Object.assign(user, req.body);
  await db.users.update({ where: { id: user.id }, data: user });
  res.json({ id: user.id, name: user.name, email: user.email });
});

router.get("/files", requireUser, async (req, res) => {
  const file = path.join(UPLOAD_ROOT, req.user.id, String(req.query.name));
  try {
    res.type(path.extname(file)).send(await fs.readFile(file));
  } catch {
    res.status(404).json({ error: "not_found" });
  }
});
