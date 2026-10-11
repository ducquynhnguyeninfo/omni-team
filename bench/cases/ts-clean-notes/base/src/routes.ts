import { Router } from "express";
import { requireUser } from "./auth";
import { db } from "./db";

export const router = Router();

router.get("/notes", requireUser, async (req, res) => {
  const notes = await db.notes.findMany({ where: { ownerId: req.user.id } });
  res.json(notes.map((n) => ({ id: n.id, title: n.title })));
});
