import { Router } from "express";
import { sendError } from "./http";
import { db } from "./db";

export const router = Router();

router.get("/products/:id", async (req, res) => {
  const product = await db.products.findUnique({ where: { id: req.params.id } });
  if (!product) {
    return sendError(res, 404, "not_found", "Product not found");
  }
  res.json(product);
});
