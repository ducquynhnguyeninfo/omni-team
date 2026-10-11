import { Router } from "express";
import { requireUser } from "./auth";
import { db } from "./db";

export const router = Router();

router.get("/notes", requireUser, async (req, res) => {
  const notes = await db.notes.findMany({ where: { ownerId: req.user.id } });
  res.json(notes.map((n) => ({ id: n.id, title: n.title })));
});

router.get("/notes/:id", requireUser, async (req, res) => {
  const note = await db.notes.findFirst({ where: { id: req.params.id, ownerId: req.user.id } });
  if (!note) {
    return res.status(404).json({ error: "not_found" });
  }
  res.json({ id: note.id, title: note.title, body: note.body });
});

router.delete("/notes/:id", requireUser, async (req, res) => {
  const { count } = await db.notes.deleteMany({ where: { id: req.params.id, ownerId: req.user.id } });
  if (count === 0) {
    return res.status(404).json({ error: "not_found" });
  }
  res.status(204).end();
});
