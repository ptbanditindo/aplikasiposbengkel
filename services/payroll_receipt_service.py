"""Nota gaji karyawan dalam bentuk teks WhatsApp terstruktur."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from database.models import Employee, SalaryPayment
from services import employee_debt_service, employee_service, settings_service


def _rp(value) -> str:
    amount = Decimal(value or 0)
    return "Rp " + f"{amount:,.0f}".replace(",", ".")


def _rate(value) -> str:
    number = Decimal(value or 0).normalize()
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _date(value) -> str:
    return value.strftime("%d-%m-%Y") if value else "-"


def _method(payment: SalaryPayment) -> str:
    return "Transfer" if payment.metode == "TRANSFER" else "Tunai"


def build_text(db: Session, payment: SalaryPayment) -> str:
    employee = (
        db.get(Employee, payment.employee_id)
        if payment.employee_id
        else None
    )
    info = settings_service.get_bengkel_info(db)
    nama_bengkel = info.get("nama") or "Bengkel"
    lines = [
        "",
        "**NOTA GAJI**",
        nama_bengkel,
        "",
        "--------------------------------",
        "",
        "Karyawan : " + payment.nama_karyawan,
        "Periode  : " + (payment.periode or "-"),
        "Tanggal  : " + _date(payment.tanggal),
        "Metode   : " + _method(payment),
    ]
    if payment.metode == "TRANSFER" and employee is not None:
        rekening = " · ".join(
            [
                part
                for part in (
                    employee.bank_nama,
                    employee.bank_nomor,
                    "a.n. " + employee.bank_atas_nama
                    if employee.bank_atas_nama
                    else "",
                )
                if part
            ]
        )
        if rekening:
            lines.append("Rekening : " + rekening)

    if employee is None:
        lines.extend(
            [
                "",
                "--------------------------------",
                "",
                "*TOTAL DIBAYAR: " + _rp(payment.nominal) + "*",
                "",
                "Terima kasih.",
            ]
        )
        return "\n".join(lines)

    start = payment.cycle_start or employee_service.payroll_cycle_start(
        employee, payment.tanggal
    )
    records = employee_service.records_for_range(
        db, employee, start, payment.tanggal
    )
    breakdown = employee_service.commission_breakdown(db, employee, records)
    salary_due = employee_service.salary_due_for_receipt(employee)

    sections = []
    if salary_due > 0:
        sections.append("*GAJI*\nGaji periode ini: " + _rp(salary_due))

    goods_rows = [row for row in breakdown if row["goods_commission"] > 0]
    if goods_rows:
        item_lines = ["*KOMISI BARANG*"]
        for row in goods_rows:
            item_lines.append(
                "- Nota "
                + row["no_nota"]
                + " · "
                + _date(row["waktu_service"].date())
            )
            if row["parts"]:
                item_lines.append("  Barang: " + ", ".join(row["parts"]))
            rate = employee.komisi_barang_nilai
            item_lines.append(
                "  Margin "
                + _rp(row["margin"])
                + " x "
                + _rate(rate)
                + "% = "
                + _rp(row["goods_commission"])
            )
        sections.append("\n".join(item_lines))

    service_rows = [
        row for row in breakdown if row["service_commission"] > 0
    ]
    if service_rows:
        item_lines = ["*KOMISI JASA*"]
        for row in service_rows:
            item_lines.append(
                "- Nota "
                + row["no_nota"]
                + " · "
                + _date(row["waktu_service"].date())
            )
            if row["jobs"]:
                item_lines.append("  Jasa: " + ", ".join(row["jobs"]))
            item_lines.append(
                "  Jasa "
                + _rp(row["jasa"])
                + " x "
                + _rate(employee.komisi_jasa_nilai)
                + "% = "
                + _rp(row["service_commission"])
            )
        sections.append("\n".join(item_lines))

    manual_rows = [
        row
        for row in breakdown
        if (row["manual"] or row["nominal_mode"]) and row["total"] > 0
    ]
    if manual_rows:
        item_lines = ["*KOMISI NOTA*"]
        for row in manual_rows:
            label = "Komisi manual" if row["manual"] else "Komisi nota"
            item_lines.append(
                "- Nota "
                + row["no_nota"]
                + " · "
                + label
                + ": "
                + _rp(row["total"])
            )
        sections.append("\n".join(item_lines))

    if payment.bonus > 0:
        bonus_text = "*BONUS*\nBonus: " + _rp(payment.bonus)
        if payment.bonus_keterangan:
            bonus_text += "\nKeterangan: " + payment.bonus_keterangan
        sections.append(bonus_text)

    outstanding_after = employee_debt_service.outstanding_by_employee(db).get(
        employee.id, Decimal("0.00")
    )
    potongan = Decimal(payment.potongan_hutang or 0)
    cicilan = Decimal(payment.cicilan_hutang or 0)
    debt_before = outstanding_after + potongan + cicilan
    if potongan > 0 or cicilan > 0 or outstanding_after > 0:
        debt_lines = ["*HUTANG*"]
        if debt_before > 0:
            debt_lines.append("Hutang awal periode: " + _rp(debt_before))
        if potongan > 0:
            debt_lines.append("Dipotong dari gaji: " + _rp(potongan))
        if cicilan > 0:
            debt_lines.append("Cicilan dibayar: " + _rp(cicilan))
        if outstanding_after <= 0:
            debt_lines.append("Status: Hutang lunas")
        else:
            debt_lines.append(
                "Sisa hutang (dibawa ke periode berikutnya): "
                + _rp(outstanding_after)
            )
        sections.append("\n".join(debt_lines))

    if sections:
        lines.append("")
        lines.append("\n\n".join(sections))
    else:
        lines.extend(["", "Belum ada rincian gaji atau komisi pada periode ini."])

    lines.extend(
        [
            "",
            "--------------------------------",
            "",
            "*TOTAL DIBAYAR: " + _rp(payment.nominal) + "*",
            "",
            "Terima kasih.",
        ]
    )
    return "\n".join(lines)
