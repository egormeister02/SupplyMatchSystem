import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import os
from typing import Dict, List

def generate_requests_graph(data: Dict[str, List[Dict]], days: int) -> str:
    """
    Generate a combined bar and line graph showing daily request statistics
    
    Args:
        data: Dictionary containing supplier_requests and seeker_requests data
        days: Number of days to display
        
    Returns:
        str: Path to the generated image file
    """
    # Create figure and axis with high DPI for better quality
    plt.figure(figsize=(12, 8), dpi=300)
    ax = plt.gca()
    
    # Сформировать полный список дат
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days-1)
    all_dates = [start_date + timedelta(days=i) for i in range(days)]
    
    # Преобразовать данные в словари для быстрого доступа
    supplier_dict = {datetime.strptime(str(row['date']), '%Y-%m-%d').date(): row['count'] for row in data['supplier_requests']}
    seeker_dict = {datetime.strptime(str(row['date']), '%Y-%m-%d').date(): row['count'] for row in data['seeker_requests']}
    
    # Собрать значения по всем датам, подставляя 0 если нет данных
    supplier_counts = [supplier_dict.get(date, 0) for date in all_dates]
    seeker_counts = [seeker_dict.get(date, 0) for date in all_dates]
    total_counts = [s + r for s, r in zip(supplier_counts, seeker_counts)]
    dates = all_dates
    
    # Set width of bars
    bar_width = 0.35
    
    # Create bar chart
    x = range(len(dates))
    ax.bar([i - bar_width/2 for i in x], supplier_counts, bar_width, label='Заявки поставщиков', color='#2ecc71')
    ax.bar([i + bar_width/2 for i in x], seeker_counts, bar_width, label='Заявки искателей', color='#3498db')
    
    # Create line chart for total
    ax.plot(x, total_counts, 'r-', label='Общее количество', linewidth=2, color='#e74c3c')
    
    # Customize the graph
    ax.set_title(f'Динамика заявок за последние {days} дней', fontsize=14, pad=20)
    ax.set_xlabel('Дата', fontsize=12)
    ax.set_ylabel('Количество заявок', fontsize=12)
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, days//10)))
    ax.set_xticks(x)
    
    # Прореживание подписей дат, если дней больше 30
    if days > 30:
        step = max(1, days // 25)# Показывать примерно 10-15 подписей
        xticklabels = [date.strftime('%d.%m') if i % step == 0 else '' for i, date in enumerate(dates)]
    else:
        xticklabels = [date.strftime('%d.%m') for date in dates]
    ax.set_xticklabels(xticklabels, rotation=45)
    
    # Add legend
    ax.legend(loc='upper left')
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Adjust layout to prevent label cutoff
    plt.tight_layout()
    
    # Create directory for graphs if it doesn't exist
    os.makedirs('temp/graphs', exist_ok=True)
    
    # Save the graph
    file_path = f'temp/graphs/requests_by_days_{days}.png'
    plt.savefig(file_path)
    plt.close()
    
    return file_path

def generate_status_pie_charts(data: dict, days: int) -> str:
    """
    Генерирует изображение с тремя круговыми диаграммами по статусам заявок
    data: {'suppliers': [...], 'seekers': [...], 'all': [...]}
    days: за сколько дней
    Возвращает путь к файлу
    """
    status_map = {
        'approved': 'Одобрено',
        'closed': 'Одобрено',
        'rejected': 'Отклонено',
        'pending': 'Ожидает',
    }
    def prepare_counts(rows):
        counts = {'Одобрено': 0, 'Отклонено': 0, 'Ожидает': 0}
        for row in rows:
            label = status_map.get(row['status'], 'Другое')
            if label == 'Одобрено' and row['status'] == 'closed':
                # closed тоже как одобрено
                counts['Одобрено'] += row['count']
            elif label in counts:
                counts[label] += row['count']
            else:
                counts['Другое'] = counts.get('Другое', 0) + row['count']
        return counts
    supplier_counts = prepare_counts(data['suppliers'])
    seeker_counts = prepare_counts(data['seekers'])
    all_counts = prepare_counts(data['all'])
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), dpi=300)
    for ax, counts, title in zip(axes, [supplier_counts, seeker_counts, all_counts],
                                 ['Поставщики', 'Искатели', 'Все заявки']):
        labels = list(counts.keys())
        values = list(counts.values())
        ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 12})
        ax.set_title(title, fontsize=14)
    fig.suptitle(f'Статусы заявок за последние {days} дней', fontsize=16)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    os.makedirs('temp/graphs', exist_ok=True)
    file_path = f'temp/graphs/requests_status_pie_{days}.png'
    plt.savefig(file_path)
    plt.close()
    return file_path

def generate_top10_categories_bar(data: list, days: int = None) -> str:
    """
    Генерирует bar chart для топ-10 категорий по количеству заявок
    """
    categories = [row['main_category'] or 'Без категории' for row in data]
    counts = [row['request_count'] for row in data]
    plt.figure(figsize=(14, 8), dpi=300)
    bars = plt.bar(categories, counts, color='#3498db')
    plt.title(f"Топ-10 категорий по заявкам" + (f" за {days} дней" if days else " за всё время"), fontsize=16)
    plt.xlabel("Категория", fontsize=14)
    plt.ylabel("Количество заявок", fontsize=14)
    plt.xticks(rotation=30, ha='right')
    plt.tight_layout()
    for bar, count in zip(bars, counts):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), str(count), ha='center', va='bottom', fontsize=12)
    os.makedirs('temp/graphs', exist_ok=True)
    file_path = f'temp/graphs/top10_categories_{days if days else "all"}.png'
    plt.savefig(file_path)
    plt.close()
    return file_path

def generate_top10_suppliers_bar(data: list, days: int = None) -> str:
    """
    Генерирует bar chart для топ-10 активных поставщиков по количеству accepted matches
    """
    suppliers = [row['company_name'] or f"ID {row['supplier_id']}" for row in data]
    counts = [row['accepted_count'] for row in data]
    plt.figure(figsize=(14, 8), dpi=300)
    bars = plt.bar(suppliers, counts, color='#2ecc71')
    plt.title(f"Топ-10 активных поставщиков" + (f" за {days} дней" if days else " за всё время"), fontsize=16)
    plt.xlabel("Поставщик", fontsize=14)
    plt.ylabel("Количество принятых заявок", fontsize=14)
    plt.xticks(rotation=30, ha='right')
    plt.tight_layout()
    for bar, count in zip(bars, counts):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(), str(count), ha='center', va='bottom', fontsize=12)
    os.makedirs('temp/graphs', exist_ok=True)
    file_path = f'temp/graphs/top10_suppliers_{days if days else "all"}.png'
    plt.savefig(file_path)
    plt.close()
    return file_path
