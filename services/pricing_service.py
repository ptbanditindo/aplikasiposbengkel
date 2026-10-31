"""Mesin kalkulasi finansial presisi Decimal.

Ref: PRD FR-POS-05 & FR-POS-06 / FR-POS-07.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Iterable, List

from services.errors import BusinessValidationError, PaymentError
from services.utils import money, to_decimal


def line_subtotal(jumlah: Any, harga: Any) -> Decimal:
    qty = int(jumlah)
    price = money(harga)
    if qty < 1:
        raise BusinessValidationError("Jumlah item minimal 1.")
    if price < 0:
        raise BusinessValidationError("Harga tidak boleh negatif.")
    return money(Decimal(qty) * price)


def compute_invoice(
    jobs: Iterable[Dict[str, Any]],
    parts: Iterable[Dict[str, Any]],
    diskon: Any = 0,
) -> Dict[str, Decimal]:
    biaya_jasa = Decimal("0.00")
    total_part = Decimal("0.00")

    for job in jobs:
        biaya_jasa += line_subtotal(job["jumlah"], job["harga"])
    for part in parts:
        total_part += line_subtotal(part["jumlah"], part["harga_satuan"])

    biaya_jasa = money(biaya_jasa)
    total_part = money(total_part)
    subtotal = money(biaya_jasa + total_part)
    diskon_value = money(diskon)

    if diskon_value < 0:
        raise BusinessValidationError("Diskon tidak boleh negatif.")
    if diskon_value > subtotal:
        raise BusinessValidationError("Diskon melebihi subtotal transaksi.")

    total_servis = money(subtotal - diskon_value)
    return {
        "biaya_jasa": biaya_jasa,
        "total_part": total_part,
        "subtotal": subtotal,
        "diskon": diskon_value,
        "total_servis": total_servis,
    }


def compute_payment(total_servis: Any, metode_bayar: str, bayar: Any) -> Dict[str, Decimal]:
    total = money(total_servis)
    method = (metode_bayar or "").strip().upper()

    if method == "CASH":
        paid = money(bayar)
        if paid < total:
            raise PaymentError(
                "Uang tunai yang diterima kurang dari grand total transaksi."
            )
        return {"bayar": paid, "kembalian": money(paid - total)}

    if method == "TRANSFER":
        # Ref: PRD FR-POS-07 - transfer selalu pas & kembalian Rp 0.
        return {"bayar": total, "kembalian": Decimal("0.00")}

    raise BusinessValidationError("Metode pembayaran harus CASH atau TRANSFER.")


def compute_dp_payment(total_servis: Any, dp: Any) -> Dict[str, Decimal]:
    """Uang muka (DP) harus lebih dari nol dan lebih kecil dari grand total."""
    total = money(total_servis)
    uang_muka = money(dp)
    if total <= 0 or uang_muka <= 0:
        raise PaymentError("DP harus lebih dari Rp 0.")
    if uang_muka >= total:
        raise PaymentError(
            "DP harus lebih kecil dari grand total. Gunakan Lunas bila "
            "pelanggan membayar penuh."
        )
    return {
        "bayar": uang_muka,
        "kembalian": Decimal("0.00"),
        "sisa": money(total - uang_muka),
    }


def compute_credit_payment(
    total_servis: Any, uang_muka: Any = 0, rencana_bayar: Any = 0
) -> Dict[str, Decimal]:
    """Kredit: uang muka opsional (boleh Rp 0), sisanya menjadi tagihan.

    Rencana pembayaran adalah nominal yang dijanjikan pelanggan dan tidak boleh
    melebihi sisa tagihan.
    """
    total = money(total_servis)
    muka = money(uang_muka)
    if muka < 0:
        raise PaymentError("Uang muka tidak boleh negatif.")
    if muka >= total:
        raise PaymentError(
            "Uang muka harus lebih kecil dari grand total. Gunakan Lunas bila "
            "pelanggan membayar penuh."
        )
    sisa = money(total - muka)
    rencana = money(rencana_bayar)
    if rencana > sisa:
        raise PaymentError(
            "Rencana pembayaran tidak boleh melebihi sisa tagihan."
        )
    return {
        "bayar": muka,
        "kembalian": Decimal("0.00"),
        "sisa": sisa,
    }


def compute_payment_preview(
    total_servis: Any, metode_bayar: str, bayar: Any
) -> Dict[str, Decimal]:
    """Perkiraan pembayaran untuk layar kasir.

    Nilai final tetap dihitung compute_payment saat nota disimpan; pratinjau
    ini sengaja toleran terhadap uang kurang agar kasir melihat kekurangannya.
    """
    total = money(total_servis)
    method = (metode_bayar or "").strip().upper()
    paid = total if method == "TRANSFER" else money(bayar)
    return {
        "bayar": paid,
        "kembalian": money(max(paid - total, Decimal("0.00"))),
        "kekurangan": money(max(total - paid, Decimal("0.00"))),
    }


def calculate_gross_profit(part_lines: List[Dict[str, Any]]) -> Decimal:
    """Laba kotor sparepart = (harga jual deal - harga modal master) x qty."""
    profit = Decimal("0.00")
    for line in part_lines:
        if line.get("harga_modal") is None:
            continue
        profit += (to_decimal(line["harga_satuan"]) - to_decimal(line["harga_modal"])) * int(
            line["jumlah"]
        )
    return money(profit)
