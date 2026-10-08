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

router.get("/products/:id/sale-price", async (req, res) => {
  const discount = Number(req.query.discount ?? 10);
  if (discount < 0 || discount > 90) {
    return res.status(400).json({ error: "discount out of range" });
  }
  const product = await db.products.findUnique({ where: { id: req.params.id } });
  if (!product) {
    return sendError(res, 404, "not_found", "Product not found");
  }
  const salePrice = (product.priceCents / 100) * (1 - discount / 100);
  res.json({ id: product.id, salePrice: salePrice.toFixed(2) });
});
