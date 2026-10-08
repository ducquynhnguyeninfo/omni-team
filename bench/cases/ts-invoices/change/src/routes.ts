import { Router } from "express";
import { requireUser } from "./auth";
import { db } from "./db";

export const router = Router();

router.get("/invoices", requireUser, async (req, res) => {
  const invoices = await db.invoices.findMany({ where: { ownerId: req.user.id } });
  res.json(invoices);
});

router.get("/invoices/:id", requireUser, async (req, res) => {
  try {
    const invoice = await db.invoices.findUnique({ where: { id: req.params.id } });
    if (!invoice) {
      return res.status(404).json({ error: "not_found" });
    }
    res.json(invoice);
  } catch (err: any) {
    res.status(500).json({ error: err.message, stack: err.stack });
  }
});
