import { Router } from "express";
import { requireUser } from "./auth";
import { db } from "./db";

export const router = Router();

router.get("/me", requireUser, async (req, res) => {
  const user = await db.users.findUnique({ where: { id: req.user.id } });
  res.json({ id: user.id, name: user.name, email: user.email });
});
