import { Router } from "express";
import { requireUser } from "./auth";
import { db } from "./db";

export const router = Router();

router.get("/invoices", requireUser, async (req, res) => {
  const invoices = await db.invoices.findMany({ where: { ownerId: req.user.id } });
  res.json(invoices);
});
