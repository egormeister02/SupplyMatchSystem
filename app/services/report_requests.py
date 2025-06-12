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

    @staticmethod
    async def get_seeker_requests_report(months: int = None):
        date_filter = ""
        params = {}
        if months:
            date_filter = "AND r.created_at >= :date_from"
            from_date = datetime.now() - timedelta(days=30 * months)
            params["date_from"] = from_date
        query = f'''
        SELECT 
            r.id AS request_id,
            r.created_at::date AS date,
            mc.name AS main_category,
            c.name AS category,
            COUNT(m.id) AS matches_count,
            COUNT(CASE WHEN m.status = 'accepted' OR m.status = 'closed' THEN 1 END) AS accepted_count,
            COUNT(CASE WHEN m.status = 'rejected' THEN 1 END) AS rejected_count,
            r.status
        FROM requests r
        LEFT JOIN categories c ON r.category_id = c.id
        LEFT JOIN main_categories mc ON c.main_category_name = mc.name
        LEFT JOIN matches m ON r.id = m.request_id
        WHERE 1=1 {date_filter}
        GROUP BY r.id, r.created_at, mc.name, c.name, r.status
        ORDER BY r.created_at DESC
        '''
        return await DBService.fetch_data(query, params if params else None)

    @staticmethod
    async def get_suppliers_activity_report(months: int = None):
        date_filter = ""
        params = {}
        if months:
            date_filter = "AND s.created_at >= :date_from"
            from_date = datetime.now() - timedelta(days=30 * months)
            params["date_from"] = from_date
        query = f'''
        SELECT 
            s.id AS supplier_id,
            s.created_at::date AS created_at,
            (
                SELECT MAX(m2.created_at)
                FROM matches m2
                WHERE m2.supplier_id = s.id AND m2.status != 'pending'
            ) AS last_activity,
            COUNT(CASE WHEN m.status = 'accepted' THEN 1 END) AS accepted_count,
            COUNT(CASE WHEN m.status = 'rejected' THEN 1 END) AS rejected_count,
            COUNT(CASE WHEN m.status = 'closed' THEN 1 END) AS closed_count,
            (
                SELECT ROUND(AVG(r.mark)::numeric, 2)
                FROM reviews r
                WHERE r.review_id = s.id
            ) AS rating
        FROM suppliers s
        LEFT JOIN matches m ON s.id = m.supplier_id
        WHERE 1=1 {date_filter}
        GROUP BY s.id, s.created_at
        ORDER BY last_activity DESC NULLS LAST, s.created_at DESC
        '''
        return await DBService.fetch_data(query, params if params else None)

    @staticmethod
    async def get_reviews_report(months: int = None):
        date_filter = ""
        params = {}
        if months:
            date_filter = "AND r.created_at >= :date_from"
            from_date = datetime.now() - timedelta(days=30 * months)
            params["date_from"] = from_date
        query = f'''
        SELECT 
            r.created_at::date AS created_at,
            r.review_id AS supplier_id,
            r.author_id AS request_id,
            u.username AS author_username,
            r.mark,
            r.review AS text
        FROM reviews r
        LEFT JOIN requests req ON r.author_id = req.id
        LEFT JOIN users u ON req.created_by_id = u.tg_id
        WHERE 1=1 {date_filter}
        ORDER BY r.created_at DESC
        '''
        return await DBService.fetch_data(query, params if params else None)

    @staticmethod
    async def get_requests_by_days(days: int):
        """
        Get daily statistics for supplier and seeker requests for the specified number of days
        """
        date_filter = "AND created_at >= :date_from"
        from_date = datetime.now() - timedelta(days=days)
        params = {"date_from": from_date}

        # Query for supplier requests
        supplier_query = f'''
        SELECT 
            created_at::date AS date,
            COUNT(*) as count
        FROM suppliers
        WHERE 1=1 {date_filter}
        GROUP BY created_at::date
        ORDER BY date
        '''
        supplier_data = await DBService.fetch_data(supplier_query, params)

        # Query for seeker requests
        seeker_query = f'''
        SELECT 
            created_at::date AS date,
            COUNT(*) as count
        FROM requests
        WHERE 1=1 {date_filter}
        GROUP BY created_at::date
        ORDER BY date
        '''
        seeker_data = await DBService.fetch_data(seeker_query, params)

        return {
            "supplier_requests": supplier_data,
            "seeker_requests": seeker_data
        }

    @staticmethod
    async def get_requests_status_pie_data(days: int = None):
        """
        Получить данные для круговой диаграммы по статусам заявок за N дней (или за всё время, если days=None)
        Возвращает словарь с данными для поставщиков, искателей и всех вместе
        """
        params = {}
        date_filter = ""
        if days is not None and days > 0:
            date_filter = "AND created_at >= :date_from"
            from_date = datetime.now() - timedelta(days=days)
            params["date_from"] = from_date
        # Поставщики
        supplier_query = f'''
        SELECT status, COUNT(*) as count
        FROM suppliers
        WHERE 1=1 {date_filter}
        GROUP BY status
        '''
        supplier_data = await DBService.fetch_data(supplier_query, params if params else None)
        # Искатели
        seeker_query = f'''
        SELECT status, COUNT(*) as count
        FROM requests
        WHERE 1=1 {date_filter}
        GROUP BY status
        '''
        seeker_data = await DBService.fetch_data(seeker_query, params if params else None)
        # Суммарно
        all_status_counts = {}
        for row in supplier_data + seeker_data:
            status = row['status']
            all_status_counts[status] = all_status_counts.get(status, 0) + row['count']
        return {
            'suppliers': supplier_data,
            'seekers': seeker_data,
            'all': [{'status': k, 'count': v} for k, v in all_status_counts.items()]
        }

    @staticmethod
    async def get_top10_categories(days: int = None):
        params = {}
        date_filter = ""
        if days and days > 0:
            date_filter = "AND r.created_at >= :date_from"
            from_date = datetime.now() - timedelta(days=days)
            params["date_from"] = from_date
        query = f'''
        SELECT 
            mc.name AS main_category,
            COUNT(*) AS request_count
        FROM requests r
        LEFT JOIN categories c ON r.category_id = c.id
        LEFT JOIN main_categories mc ON c.main_category_name = mc.name
        WHERE 1=1 {date_filter}
        GROUP BY mc.name
        ORDER BY request_count DESC NULLS LAST
        LIMIT 10
        '''
        return await DBService.fetch_data(query, params if params else None)

    @staticmethod
    async def get_top10_suppliers_by_activity(days: int = None):
        params = {}
        date_filter = ""
        if days and days > 0:
            date_filter = "AND m.created_at >= :date_from"
            from_date = datetime.now() - timedelta(days=days)
            params["date_from"] = from_date
        query = f'''
        SELECT 
            s.id AS supplier_id,
            s.company_name,
            COUNT(m.id) AS accepted_count
        FROM suppliers s
        LEFT JOIN matches m ON s.id = m.supplier_id AND m.status = 'accepted'
        WHERE 1=1 {date_filter}
        GROUP BY s.id, s.company_name
        ORDER BY accepted_count DESC NULLS LAST
        LIMIT 10
        '''
        return await DBService.fetch_data(query, params if params else None)
