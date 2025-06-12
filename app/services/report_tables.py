import openpyxl
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter
from tempfile import NamedTemporaryFile

class ReportXLSX:
    def __init__(self, data: list, headers: list, sheet_title: str, row_builder):
        self.data = data
        self.headers = headers
        self.sheet_title = sheet_title
        self.table_style = "TableStyleMedium9"
        self.row_builder = row_builder  # функция, которая строит строку по элементу data

    async def generate(self) -> str:
        """
        Генерирует xlsx-файл с отчётом.
        Возвращает путь к временному файлу.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = self.sheet_title

        ws.append(self.headers)

        for row in self.data:
            ws.append(self.row_builder(row))

        # Add autofilter
        ws.auto_filter.ref = ws.dimensions

        # Table styling
        tab = Table(displayName="ReportTable", ref=ws.dimensions)
        style = TableStyleInfo(name=self.table_style, showFirstColumn=False,
                               showLastColumn=False, showRowStripes=True, showColumnStripes=False)
        tab.tableStyleInfo = style
        ws.add_table(tab)

        # Auto column width
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            ws.column_dimensions[column].width = max_length + 2

        # Save to temp file
        with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            wb.save(tmp.name)
            return tmp.name

class SupplierRequestsReportXLSX(ReportXLSX):
    def __init__(self, data: list):
        headers = [
            "ID заявки", "Дата", "Название компании", "Категория", "Подкатегория", "Статус", "Проверил"
        ]
        sheet_title = "Заявки на поставщиков"
        def row_builder(row):
            return [
                row.get("supplier_id"),
                row.get("date"),
                row.get("company_name"),
                row.get("main_category"),
                row.get("category"),
                row.get("status"),
                row.get("verified_by")
            ]
        super().__init__(data, headers, sheet_title, row_builder)

class SeekerRequestsReportXLSX(ReportXLSX):
    def __init__(self, data: list):
        headers = [
            "ID заявки", "Дата", "Категория", "Подкатегория", "Сколько поставщиков получили заявку", "Сколько приняли", "Сколько отклонили", "Статус"
        ]
        sheet_title = "Заявки искателей"
        def row_builder(row):
            return [
                row.get("request_id"),
                row.get("date"),
                row.get("main_category"),
                row.get("category"),
                row.get("matches_count"),
                row.get("accepted_count"),
                row.get("rejected_count"),
                row.get("status")
            ]
        super().__init__(data, headers, sheet_title, row_builder)
