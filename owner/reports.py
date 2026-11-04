"""A real Excel workbook of recorded collections, using standard OOXML."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from events.models import Event

from .workspace import scope


def workbook(rows):
    sheet = []
    for number, row in enumerate(rows, 1):
        cells = []
        for value in row:
            if isinstance(value, (Decimal, int)):
                cells.append(f"<c><v>{value}</v></c>")
            else:
                # Inline strings prevent spreadsheet formula injection from branch names.
                clean = "".join(c for c in str(value) if ord(c) >= 32 or c in "\t\n\r")
                cells.append(f'<c t="inlineStr"><is><t>{escape(clean)}</t></is></c>')
        sheet.append(f'<row r="{number}">{"".join(cells)}</row>')
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    files = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Daily collections" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{ns}"><sheetData>{"".join(sheet)}</sheetData></worksheet>',
    }
    stream = BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(
                path,
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + content,
            )
    return stream.getvalue()


@require_GET
@never_cache
def sales(request):
    ctx = scope(request)
    try:
        today = timezone.localdate()
        start = date.fromisoformat(
            request.GET.get("start") or today.replace(day=1).isoformat()
        )
        end = date.fromisoformat(request.GET.get("end") or today.isoformat())
        if start > end:
            raise ValueError()
    except ValueError:
        return HttpResponse(
            "Choose valid dates, with the start on or before the end.", status=422
        )
    totals = {}
    for e in Event.objects.filter(
        branch__in=ctx["chosen"],
        occurred_at__date__range=(start, end),
        type__in=["payment_recorded", "self_service_started"],
    ).select_related("branch"):
        method = e.payload.get("method")
        if method not in ("cash", "gcash"):
            continue
        key = (timezone.localdate(e.occurred_at), e.branch.number, e.branch.name)
        row = totals.setdefault(key, {"cash": Decimal("0"), "gcash": Decimal("0")})
        row[method] += Decimal(e.payload["amount"])
    rows = [
        [
            "Date (Asia/Manila)",
            "Branch",
            "Cash (PHP)",
            "GCash (PHP)",
            "Total collections (PHP)",
        ]
    ]
    for (day, _, name), amounts in sorted(totals.items()):
        rows.append(
            [
                day.isoformat(),
                name,
                amounts["cash"],
                amounts["gcash"],
                sum(amounts.values()),
            ]
        )
    response = HttpResponse(
        workbook(rows),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="washday-sales-{start}-{end}.xlsx"'
    )
    return response
