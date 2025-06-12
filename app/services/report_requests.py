from app.services.database import DBService
from datetime import datetime, timedelta

class ReportRequests(DBService):
    @staticmethod
    async def get_supplier_requests_report(months: int = None):
        date_filter = ""
        params = {}
        if months:
            date_filter = "AND s.created_at >= :date_from"
            from_date = datetime.now() - timedelta(days=30 * months)
            params["date_from"] = from_date
        query = f'''
        SELECT 
            s.id AS supplier_id,
            s.created_at::date AS date,
            s.company_name,
            mc.name AS main_category,
            c.name AS category,
            s.status,
            u_verified.username AS verified_by
        FROM suppliers s
        LEFT JOIN categories c ON s.category_id = c.id
        LEFT JOIN main_categories mc ON c.main_category_name = mc.name
        LEFT JOIN users u_verified ON s.verified_by_id = u_verified.tg_id
        WHERE s.status IN ('approved', 'rejected')
        {date_filter}
        ORDER BY s.created_at DESC
        '''
        return await DBService.fetch_data(query, params if params else None)
